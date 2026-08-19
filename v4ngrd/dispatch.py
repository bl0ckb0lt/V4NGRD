import sys
import traceback

from . import storage, tg, util
from .analytics import core, community
from .features import antiflood, blacklist, locks, welcome, captcha, karma
from .features import filters as msg_filters
from .commands import moderation, settings, notes, federation, analytics_cmds
from .commands import filters as cmd_filters
from .commands import karma as cmd_karma

COMMANDS = {
    "ban": moderation.cmd_ban,
    "unban": moderation.cmd_unban,
    "kick": moderation.cmd_kick,
    "mute": moderation.cmd_mute,
    "unmute": moderation.cmd_unmute,
    "warn": moderation.cmd_warn,
    "unwarn": moderation.cmd_unwarn,
    "warns": moderation.cmd_warns,

    "setwelcome": settings.cmd_setwelcome,
    "setgoodbye": settings.cmd_setgoodbye,
    "lock": settings.cmd_lock,
    "unlock": settings.cmd_unlock,
    "locks": settings.cmd_locks,
    "addblacklist": settings.cmd_addblacklist,
    "rmblacklist": settings.cmd_rmblacklist,
    "blacklist": settings.cmd_blacklist,
    "setflood": settings.cmd_setflood,
    "setwarnlimit": settings.cmd_setwarnlimit,
    "setwarnaction": settings.cmd_setwarnaction,
    "setlog": settings.cmd_setlog,
    "captcha": settings.cmd_captcha,

    "filter": cmd_filters.cmd_filter,
    "stop": cmd_filters.cmd_stop,
    "filters": cmd_filters.cmd_filters,

    "save": notes.cmd_save,
    "get": notes.cmd_get,
    "notes": notes.cmd_notes,
    "clear": notes.cmd_clear,

    "newfed": federation.cmd_newfed,
    "joinfed": federation.cmd_joinfed,
    "leavefed": federation.cmd_leavefed,
    "fban": federation.cmd_fban,
    "unfban": federation.cmd_unfban,
    "fedinfo": federation.cmd_fedinfo,

    "stats": analytics_cmds.cmd_stats,
    "activity": analytics_cmds.cmd_activity,
    "top": analytics_cmds.cmd_top,
    "modlog": analytics_cmds.cmd_modlog,
    "digestnow": analytics_cmds.cmd_digestnow,
    "insights": analytics_cmds.cmd_insights,
    "churnrisk": analytics_cmds.cmd_churnrisk,

    # Community analytics commands (replace legacy export/cohorts)
    "export": community.cmd_export,
    "cohorts": community.cmd_cohorts,
    "funnel": community.cmd_funnel,
    "distinct": community.cmd_distinct,

    "rep": cmd_karma.cmd_rep,
    "topkarma": cmd_karma.cmd_topkarma,
}


def handle_message(state, message):
    chat = message.get("chat", {})
    if chat.get("type") not in ("group", "supergroup"):
        return
    chat_id = chat["id"]
    group = storage.get_group(state, chat_id)
    group["title"] = chat.get("title", group.get("title", ""))

    if "new_chat_members" in message:
        for new_member in message["new_chat_members"]:
            if new_member.get("is_bot"):
                continue
            if federation.check_fban_on_join(state, chat_id, new_member["id"]):
                tg.ban_chat_member(chat_id, new_member["id"])
                storage.append_event(chat_id, "fban_autoban", user_id=new_member["id"])
                return
        welcome.handle_join(state, chat_id, message)
        return

    if "left_chat_member" in message:
        welcome.handle_leave(state, chat_id, message)
        return

    actor = message.get("from")
    if not actor or actor.get("is_bot"):
        return

    member = storage.get_member(group, actor["id"], defaults={
        "first_name": actor.get("first_name", ""), "username": actor.get("username", ""),
    })
    member["first_name"] = actor.get("first_name", "")
    member["username"] = actor.get("username", "")

    text = message.get("text") or ""
    if text.startswith("/"):
        command = text.split()[0].split("@")[0][1:].lower()
        handler = COMMANDS.get(command)
        if handler:
            handler(state, chat_id, message, util.command_args(text))
            return

    if notes.maybe_reply_note(state, chat_id, message):
        return
    if locks.check(state, chat_id, message):
        return
    if blacklist.check(state, chat_id, message):
        return
    if antiflood.check(state, chat_id, message):
        return

    msg_filters.check(state, chat_id, message)
    core.record_message_stat(group, member)
    karma.record_author(state, chat_id, message["message_id"], actor["id"])
    community.on_message_sent(state, chat_id, message)


def handle_update(state, update):
    if "message" in update:
        handle_message(state, update["message"])
    elif "callback_query" in update:
        cb = update["callback_query"]
        if not community.handle_welcome_callback(state, cb):
            captcha.handle_callback(state, cb)
    elif "message_reaction" in update:
        karma.handle_reaction(state, update["message_reaction"])


def process_updates(state):
    updates = tg.get_updates(state["last_update_id"] + 1)
    for update in updates:
        try:
            handle_update(state, update)
        except Exception:
            print(f"Error handling update {update.get('update_id')}:", file=sys.stderr)
            traceback.print_exc()
        finally:
            state["last_update_id"] = update["update_id"]
    return state
