from .. import storage, tg, util


def _require_admin(message, chat_id):
    return tg.is_admin(chat_id, message["from"]["id"])


def cmd_filter(state, chat_id, message, args):
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    text = message["text"].split(maxsplit=2)
    if len(text) < 3:
        return tg.send_message(chat_id, "Usage: /filter <keyword> <reply text>")
    keyword, reply_text = text[1].lower(), text[2]
    group = storage.get_group(state, chat_id)
    group["filters"][keyword] = reply_text
    tg.send_message(chat_id, f"Filter added: '{util.escape_html(keyword)}'.")


def cmd_stop(state, chat_id, message, args):
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    if not args:
        return tg.send_message(chat_id, "Usage: /stop <keyword>")
    keyword = " ".join(args).lower()
    group = storage.get_group(state, chat_id)
    if keyword in group["filters"]:
        del group["filters"][keyword]
        tg.send_message(chat_id, f"Filter removed: '{util.escape_html(keyword)}'.")
    else:
        tg.send_message(chat_id, "No such filter.")


def cmd_filters(state, chat_id, message, args):
    group = storage.get_group(state, chat_id)
    if not group["filters"]:
        return tg.send_message(chat_id, "No filters set.")
    lines = [util.escape_html(k) for k in group["filters"]]
    tg.send_message(chat_id, "<b>Filters</b>\n" + "\n".join(lines))
