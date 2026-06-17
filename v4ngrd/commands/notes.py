from .. import storage, tg, util


def _require_admin(message, chat_id):
    return tg.is_admin(chat_id, message["from"]["id"])


def cmd_save(state, chat_id, message, args):
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    text = message["text"].split(maxsplit=2)
    if len(text) < 2:
        return tg.send_message(chat_id, "Usage: /save <name> <content> (or reply to a message with /save <name>)")
    name = text[1].lower()
    content = text[2] if len(text) > 2 else None

    reply = message.get("reply_to_message")
    if content is None and reply:
        content = reply.get("text") or reply.get("caption") or ""
    if not content:
        return tg.send_message(chat_id, "Nothing to save.")

    group = storage.get_group(state, chat_id)
    group["notes"][name] = content
    tg.send_message(chat_id, f"Saved note '{util.escape_html(name)}'. Get it with /get {name} or #{name}.")


def cmd_get(state, chat_id, message, args):
    if not args:
        return tg.send_message(chat_id, "Usage: /get <name>")
    name = args[0].lower()
    group = storage.get_group(state, chat_id)
    note = group["notes"].get(name)
    if not note:
        return tg.send_message(chat_id, "No such note.")
    tg.send_message(chat_id, note)


def cmd_notes(state, chat_id, message, args):
    group = storage.get_group(state, chat_id)
    if not group["notes"]:
        return tg.send_message(chat_id, "No notes saved.")
    lines = [f"#{util.escape_html(n)}" for n in group["notes"]]
    tg.send_message(chat_id, "<b>Notes</b>\n" + "\n".join(lines))


def cmd_clear(state, chat_id, message, args):
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    if not args:
        return tg.send_message(chat_id, "Usage: /clear <name>")
    name = args[0].lower()
    group = storage.get_group(state, chat_id)
    if name in group["notes"]:
        del group["notes"][name]
        tg.send_message(chat_id, f"Deleted note '{util.escape_html(name)}'.")
    else:
        tg.send_message(chat_id, "No such note.")


def maybe_reply_note(state, chat_id, message):
    """Handle plain-text '#notename' shortcuts."""
    text = message.get("text") or ""
    if not text.startswith("#") or " " in text:
        return False
    name = text[1:].lower().strip()
    if not name:
        return False
    group = storage.get_group(state, chat_id)
    note = group["notes"].get(name)
    if note:
        tg.send_message(chat_id, note, reply_to=message["message_id"])
        return True
    return False
