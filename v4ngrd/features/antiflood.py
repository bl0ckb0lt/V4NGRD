from .. import storage, tg, util, modlog


def check(state, chat_id, message):
    """Track message timestamps per user and apply the configured antiflood action."""
    actor = message["from"]
    if actor.get("is_bot"):
        return False

    group = storage.get_group(state, chat_id)
    if tg.is_admin(chat_id, actor["id"]):
        return False

    flood_cfg = group["settings"]["antiflood"]
    member = storage.get_member(group, actor["id"])
    now = storage.now_ts()

    recent = member.get("recent_msgs", [])
    recent.append(now)
    window_start = now - flood_cfg["window_sec"]
    recent = [t for t in recent if t >= window_start]
    member["recent_msgs"] = recent

    if len(recent) < flood_cfg["limit"]:
        return False

    member["recent_msgs"] = []
    action = flood_cfg["action"]
    display = util.display_name(actor)

    if action == "ban":
        tg.ban_chat_member(chat_id, actor["id"])
    elif action == "kick":
        tg.ban_chat_member(chat_id, actor["id"])
        tg.unban_chat_member(chat_id, actor["id"])
    elif action == "mute":
        tg.mute_chat_member(chat_id, actor["id"])
        member["muted_until"] = None

    storage.append_event(chat_id, "flood_trigger", user_id=actor["id"],
                          meta={"action": action, "count": flood_cfg["limit"], "window_sec": flood_cfg["window_sec"]})
    modlog.record(state, chat_id, f"flood_{action}", actor["id"], display, reason="antiflood triggered")
    tg.send_message(chat_id, f"{util.mention(actor['id'], display)} was {action}ned for flooding.")
    return True
