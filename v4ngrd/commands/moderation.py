from .. import storage, tg, util, modlog


def _require_admin(message, chat_id):
    actor = message["from"]
    if not tg.is_admin(chat_id, actor["id"]):
        return False
    return True


def _resolve_target(state, chat_id, message, args):
    user_id, name, rest = util.extract_target(message, args)
    if user_id is None:
        return None, None, " ".join(rest) if rest else None
    group = storage.get_group(state, chat_id)
    member = group["members"].get(str(user_id))
    display = member["first_name"] if member else (name or str(user_id))
    reason = " ".join(rest) if rest else None
    return user_id, display, reason


def cmd_ban(state, chat_id, message, args):
    actor = message["from"]
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.", reply_to=message["message_id"])
    user_id, display, reason = _resolve_target(state, chat_id, message, args)
    if user_id is None:
        return tg.send_message(chat_id, "Reply to a user or give a user id to ban.", reply_to=message["message_id"])
    tg.ban_chat_member(chat_id, user_id)
    modlog.record(state, chat_id, "ban", user_id, display, actor["id"], util.display_name(actor), reason)
    tg.send_message(chat_id, f"Banned {util.mention(user_id, display)}.")


def cmd_unban(state, chat_id, message, args):
    actor = message["from"]
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.", reply_to=message["message_id"])
    user_id, display, reason = _resolve_target(state, chat_id, message, args)
    if user_id is None:
        return tg.send_message(chat_id, "Reply to a user or give a user id to unban.", reply_to=message["message_id"])
    tg.unban_chat_member(chat_id, user_id)
    modlog.record(state, chat_id, "unban", user_id, display, actor["id"], util.display_name(actor), reason)
    tg.send_message(chat_id, f"Unbanned {util.mention(user_id, display)}.")


def cmd_kick(state, chat_id, message, args):
    actor = message["from"]
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.", reply_to=message["message_id"])
    user_id, display, reason = _resolve_target(state, chat_id, message, args)
    if user_id is None:
        return tg.send_message(chat_id, "Reply to a user or give a user id to kick.", reply_to=message["message_id"])
    tg.ban_chat_member(chat_id, user_id)
    tg.unban_chat_member(chat_id, user_id)
    modlog.record(state, chat_id, "kick", user_id, display, actor["id"], util.display_name(actor), reason)
    tg.send_message(chat_id, f"Kicked {util.mention(user_id, display)}.")


def cmd_mute(state, chat_id, message, args):
    actor = message["from"]
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.", reply_to=message["message_id"])
    user_id, display, rest = util.extract_target(message, args)
    if user_id is None:
        return tg.send_message(chat_id, "Reply to a user or give a user id to mute.", reply_to=message["message_id"])

    until_date = None
    reason = None
    if rest:
        duration = util.parse_duration(rest[0])
        if duration:
            until_date = storage.now_ts() + duration
            reason = " ".join(rest[1:]) or None
        else:
            reason = " ".join(rest)

    tg.mute_chat_member(chat_id, user_id, until_date)
    group = storage.get_group(state, chat_id)
    member = storage.get_member(group, user_id)
    member["muted_until"] = until_date
    modlog.record(state, chat_id, "mute", user_id, display, actor["id"], util.display_name(actor), reason)
    suffix = f" until <{rest[0]}> elapses" if until_date else " indefinitely"
    tg.send_message(chat_id, f"Muted {util.mention(user_id, display)}{suffix}.")


def cmd_unmute(state, chat_id, message, args):
    actor = message["from"]
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.", reply_to=message["message_id"])
    user_id, display, reason = _resolve_target(state, chat_id, message, args)
    if user_id is None:
        return tg.send_message(chat_id, "Reply to a user or give a user id to unmute.", reply_to=message["message_id"])
    tg.unmute_chat_member(chat_id, user_id)
    group = storage.get_group(state, chat_id)
    member = storage.get_member(group, user_id)
    member["muted_until"] = None
    modlog.record(state, chat_id, "unmute", user_id, display, actor["id"], util.display_name(actor), reason)
    tg.send_message(chat_id, f"Unmuted {util.mention(user_id, display)}.")


def _apply_warn_limit_action(state, chat_id, user_id, display, actor):
    group = storage.get_group(state, chat_id)
    action = group["settings"]["warn_action"]
    if action == "ban":
        tg.ban_chat_member(chat_id, user_id)
    elif action == "kick":
        tg.ban_chat_member(chat_id, user_id)
        tg.unban_chat_member(chat_id, user_id)
    elif action == "mute":
        tg.mute_chat_member(chat_id, user_id)
    modlog.record(state, chat_id, f"warn_limit_{action}", user_id, display,
                  actor["id"], util.display_name(actor), "warn limit reached")
    tg.send_message(chat_id, f"{util.mention(user_id, display)} hit the warn limit and was {action}ned.")


def cmd_warn(state, chat_id, message, args):
    actor = message["from"]
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.", reply_to=message["message_id"])
    user_id, display, reason = _resolve_target(state, chat_id, message, args)
    if user_id is None:
        return tg.send_message(chat_id, "Reply to a user or give a user id to warn.", reply_to=message["message_id"])

    group = storage.get_group(state, chat_id)
    member = storage.get_member(group, user_id)
    member["warns"] += 1
    member.setdefault("warn_times", []).append(storage.now_ts())
    modlog.record(state, chat_id, "warn", user_id, display, actor["id"], util.display_name(actor), reason)

    limit = group["settings"]["warn_limit"]
    if member["warns"] >= limit:
        member["warns"] = 0
        member["warn_times"] = []
        _apply_warn_limit_action(state, chat_id, user_id, display, actor)
    else:
        tg.send_message(chat_id, f"Warned {util.mention(user_id, display)} ({member['warns']}/{limit}).")


def cmd_unwarn(state, chat_id, message, args):
    actor = message["from"]
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.", reply_to=message["message_id"])
    user_id, display, reason = _resolve_target(state, chat_id, message, args)
    if user_id is None:
        return tg.send_message(chat_id, "Reply to a user to remove a warn.", reply_to=message["message_id"])
    group = storage.get_group(state, chat_id)
    member = storage.get_member(group, user_id)
    member["warns"] = max(0, member["warns"] - 1)
    times = member.get("warn_times", [])
    if times:
        member["warn_times"] = times[:-1]
    modlog.record(state, chat_id, "unwarn", user_id, display, actor["id"], util.display_name(actor), reason)
    tg.send_message(chat_id, f"Removed a warn from {util.mention(user_id, display)} ({member['warns']} remaining).")


def cmd_warns(state, chat_id, message, args):
    user_id, display, _ = util.extract_target(message, args)
    if user_id is None:
        user_id = message["from"]["id"]
        display = util.display_name(message["from"])
    group = storage.get_group(state, chat_id)
    member = storage.get_member(group, user_id)
    limit = group["settings"]["warn_limit"]
    tg.send_message(chat_id, f"{util.mention(user_id, display)} has {member['warns']}/{limit} warns.")
