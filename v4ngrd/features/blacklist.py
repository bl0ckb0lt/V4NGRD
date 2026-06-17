from .. import storage, tg, util, modlog


def check(state, chat_id, message):
    text = (message.get("text") or message.get("caption") or "").lower()
    if not text:
        return False

    actor = message["from"]
    if tg.is_admin(chat_id, actor["id"]):
        return False

    group = storage.get_group(state, chat_id)
    words = group["settings"]["blacklist_words"]
    hit = next((w for w in words if w in text), None)
    if not hit:
        return False

    tg.delete_message(chat_id, message["message_id"])
    member = storage.get_member(group, actor["id"])
    member["warns"] += 1
    display = util.display_name(actor)

    storage.append_event(chat_id, "blacklist_hit", user_id=actor["id"], meta={"word": hit})

    limit = group["settings"]["warn_limit"]
    if member["warns"] >= limit:
        member["warns"] = 0
        action = group["settings"]["warn_action"]
        if action == "ban":
            tg.ban_chat_member(chat_id, actor["id"])
        elif action == "kick":
            tg.ban_chat_member(chat_id, actor["id"])
            tg.unban_chat_member(chat_id, actor["id"])
        elif action == "mute":
            tg.mute_chat_member(chat_id, actor["id"])
        modlog.record(state, chat_id, f"blacklist_{action}", actor["id"], display, reason=f"blacklisted word: {hit}")
        tg.send_message(chat_id, f"{util.mention(actor['id'], display)} hit the warn limit (blacklist) and was {action}ned.")
    else:
        modlog.record(state, chat_id, "blacklist_warn", actor["id"], display, reason=f"blacklisted word: {hit}")
        tg.send_message(chat_id, f"{util.mention(actor['id'], display)}, that word isn't allowed here. ({member['warns']}/{limit})")
    return True
