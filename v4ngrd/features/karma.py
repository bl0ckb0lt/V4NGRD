from .. import storage


def record_author(state, chat_id, message_id, user_id):
    group = storage.get_group(state, chat_id)
    authors = group.setdefault("recent_authors", {})
    authors[str(message_id)] = user_id
    if len(authors) > 1000:
        for key in list(authors.keys())[:-1000]:
            del authors[key]


def handle_reaction(state, update):
    chat_id = update["chat"]["id"]
    message_id = update["message_id"]
    reactor = update.get("user") or {}
    reactor_id = reactor.get("id")

    group = storage.get_group(state, chat_id)
    authors = group.get("recent_authors", {})
    author_id = authors.get(str(message_id))
    if not author_id or author_id == reactor_id:
        return False

    old_count = len(update.get("old_reaction") or [])
    new_count = len(update.get("new_reaction") or [])
    if new_count == old_count:
        return False

    member = storage.get_member(group, author_id)
    delta = 1 if new_count > old_count else -1
    member["rep"] += delta
    storage.append_event(chat_id, "karma_reaction", user_id=author_id, actor_id=reactor_id, meta={"delta": delta})
    return True
