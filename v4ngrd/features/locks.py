from .. import storage, tg, util


def _message_content_type(message):
    if message.get("sticker"):
        return "sticker"
    if message.get("animation"):
        return "gif"
    if message.get("document"):
        return "document"
    if message.get("video"):
        return "video"
    if message.get("photo"):
        return "photo"
    if message.get("audio"):
        return "audio"
    if message.get("voice"):
        return "voice"
    if message.get("poll"):
        return "poll"
    if message.get("forward_origin") or message.get("forward_from"):
        return "forward"
    text = message.get("text") or message.get("caption") or ""
    entities = (message.get("entities") or []) + (message.get("caption_entities") or [])
    if any(e.get("type") in ("url", "text_link") for e in entities):
        return "link"
    if "http://" in text or "https://" in text or "t.me/" in text:
        return "link"
    return None


def check(state, chat_id, message):
    actor = message["from"]
    if tg.is_admin(chat_id, actor["id"]):
        return False

    group = storage.get_group(state, chat_id)
    content_type = _message_content_type(message)
    if not content_type:
        return False

    if not group["settings"]["locks"].get(content_type):
        return False

    tg.delete_message(chat_id, message["message_id"])
    storage.append_event(chat_id, "lock_delete", user_id=actor["id"], meta={"content_type": content_type})
    display = util.display_name(actor)
    tg.send_message(chat_id, f"{util.mention(actor['id'], display)}, {content_type}s are locked here.")
    return True
