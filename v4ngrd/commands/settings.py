from .. import storage, tg, util
from .. import config

_VALID_SLOW_DELAYS = [0, 10, 30, 60, 300, 900, 3600, 21600, 86400]


def _require_admin(message, chat_id):
    return tg.is_admin(chat_id, message["from"]["id"])


def cmd_setwelcome(state, chat_id, message, args):
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    text = message["text"].split(maxsplit=1)
    if len(text) < 2:
        return tg.send_message(chat_id, "Usage: /setwelcome <message> (vars: {first_name} {username} {group} {count})")
    group = storage.get_group(state, chat_id)
    group["settings"]["welcome_message"] = text[1]
    tg.send_message(chat_id, "Welcome message updated.")


def cmd_setgoodbye(state, chat_id, message, args):
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    text = message["text"].split(maxsplit=1)
    if len(text) < 2:
        return tg.send_message(chat_id, "Usage: /setgoodbye <message>")
    group = storage.get_group(state, chat_id)
    group["settings"]["goodbye_message"] = text[1]
    tg.send_message(chat_id, "Goodbye message updated.")


def cmd_lock(state, chat_id, message, args):
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    if not args or args[0] not in config.CONTENT_LOCK_TYPES:
        return tg.send_message(chat_id, f"Usage: /lock <{'|'.join(config.CONTENT_LOCK_TYPES)}>")
    group = storage.get_group(state, chat_id)
    group["settings"]["locks"][args[0]] = True
    tg.send_message(chat_id, f"Locked: {args[0]}")


def cmd_unlock(state, chat_id, message, args):
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    if not args or args[0] not in config.CONTENT_LOCK_TYPES:
        return tg.send_message(chat_id, f"Usage: /unlock <{'|'.join(config.CONTENT_LOCK_TYPES)}>")
    group = storage.get_group(state, chat_id)
    group["settings"]["locks"][args[0]] = False
    tg.send_message(chat_id, f"Unlocked: {args[0]}")


def cmd_locks(state, chat_id, message, args):
    group = storage.get_group(state, chat_id)
    locks = group["settings"]["locks"]
    lines = [f"{'🔒' if v else '🔓'} {k}" for k, v in locks.items()]
    tg.send_message(chat_id, "<b>Content locks</b>\n" + "\n".join(lines))


def cmd_addblacklist(state, chat_id, message, args):
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    if not args:
        return tg.send_message(chat_id, "Usage: /addblacklist <word>")
    group = storage.get_group(state, chat_id)
    word = " ".join(args).lower()
    if word not in group["settings"]["blacklist_words"]:
        group["settings"]["blacklist_words"].append(word)
    tg.send_message(chat_id, f"Added '{util.escape_html(word)}' to the blacklist.")


def cmd_rmblacklist(state, chat_id, message, args):
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    if not args:
        return tg.send_message(chat_id, "Usage: /rmblacklist <word>")
    group = storage.get_group(state, chat_id)
    word = " ".join(args).lower()
    if word in group["settings"]["blacklist_words"]:
        group["settings"]["blacklist_words"].remove(word)
        tg.send_message(chat_id, f"Removed '{util.escape_html(word)}' from the blacklist.")
    else:
        tg.send_message(chat_id, "That word isn't blacklisted.")


def cmd_blacklist(state, chat_id, message, args):
    group = storage.get_group(state, chat_id)
    words = group["settings"]["blacklist_words"]
    if not words:
        return tg.send_message(chat_id, "Blacklist is empty.")
    tg.send_message(chat_id, "<b>Blacklisted words</b>\n" + "\n".join(util.escape_html(w) for w in words))


def cmd_setflood(state, chat_id, message, args):
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    if len(args) < 2 or not args[0].isdigit() or not args[1].isdigit():
        return tg.send_message(chat_id, "Usage: /setflood <msg_limit> <window_sec> [ban|kick|mute]")
    group = storage.get_group(state, chat_id)
    group["settings"]["antiflood"]["limit"] = int(args[0])
    group["settings"]["antiflood"]["window_sec"] = int(args[1])
    if len(args) > 2 and args[2] in ("ban", "kick", "mute"):
        group["settings"]["antiflood"]["action"] = args[2]
    flood = group["settings"]["antiflood"]
    tg.send_message(chat_id, f"Antiflood: {flood['limit']} msgs / {flood['window_sec']}s -> {flood['action']}")


def cmd_setwarnlimit(state, chat_id, message, args):
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    if not args or not args[0].isdigit():
        return tg.send_message(chat_id, "Usage: /setwarnlimit <n>")
    group = storage.get_group(state, chat_id)
    group["settings"]["warn_limit"] = int(args[0])
    tg.send_message(chat_id, f"Warn limit set to {args[0]}.")


def cmd_setwarnaction(state, chat_id, message, args):
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    if not args or args[0] not in ("ban", "kick", "mute"):
        return tg.send_message(chat_id, "Usage: /setwarnaction <ban|kick|mute>")
    group = storage.get_group(state, chat_id)
    group["settings"]["warn_action"] = args[0]
    tg.send_message(chat_id, f"Warn limit action set to {args[0]}.")


def cmd_setwarnexpiry(state, chat_id, message, args):
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    if not args or not args[0].isdigit():
        return tg.send_message(chat_id, "Usage: /setwarnexpiry <days> (0 = never expire)")
    group = storage.get_group(state, chat_id)
    days = int(args[0])
    group["settings"]["warn_expiry_days"] = days
    tg.send_message(chat_id, f"Warns expire after {days} days." if days else "Warn expiry disabled.")


def cmd_setlog(state, chat_id, message, args):
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    if not args or not args[0].lstrip("-").isdigit():
        return tg.send_message(chat_id, "Usage: /setlog <channel_id> (bot must be admin there)")
    group = storage.get_group(state, chat_id)
    group["settings"]["log_channel_id"] = int(args[0])
    tg.send_message(chat_id, "Log channel set.")
    tg.send_message(int(args[0]), f"This channel is now the mod-log for {group.get('title') or chat_id}.")


def cmd_captcha(state, chat_id, message, args):
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    if not args or args[0] not in ("on", "off"):
        return tg.send_message(chat_id, "Usage: /captcha <on|off>")
    group = storage.get_group(state, chat_id)
    group["settings"]["captcha_enabled"] = (args[0] == "on")
    tg.send_message(chat_id, f"Captcha verification turned {args[0]}.")


def cmd_slowmode(state, chat_id, message, args):
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    if not args:
        return tg.send_message(chat_id, "Usage: /slowmode <seconds|off>\nValid: 0 10 30 60 300 900 3600 21600 86400")
    raw = args[0].lower()
    if raw in ("off", "0"):
        delay = 0
    elif raw.isdigit():
        delay = min(_VALID_SLOW_DELAYS, key=lambda x: abs(x - int(raw)))
    else:
        return tg.send_message(chat_id, "Usage: /slowmode <seconds|off>")
    tg.set_slow_mode(chat_id, delay)
    tg.send_message(chat_id, "Slow mode disabled." if delay == 0 else f"Slow mode set to {delay}s.")


def cmd_setdrip(state, chat_id, message, args):
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    if not args or args[0] not in ("on", "off"):
        return tg.send_message(chat_id, "Usage: /setdrip <on|off>")
    group = storage.get_group(state, chat_id)
    group["settings"]["drip_enabled"] = (args[0] == "on")
    tg.send_message(chat_id, f"Onboarding drip turned {args[0]}.")
