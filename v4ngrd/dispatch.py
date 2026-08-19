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
    "setwarnexpiry": settings.cmd_setwarnexpiry,
    "setlog": settings.cmd_setlog,
    "captcha": settings.cmd_captcha,
    "slowmode": settings.cmd_slowmode,
    "setdrip": settings.cmd_setdrip,

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

    "export": community.cmd_export,
    "cohorts": community.cmd_cohorts,
    "funnel": community.cmd_funnel,
    "distinct": community.cmd_distinct,
    "health": community.cmd_health,
    "activation": community.cmd_activation,
    "segment": community.cmd_segment,

    "rep": cmd_karma.cmd_rep,
    "topkarma": cmd_karma.cmd_topkarma,
}

_HELP_TEXT = (
    "<b>V4NGRD — Group Manager</b>\n\n"
    "Add me to a group and make me an admin to get started.\n\n"
    "<b>Moderation</b>\n"
    "/ban /unban /kick /mute /unmute /warn /unwarn /warns\n\n"
    "<b>Settings</b>\n"
    "/setwelcome /setgoodbye /lock /unlock /locks\n"
    "/addblacklist /rmblacklist /blacklist\n"
    "/setflood /setwarnlimit /setwarnaction /setwarnexpiry\n"
    "/setlog /captcha /slowmode /setdrip\n\n"
    "<b>Notes &amp; Filters</b>\n"
    "/save /get /notes /clear /filter /stop /filters\n\n"
    "<b>Analytics (admin only)</b>\n"
    "/stats /activity /top /modlog /insights /churnrisk\n"
    "/health /activation /segment [type]\n"
    "/export [days] /cohorts /funnel [weeks] /distinct [days]\n"
    "/digestnow [daily|weekly]\n\n"
    "<b>Federations</b>\n"
    "/newfed /joinfed /leavefed /fban /unfban /fedinfo\n\n"
    "<b>Karma</b>\n"
    "/rep /topkarma"
)


def handle_private(message):
    text = message.get("text") or ""
    chat_id = message["chat"]["id"]
    if text.startswith("/start") or text.startswith("/help"):
        tg.send_message(chat_id, _HELP_TEXT)


def handle_message(state, message):
    chat = message.get("chat", {})
    chat_type = chat.get("type")

    if chat_type == "private":
        handle_private(message)
        return

    if chat_type not in ("group", "supergroup"):
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
    elif "chat_member" in update:
        community.handle_chat_member(state, update["chat_member"])


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
