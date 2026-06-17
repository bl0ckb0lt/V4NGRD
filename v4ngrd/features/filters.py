from .. import storage, tg


def check(state, chat_id, message):
    text = (message.get("text") or message.get("caption") or "").lower()
    if not text:
        return False

    group = storage.get_group(state, chat_id)
    for keyword, reply_text in group["filters"].items():
        if keyword in text:
            tg.send_message(chat_id, reply_text, reply_to=message["message_id"])
            return True
    return False
