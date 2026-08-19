import secrets
from datetime import datetime, timezone

from .. import storage, tg, util


def _require_admin(message, chat_id):
    return tg.is_admin(chat_id, message["from"]["id"])


def _parse_when(arg):
    """Parse relative (30m/2h/1d/1w) or absolute (YYYY-MM-DD HH:MM UTC) into a Unix timestamp."""
    now = storage.now_ts()
    if len(arg) >= 2 and arg[-1] in "mhdw" and arg[:-1].isdigit():
        n = int(arg[:-1])
        mult = {"m": 60, "h": 3600, "d": 86400, "w": 604800}[arg[-1]]
        return now + n * mult
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(arg, fmt).replace(tzinfo=timezone.utc)
            return int(dt.timestamp())
        except ValueError:
            continue
    return None


def cmd_schedule(state, chat_id, message, args):
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    if len(args) < 2:
        return tg.send_message(
            chat_id,
            "Usage: /schedule <when> <text>\n"
            "when: 30m 2h 1d 1w  or  YYYY-MM-DD HH:MM (UTC)\n"
            "Example: /schedule 2h Reminder: town hall tonight!",
        )
    when_str = args[0]
    ts = _parse_when(when_str)
    if ts is None:
        return tg.send_message(
            chat_id,
            f"Couldn't parse '{util.escape_html(when_str)}'. Use 30m/2h/1d or YYYY-MM-DD HH:MM.",
        )
    if ts <= storage.now_ts():
        return tg.send_message(chat_id, "That time is already in the past.")

    text = " ".join(args[1:])
    msg_id = secrets.token_hex(4)
    group = storage.get_group(state, chat_id)
    group.setdefault("scheduled_messages", []).append({
        "id": msg_id,
        "scheduled_ts": ts,
        "text": text,
        "scheduled_by": message["from"]["id"],
    })
    dt_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    tg.send_message(chat_id, f"Scheduled for {dt_str}. ID: <code>{msg_id}</code>")


def cmd_schedules(state, chat_id, message, args):
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    group = storage.get_group(state, chat_id)
    pending = sorted(group.get("scheduled_messages", []), key=lambda x: x["scheduled_ts"])
    if not pending:
        return tg.send_message(chat_id, "No scheduled messages.")
    lines = ["<b>Scheduled messages</b>"]
    for s in pending:
        dt_str = datetime.fromtimestamp(s["scheduled_ts"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        preview = util.escape_html(s["text"][:50]) + ("…" if len(s["text"]) > 50 else "")
        lines.append(f"<code>{s['id']}</code> @ {dt_str}\n  {preview}")
    tg.send_message(chat_id, "\n".join(lines))


def cmd_cancelschedule(state, chat_id, message, args):
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    if not args:
        return tg.send_message(chat_id, "Usage: /cancelschedule <id>")
    msg_id = args[0]
    group = storage.get_group(state, chat_id)
    before = len(group.get("scheduled_messages", []))
    group["scheduled_messages"] = [
        s for s in group.get("scheduled_messages", []) if s["id"] != msg_id
    ]
    if len(group["scheduled_messages"]) < before:
        tg.send_message(chat_id, f"Cancelled <code>{util.escape_html(msg_id)}</code>.")
    else:
        tg.send_message(chat_id, f"No scheduled message with ID <code>{util.escape_html(msg_id)}</code>.")


def sweep(state):
    """Send any scheduled messages that are now due. Called every poll cycle."""
    now = storage.now_ts()
    for cid, group in state["groups"].items():
        pending = group.get("scheduled_messages", [])
        if not pending:
            continue
        due = [s for s in pending if s["scheduled_ts"] <= now]
        if not due:
            continue
        group["scheduled_messages"] = [s for s in pending if s["scheduled_ts"] > now]
        for s in due:
            tg.try_call("sendMessage", {"chat_id": int(cid), "text": s["text"]})
