"""
Community analytics — isolated observer module.

Event types logged to JSONL: msg
Member fields added: invite_source, clicked_welcome_at, first_message_at, third_message_at
Daily stats keys added: members_eod, unique_posters, top5_messages, replies
No shared writes with moderation, karma, or filter logic.
"""
import csv
import os
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from .. import storage, tg


def _today_start_ts():
    dt = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(dt.timestamp())


def _iso_week(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%G-W%V")


# ── Event recording ───────────────────────────────────────────────────────

def record_message(chat_id, message):
    """Log message metadata to JSONL event log. No message text is stored."""
    actor = message.get("from") or {}
    user_id = actor.get("id")
    if not user_id:
        return
    reply = message.get("reply_to_message")
    is_reply = reply is not None
    reply_to_uid = None
    if reply:
        rf = reply.get("from") or {}
        reply_to_uid = rf.get("id")
    storage.append_event(chat_id, "msg", user_id=user_id, meta={
        "msg_id": message.get("message_id"),
        "is_reply": is_reply,
        "reply_to_uid": str(reply_to_uid) if reply_to_uid else None,
    })


def stamp_activation(group, user_id, field):
    """Set an activation timestamp on a member if not already stamped."""
    member = group["members"].get(str(user_id))
    if member is not None and not member.get(field):
        member[field] = storage.now_ts()


def on_message_sent(state, chat_id, message):
    """
    Called after core.record_message_stat (so message_count is already incremented).
    Logs message metadata and stamps first/third-message activation milestones.
    """
    actor = message.get("from") or {}
    user_id = actor.get("id")
    if not user_id:
        return
    record_message(chat_id, message)
    group = storage.get_group(state, chat_id)
    member = group["members"].get(str(user_id))
    if member is None:
        return
    mc = member.get("message_count", 0)
    if mc == 1:
        stamp_activation(group, user_id, "first_message_at")
    elif mc == 3:
        stamp_activation(group, user_id, "third_message_at")


# ── Daily rollup ──────────────────────────────────────────────────────

def daily_rollup(state, chat_id):
    """
    Recompute today's enriched stats from today's msg events.
    Idempotent: overwrites same-day entry every cycle.
    """
    group = storage.get_group(state, chat_id)
    today = storage.today_str()
    day_start = _today_start_ts()

    user_msgs = defaultdict(int)
    reply_count = 0
    for ev in storage.read_events(chat_id=chat_id, types=["msg"], since_ts=day_start):
        uid = ev.get("user_id")
        if uid:
            user_msgs[uid] += 1
        if ev.get("meta", {}).get("is_reply"):
            reply_count += 1

    counts = sorted(user_msgs.values(), reverse=True)
    active_members = sum(1 for m in group["members"].values() if not m.get("left_date"))

    daily = group["stats"]["daily"].setdefault(today, {"messages": 0, "joins": 0, "leaves": 0})
    daily["members_eod"] = active_members
    daily["unique_posters"] = len(user_msgs)
    daily["top5_messages"] = sum(counts[:5])
    daily["replies"] = reply_count


def daily_rollup_all(state):
    for cid in list(state["groups"].keys()):
        try:
            daily_rollup(state, int(cid))
        except Exception:
            pass


# ── Welcome callback ─────────────────────────────────────────────────────

def handle_welcome_callback(state, callback_query):
    """
    Handle the 'Start here' inline button click.
    Returns True if the callback was consumed, False to fall through to captcha handler.
    """
    data = callback_query.get("data", "")
    if not data.startswith("welcome:"):
        return False

    from_user = callback_query.get("from") or {}
    user_id = from_user.get("id")
    msg = callback_query.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")

    if not user_id or not chat_id:
        tg.answer_callback_query(callback_query["id"])
        return True

    expected_uid = data.split(":", 1)[1]
    if str(user_id) != expected_uid:
        tg.answer_callback_query(callback_query["id"],
                                  text="This button isn't for you.", show_alert=True)
        return True

    group = storage.get_group(state, chat_id)
    stamp_activation(group, user_id, "clicked_welcome_at")
    orientation = (
        group["settings"].get("orientation_text")
        or "Welcome! Please read the group rules and introduce yourself."
    )
    tg.answer_callback_query(callback_query["id"], text=orientation[:200], show_alert=True)
    return True


# ── Admin commands ───────────────────────────────────────────────────────

def _require_admin(message, chat_id):
    return tg.is_admin(chat_id, message["from"]["id"])


def cmd_export(state, chat_id, message, args):
    """Export daily stats as CSV."""
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    days = int(args[0]) if args and args[0].isdigit() else 30
    group = storage.get_group(state, chat_id)
    end_date = datetime.now(timezone.utc).date()

    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Date", "Members", "Joins", "Leaves", "Total Messages",
                          "Unique Posters", "Msgs from Top 5 Posters", "Replies"])
        for i in range(days - 1, -1, -1):
            day = (end_date - timedelta(days=i)).strftime("%Y-%m-%d")
            d = group["stats"]["daily"].get(day, {})
            writer.writerow([
                day,
                d.get("members_eod", ""),
                d.get("joins", 0),
                d.get("leaves", 0),
                d.get("messages", 0),
                d.get("unique_posters", ""),
                d.get("top5_messages", ""),
                d.get("replies", ""),
            ])

    tg.send_document(chat_id, path, caption=f"Export: last {days} days")
    os.remove(path)


def cmd_cohorts(state, chat_id, message, args):
    """Cohort retention CSV: Join Week, Cohort Size, Active D7, Active D14, Active D30."""
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    group = storage.get_group(state, chat_id)

    user_msg_times = defaultdict(list)
    for ev in storage.read_events(chat_id=chat_id, types=["msg"]):
        uid = ev.get("user_id")
        if uid:
            user_msg_times[uid].append(ev["ts"])

    by_week = defaultdict(list)
    for uid, m in group["members"].items():
        jd = m.get("join_date")
        if jd:
            by_week[_iso_week(jd)].append((uid, jd))

    if not by_week:
        return tg.send_message(chat_id, "Not enough join history yet.")

    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Join Week", "Cohort Size", "Active D7", "Active D14", "Active D30"])
        for week in sorted(by_week.keys()):
            cohort = by_week[week]
            size = len(cohort)
            d7 = d14 = d30 = 0
            for uid, join_ts in cohort:
                times = user_msg_times.get(str(uid), [])
                if any(join_ts <= t < join_ts + 7 * 86400 for t in times):
                    d7 += 1
                if any(join_ts + 7 * 86400 <= t < join_ts + 14 * 86400 for t in times):
                    d14 += 1
                if any(join_ts + 23 * 86400 <= t < join_ts + 30 * 86400 for t in times):
                    d30 += 1
            writer.writerow([week, size, d7, d14, d30])

    tg.send_document(chat_id, path, caption="Cohort retention by join week")
    os.remove(path)


def cmd_funnel(state, chat_id, message, args):
    """Activation funnel for the last N weeks: joined → clicked welcome → 1st msg → 3rd msg."""
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    weeks = int(args[0]) if args and args[0].isdigit() else 4
    cutoff_ts = storage.now_ts() - weeks * 7 * 86400
    group = storage.get_group(state, chat_id)

    joined = clicked = first = third = 0
    for m in group["members"].values():
        if m.get("join_date", 0) < cutoff_ts:
            continue
        joined += 1
        if m.get("clicked_welcome_at"):
            clicked += 1
        if m.get("first_message_at"):
            first += 1
        if m.get("third_message_at"):
            third += 1

    def pct(n):
        return f"{100 * n // joined}%" if joined else "—"

    lines = [
        f"Joined: {joined}",
        f"Clicked welcome: {clicked} ({pct(clicked)})",
        f"Sent first message: {first} ({pct(first)})",
        f"Sent 3rd message: {third} ({pct(third)})",
    ]
    tg.send_message(chat_id, f"<b>Activation funnel (last {weeks}w)</b>\n" + "\n".join(lines))


def cmd_distinct(state, chat_id, message, args):
    """Count distinct posters over the last N days from the msg event log."""
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    days = int(args[0]) if args and args[0].isdigit() else 7
    since_ts = storage.now_ts() - days * 86400

    posters = set()
    for ev in storage.read_events(chat_id=chat_id, types=["msg"], since_ts=since_ts):
        uid = ev.get("user_id")
        if uid:
            posters.add(uid)

    tg.send_message(chat_id, f"Distinct posters in the last {days} days: <b>{len(posters)}</b>")
