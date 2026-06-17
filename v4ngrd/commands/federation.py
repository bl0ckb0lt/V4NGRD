import time

from .. import storage, tg, util


def _require_admin(message, chat_id):
    return tg.is_admin(chat_id, message["from"]["id"])


def _gen_fed_id(owner_id):
    return f"fed{owner_id}{int(time.time())}"


def cmd_newfed(state, chat_id, message, args):
    actor = message["from"]
    if not args:
        return tg.send_message(chat_id, "Usage: /newfed <name>")
    name = " ".join(args)
    fed_data = storage.load_federations()
    fed_id = _gen_fed_id(actor["id"])
    fed_data["federations"][fed_id] = {
        "name": name, "owner_id": actor["id"], "groups": [], "bans": {},
    }
    storage.save_federations(fed_data)
    tg.send_message(chat_id, f"Federation '{util.escape_html(name)}' created.\nID: <code>{fed_id}</code>\nJoin groups with /joinfed {fed_id}")


def cmd_joinfed(state, chat_id, message, args):
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    if not args:
        return tg.send_message(chat_id, "Usage: /joinfed <fed_id>")
    fed_id = args[0]
    fed_data = storage.load_federations()
    fed = fed_data["federations"].get(fed_id)
    if not fed:
        return tg.send_message(chat_id, "No such federation.")
    if str(chat_id) not in fed["groups"]:
        fed["groups"].append(str(chat_id))
    storage.save_federations(fed_data)
    group = storage.get_group(state, chat_id)
    group["settings"]["federation_id"] = fed_id

    banned_here = 0
    for user_id in fed["bans"]:
        tg.ban_chat_member(chat_id, int(user_id))
        banned_here += 1
    tg.send_message(chat_id, f"Joined federation '{util.escape_html(fed['name'])}'. Synced {banned_here} fban(s).")


def cmd_leavefed(state, chat_id, message, args):
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    group = storage.get_group(state, chat_id)
    fed_id = group["settings"].get("federation_id")
    if not fed_id:
        return tg.send_message(chat_id, "This group is not in a federation.")
    fed_data = storage.load_federations()
    fed = fed_data["federations"].get(fed_id)
    if fed and str(chat_id) in fed["groups"]:
        fed["groups"].remove(str(chat_id))
        storage.save_federations(fed_data)
    group["settings"]["federation_id"] = None
    tg.send_message(chat_id, "Left the federation.")


def cmd_fban(state, chat_id, message, args):
    actor = message["from"]
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    group = storage.get_group(state, chat_id)
    fed_id = group["settings"].get("federation_id")
    if not fed_id:
        return tg.send_message(chat_id, "This group is not in a federation.")

    user_id, display, reason = util.extract_target(message, args)
    if user_id is None:
        return tg.send_message(chat_id, "Reply to a user or give a user id to fban.")
    reason = reason or "no reason given"

    fed_data = storage.load_federations()
    fed = fed_data["federations"].get(fed_id)
    fed["bans"][str(user_id)] = {"reason": reason, "by": actor["id"], "ts": storage.now_ts(), "name": display}
    storage.save_federations(fed_data)

    affected = 0
    for gid in fed["groups"]:
        tg.ban_chat_member(int(gid), user_id)
        affected += 1
    storage.append_event(chat_id, "fban", user_id=user_id, actor_id=actor["id"], reason=reason,
                          meta={"fed_id": fed_id, "groups_affected": affected})
    tg.send_message(chat_id, f"Fbanned {util.mention(user_id, display)} across {affected} group(s) in '{fed['name']}'.")


def cmd_unfban(state, chat_id, message, args):
    actor = message["from"]
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    group = storage.get_group(state, chat_id)
    fed_id = group["settings"].get("federation_id")
    if not fed_id:
        return tg.send_message(chat_id, "This group is not in a federation.")

    user_id, display, _ = util.extract_target(message, args)
    if user_id is None:
        return tg.send_message(chat_id, "Reply to a user or give a user id to unfban.")

    fed_data = storage.load_federations()
    fed = fed_data["federations"].get(fed_id)
    fed["bans"].pop(str(user_id), None)
    storage.save_federations(fed_data)

    affected = 0
    for gid in fed["groups"]:
        tg.unban_chat_member(int(gid), user_id)
        affected += 1
    storage.append_event(chat_id, "unfban", user_id=user_id, actor_id=actor["id"],
                          meta={"fed_id": fed_id, "groups_affected": affected})
    tg.send_message(chat_id, f"Unfbanned {util.mention(user_id, display)} across {affected} group(s).")


def cmd_fedinfo(state, chat_id, message, args):
    group = storage.get_group(state, chat_id)
    fed_id = group["settings"].get("federation_id")
    if not fed_id:
        return tg.send_message(chat_id, "This group is not in a federation.")
    fed_data = storage.load_federations()
    fed = fed_data["federations"].get(fed_id)
    if not fed:
        return tg.send_message(chat_id, "Federation data missing.")
    tg.send_message(chat_id,
        f"<b>{util.escape_html(fed['name'])}</b>\n"
        f"ID: <code>{fed_id}</code>\n"
        f"Groups: {len(fed['groups'])}\n"
        f"Federated bans: {len(fed['bans'])}")


def check_fban_on_join(state, chat_id, user_id):
    """Returns True if the joining user is fbanned in this group's federation."""
    group = storage.get_group(state, chat_id)
    fed_id = group["settings"].get("federation_id")
    if not fed_id:
        return False
    fed_data = storage.load_federations()
    fed = fed_data["federations"].get(fed_id)
    if not fed:
        return False
    return str(user_id) in fed["bans"]
