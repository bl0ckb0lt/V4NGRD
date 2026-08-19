"""
Community analytics — isolated observer module.

Event types: msg
Member fields: invite_source, clicked_welcome_at, first_message_at, third_message_at,
               drip3_sent, drip7_sent
Daily stats: members_eod, unique_posters, top5_messages, replies
"""
import csv
import os
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from .. import storage, tg, util


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _today_start_ts():
    dt = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(dt.timestamp())


def _iso_week(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%G-W%V")


# ── Event recording ─────────────────────────────────────────────────────

def record_message(chat_id, message):
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
    member = group["members"].get(str(user_id))
    if member is not None and not member.get(field):
        member[field] = storage.now_ts()


def on_message_sent(state, chat_id, message):
    """Called after core.record_message_stat (message_count already incremented)."""
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


# ── Invite source capture ───────────────────────────────────────────────

def handle_chat_member(state, update_data):
    """Capture invite_source from chat_member updates when a user joins."""
    chat = update_data.get("chat") or {}
    chat_id = chat.get("id")
    if not chat_id:
        return
    old = update_data.get("old_chat_member") or {}
    new_cm = update_data.get("new_chat_member") or {}
    old_status = old.get("status", "")
    new_status = new_cm.get("status", "")
    user = new_cm.get("user") or {}
    user_id = user.get("id")
    if not user_id or user.get("is_bot"):
        return
    if old_status in ("left", "kicked") and new_status in ("member", "restricted", "administrator", "creator"):
        invite = update_data.get("invite_link") or {}
        source = invite.get("name") or invite.get("invite_link") or "direct"
        group = storage.get_group(state, chat_id)
        member = group["members"].get(str(user_id))
        if member:
            member["invite_source"] = source


# ── Daily rollup ──────────────────────────────────────────────────────

def daily_rollup(state, chat_id):
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
    active = sum(1 for m in group["members"].values() if not m.get("left_date"))
    daily = group["stats"]["daily"].setdefault(today, {"messages": 0, "joins": 0, "leaves": 0})
    daily["members_eod"] = active
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
        tg.answer_callback_query(callback_query["id"], text="This button isn't for you.", show_alert=True)
        return True
    group = storage.get_group(state, chat_id)
    stamp_activation(group, user_id, "clicked_welcome_at")
    orientation = (group["settings"].get("orientation_text")
                   or "Welcome! Please read the group rules and introduce yourself.")
    tg.answer_callback_query(callback_query["id"], text=orientation[:200], show_alert=True)
    return True


# ── Onboarding drip sweep ──────────────────────────────────────────────────

def drip_sweep(state):
    now = storage.now_ts()
    for cid in list(state["groups"].keys()):
        try:
            _drip_group(state, int(cid), now)
        except Exception:
            pass


def _drip_group(state, chat_id, now):
    group = storage.get_group(state, chat_id)
    if not group["settings"].get("drip_enabled"):
        return
    day3_text = (group["settings"].get("drip_day3_text")
                 or "Hey {first_name}, you haven't said hello in {group} yet! Come introduce yourself.")
    day7_text = (group["settings"].get("drip_day7_text")
                 or "It's been a week, {first_name}! Share something with {group}.")
    group_title = group.get("title") or "the group"
    for uid, member in group["members"].items():
        if member.get("left_date") or member.get("first_message_at"):
            continue
        join_date = member.get("join_date", 0)
        age = now - join_date
        first_name = member.get("first_name") or "there"
        if age >= 3 * 86400 and not member.get("drip3_sent"):
            member["drip3_sent"] = True
            text = day3_text.replace("{first_name}", first_name).replace("{group}", group_title)
            tg.try_call("sendMessage", {"chat_id": int(uid), "text": text})
        if age >= 7 * 86400 and not member.get("drip7_sent"):
            member["drip7_sent"] = True
            text = day7_text.replace("{first_name}", first_name).replace("{group}", group_title)
            tg.try_call("sendMessage", {"chat_id": int(uid), "text": text})


# ── Warn expiry sweep ─────────────────────────────────────────────────────

def warn_expiry_sweep(state):
    now = storage.now_ts()
    for cid in list(state["groups"].keys()):
        try:
            group = storage.get_group(state, int(cid))
            expiry_days = group["settings"].get("warn_expiry_days", 0)
            if not expiry_days:
                continue
            cutoff = now - expiry_days * 86400
            for member in group["members"].values():
                times = member.get("warn_times", [])
                if not times:
                    continue
                fresh = [t for t in times if t > cutoff]
                if len(fresh) != len(times):
                    member["warn_times"] = fresh
                    member["warns"] = len(fresh)
        except Exception:
            pass


# ── Health score ────────────────────────────────────────────────────────

def _compute_health(state, chat_id):
    group = storage.get_group(state, chat_id)
    now = storage.now_ts()
    active = sum(1 for m in group["members"].values() if not m.get("left_date"))
    joins_30d = sum(
        1 for m in group["members"].values()
        if m.get("join_date", 0) > now - 30 * 86400 and not m.get("left_date")
    )
    leaves_30d = sum(
        1 for m in group["members"].values()
        if m.get("left_date") and m["left_date"] > now - 30 * 86400
    )
    net = joins_30d - leaves_30d
    growth_rate = net / max(active, 1)
    growth_score = int(_clamp((growth_rate + 0.05) / 0.15 * 25, 0, 25))

    new_mems = [m for m in group["members"].values() if m.get("join_date", 0) > now - 30 * 86400]
    if new_mems:
        activated = sum(
            1 for m in new_mems
            if m.get("first_message_at") and
               m["first_message_at"] - m.get("join_date", 0) <= 7 * 86400
        )
        act_rate = activated / len(new_mems)
    else:
        act_rate = 0.0
    activation_score = int(act_rate * 25)

    since_7d = now - 7 * 86400
    total_msgs = replies = 0
    posters_7d = set()
    for ev in storage.read_events(chat_id=chat_id, types=["msg"], since_ts=since_7d):
        total_msgs += 1
        uid = ev.get("user_id")
        if uid:
            posters_7d.add(uid)
        if ev.get("meta", {}).get("is_reply"):
            replies += 1
    reply_ratio = replies / max(total_msgs, 1)
    depth_score = int(_clamp(reply_ratio / 0.4, 0, 1) * 25)
    breadth = len(posters_7d) / max(active, 1)
    breadth_score = int(_clamp(breadth / 0.2, 0, 1) * 25)

    score = growth_score + activation_score + depth_score + breadth_score
    return score, {
        "growth": growth_score, "activation": activation_score,
        "depth": depth_score, "breadth": breadth_score,
        "active": active, "net_30d": net,
        "act_rate": round(act_rate * 100, 1),
        "reply_ratio": round(reply_ratio * 100, 1),
        "breadth_pct": round(breadth * 100, 1),
    }


# ── Admin commands ───────────────────────────────────────────────────────

def _require_admin(message, chat_id):
    return tg.is_admin(chat_id, message["from"]["id"])


def cmd_health(state, chat_id, message, args):
    score, bd = _compute_health(state, chat_id)
    rating = ("Excellent" if score >= 80 else "Good" if score >= 60
              else "Fair" if score >= 40 else "Needs work")
    bar = "█" * (score // 10) + "░" * (10 - score // 10)
    lines = [
        f"<b>Community Health: {score}/100 — {rating}</b>",
        f"<code>{bar}</code>",
        "",
        f"Growth (+{bd['growth']}/25): net {bd['net_30d']:+d} members over 30d",
        f"Activation (+{bd['activation']}/25): {bd['act_rate']}% posted within 7d of joining",
        f"Depth (+{bd['depth']}/25): {bd['reply_ratio']}% of messages are replies",
        f"Breadth (+{bd['breadth']}/25): {bd['breadth_pct']}% of members posted this week",
    ]
    tg.send_message(chat_id, "\n".join(lines))


def cmd_activation(state, chat_id, message, args):
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    group = storage.get_group(state, chat_id)
    now = storage.now_ts()
    new_mems = [
        m for m in group["members"].values()
        if m.get("join_date", 0) > now - 30 * 86400 and not m.get("left_date")
    ]
    total = len(new_mems)
    if not total:
        return tg.send_message(chat_id, "No new members in the last 30 days.")

    def rate(window):
        n = sum(
            1 for m in new_mems
            if m.get("first_message_at") and
               m["first_message_at"] - m.get("join_date", 0) <= window
        )
        return n, round(100 * n / total, 1)

    n24, p24 = rate(86400)
    n72, p72 = rate(3 * 86400)
    n7d, p7d = rate(7 * 86400)
    tg.send_message(chat_id, "\n".join([
        f"<b>New member activation (last 30d, n={total})</b>",
        f"Within 24h: {n24} ({p24}%)",
        f"Within 72h: {n72} ({p72}%)",
        f"Within 7 days: {n7d} ({p7d}%)",
    ]))


def cmd_segment(state, chat_id, message, args):
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    group = storage.get_group(state, chat_id)
    now = storage.now_ts()
    posters_7d = set()
    for ev in storage.read_events(chat_id=chat_id, types=["msg"], since_ts=now - 7 * 86400):
        uid = ev.get("user_id")
        if uid:
            posters_7d.add(uid)
    segs = {"new": [], "engaged": [], "dormant": [], "atrisk": [], "churned": []}
    for uid, m in group["members"].items():
        jd = m.get("join_date", 0)
        left = m.get("left_date")
        mc = m.get("message_count", 0)
        la = m.get("last_active", 0)
        name = m.get("first_name") or uid
        if left:
            if mc >= 1:
                segs["churned"].append(name)
        else:
            if jd > now - 7 * 86400:
                segs["new"].append(name)
            if uid in posters_7d:
                segs["engaged"].append(name)
            if jd < now - 30 * 86400 and mc == 0:
                segs["dormant"].append(name)
            if mc >= 3 and la < now - 14 * 86400:
                segs["atrisk"].append(name)
    seg_name = args[0].lower() if args else None
    if seg_name and seg_name in segs:
        lst = segs[seg_name]
        if not lst:
            return tg.send_message(chat_id, f"No members in segment '{seg_name}'.")
        preview = lst[:20]
        extra = len(lst) - 20
        lines = [f"<b>Segment: {seg_name} ({len(lst)})</b>"]
        lines += [f"- {util.escape_html(str(n))}" for n in preview]
        if extra > 0:
            lines.append(f"… and {extra} more")
        tg.send_message(chat_id, "\n".join(lines))
    else:
        labels = {
            "new": "New (≤7d)", "engaged": "Engaged (posted this week)",
            "dormant": "Dormant (>30d, never posted)",
            "atrisk": "At risk (active then went quiet)",
            "churned": "Churned (left after posting)",
        }
        lines = ["<b>Member segments</b>"]
        for key, label in labels.items():
            lines.append(f"{label}: <b>{len(segs[key])}</b>")
        lines.append("\nUse /segment new|engaged|dormant|atrisk|churned to list members")
        tg.send_message(chat_id, "\n".join(lines))


def cmd_export(state, chat_id, message, args):
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
                day, d.get("members_eod", ""), d.get("joins", 0), d.get("leaves", 0),
                d.get("messages", 0), d.get("unique_posters", ""),
                d.get("top5_messages", ""), d.get("replies", ""),
            ])
    tg.send_document(chat_id, path, caption=f"Export: last {days} days")
    os.remove(path)


def cmd_cohorts(state, chat_id, message, args):
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

    tg.send_message(chat_id, f"<b>Activation funnel (last {weeks}w)</b>\n"
                    f"Joined: {joined}\n"
                    f"Clicked welcome: {clicked} ({pct(clicked)})\n"
                    f"Sent first message: {first} ({pct(first)})\n"
                    f"Sent 3rd message: {third} ({pct(third)})")


def cmd_distinct(state, chat_id, message, args):
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
