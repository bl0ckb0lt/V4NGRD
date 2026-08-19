import sys
import traceback

from . import storage, tg, util
from .analytics import core, community
from .features import antiflood, blacklist, locks, welcome, captcha, karma, cas
from .features import filters as msg_filters
from .commands import moderation, settings, notes, federation, analytics_cmds
from .commands import filters as cmd_filters
from .commands import karma as cmd_karma
from .commands import schedule as schedule_cmd

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
    "cas": settings.cmd_cas,

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

    "schedule": schedule_cmd.cmd_schedule,
    "schedules": schedule_cmd.cmd_schedules,
    "cancelschedule": schedule_cmd.cmd_cancelschedule,

    "rep": cmd_karma.cmd_rep,
    "topkarma": cmd_karma.cmd_topkarma,
}

_WELCOME_TEXT = (
    "<b>V4NGRD — Premium Group Manager</b>\n\n"
    "Add me to a group and make me an admin to get started.\n\n"
    "Choose a category below to see all commands, "
    "or send /help &lt;command&gt; for details on any single command."
)

_MAIN_MENU_KEYBOARD = {"inline_keyboard": [
    [{"text": "🔨 Moderation",      "callback_data": "menu:mod"},
     {"text": "⚙️ Settings",        "callback_data": "menu:settings"}],
    [{"text": "📅 Scheduling",      "callback_data": "menu:schedule"},
     {"text": "📝 Notes & Filters", "callback_data": "menu:notes"}],
    [{"text": "📊 Analytics",       "callback_data": "menu:analytics"},
     {"text": "🔗 Federations",     "callback_data": "menu:federation"}],
    [{"text": "⭐ Karma",           "callback_data": "menu:karma"}],
]}

_BACK_KEYBOARD = {"inline_keyboard": [
    [{"text": "← Back to menu", "callback_data": "menu:main"}],
]}

_MENU_SECTIONS = {
    "mod": (
        "<b>🔨 Moderation</b>\n\n"
        "/ban — Permanently ban a user (reply or /ban @user)\n"
        "/unban — Lift a ban so the user can rejoin\n"
        "/kick — Remove a user (they can rejoin)\n"
        "/mute [@user] [1h/1d] — Silence a user\n"
        "/unmute — Restore a muted user's voice\n"
        "/warn — Issue a warning; auto-punish at the limit\n"
        "/unwarn — Remove the most recent warning\n"
        "/warns [@user] — Show a user's warning count"
    ),
    "settings": (
        "<b>⚙️ Settings</b>\n\n"
        "/setwelcome — Set the join message\n"
        "/setgoodbye — Set the leave message\n"
        "/lock /unlock &lt;type&gt; — Block content (photo/video/sticker/link…)\n"
        "/locks — List active content locks\n"
        "/addblacklist /rmblacklist — Add or remove a banned word\n"
        "/blacklist — View all banned words\n"
        "/setflood &lt;n&gt; [sec] — Auto-act after N messages in a window\n"
        "/setwarnlimit &lt;n&gt; — Warns before punishment (default 3)\n"
        "/setwarnaction &lt;ban|kick|mute&gt; — Punishment at warn limit\n"
        "/setwarnexpiry &lt;days&gt; — Warns expire after N days (0 = never)\n"
        "/setlog &lt;channel_id&gt; — Forward mod actions to a log channel\n"
        "/captcha &lt;on|off&gt; — Require join button click\n"
        "/slowmode &lt;off|10s|30s|1m|5m|15m|1h&gt; — Slow mode delay\n"
        "/setdrip &lt;on|off&gt; — DM new members at day 3 and day 7\n"
        "/cas &lt;on|off&gt; — Auto-ban CAS-flagged users on join"
    ),
    "schedule": (
        "<b>📅 Scheduled Messages</b>\n\n"
        "/schedule &lt;when&gt; &lt;text&gt; — Post a message later\n"
        "  <i>when:</i> 30m · 2h · 1d · 1w · or YYYY-MM-DD HH:MM\n\n"
        "/schedules — List all pending scheduled messages\n"
        "/cancelschedule &lt;id&gt; — Cancel a scheduled message"
    ),
    "notes": (
        "<b>📝 Notes &amp; Filters</b>\n\n"
        "/save &lt;name&gt; &lt;text&gt; — Save a note (reply to save that message)\n"
        "/get &lt;name&gt; — Post a saved note in chat\n"
        "/notes — List all saved notes\n"
        "/clear &lt;name&gt; — Delete a note\n\n"
        "/filter &lt;keyword&gt; &lt;reply&gt; — Auto-reply when keyword is sent\n"
        "/stop &lt;keyword&gt; — Remove an auto-reply filter\n"
        "/filters — List all active keyword filters"
    ),
    "analytics": (
        "<b>📊 Analytics</b> <i>(admin only)</i>\n\n"
        "/stats — Member count and activity summary\n"
        "/activity — Daily message chart (7 days)\n"
        "/top — Top 10 most active members\n"
        "/modlog — Recent moderation actions\n"
        "/insights — Churn risk and engagement signals\n"
        "/churnrisk — Members who went quiet after being active\n\n"
        "/health — Community health score (0–100)\n"
        "/activation — % of new members who posted within 24h/72h/7d\n"
        "/segment [type] — Members by activity segment\n"
        "/distinct [days] — Unique posters in last N days\n"
        "/export [days] — CSV of daily stats\n"
        "/cohorts — Join cohort retention CSV\n"
        "/funnel [weeks] — Activation funnel report\n"
        "/digestnow [daily|weekly] — Send digest immediately"
    ),
    "federation": (
        "<b>🔗 Federations</b>\n\n"
        "/newfed &lt;name&gt; — Create a ban federation\n"
        "/joinfed &lt;id&gt; — Join your group to a federation\n"
        "/leavefed — Leave the current federation\n"
        "/fban @user [reason] — Federation-ban across all member groups\n"
        "/unfban @user — Lift a federation ban\n"
        "/fedinfo — Show federation details and member groups"
    ),
    "karma": (
        "<b>⭐ Karma</b>\n\n"
        "/rep @user — Give +1 reputation to a member\n"
        "/topkarma — Leaderboard of top-reputation members"
    ),
}

_HELP_TEXT = (
    "<b>V4NGRD — Premium Group Manager</b>\n"
    "Add me to a group, make me admin, then use these commands:\n"
    "Send /help &lt;command&gt; for details on any command.\n\n"

    "<b>🔨 Moderation</b>\n"
    "/ban — Permanently ban a user (reply or /ban @user)\n"
    "/unban — Lift a ban\n"
    "/kick — Remove a user (they can rejoin)\n"
    "/mute — Silence a user (reply or /mute @user [1h/1d])\n"
    "/unmute — Restore a muted user's voice\n"
    "/warn — Issue a warning; auto-punish at the limit\n"
    "/unwarn — Remove the most recent warning\n"
    "/warns — Show a user's current warning count\n\n"

    "<b>⚙️ Group Settings</b>\n"
    "/setwelcome — Set the join message ({first_name}, {group}, {count})\n"
    "/setgoodbye — Set the leave message\n"
    "/lock /unlock — Block a content type (photo, video, sticker, link…)\n"
    "/locks — List all active content locks\n"
    "/addblacklist /rmblacklist — Add or remove a banned word/phrase\n"
    "/blacklist — View all banned words\n"
    "/setflood — Auto-action after N messages in a window (e.g. /setflood 5 10s)\n"
    "/setwarnlimit — How many warns before punishment (default 3)\n"
    "/setwarnaction — Punishment at warn limit: ban/kick/mute\n"
    "/setwarnexpiry — Warns expire after N days (0 = never)\n"
    "/setlog — Set a channel for mod-action logs\n"
    "/captcha — Toggle join captcha on/off\n"
    "/slowmode — Set slow mode delay (off/10s/30s/1m/5m/15m/1h)\n"
    "/setdrip — Enable onboarding DMs at day 3 and day 7 for new members\n"
    "/cas — Enable/disable CAS anti-spam auto-ban\n\n"

    "<b>📅 Scheduled Messages</b>\n"
    "/schedule &lt;when&gt; &lt;text&gt; — Post a message later\n"
    "  when: 30m · 2h · 1d · 1w · or YYYY-MM-DD HH:MM\n"
    "/schedules — List all pending scheduled messages\n"
    "/cancelschedule &lt;id&gt; — Cancel a scheduled message by ID\n\n"

    "<b>📝 Notes &amp; Auto-Replies</b>\n"
    "/save &lt;name&gt; &lt;text&gt; — Save a note (reply to a message to save it)\n"
    "/get &lt;name&gt; — Retrieve a saved note\n"
    "/notes — List all saved notes\n"
    "/clear &lt;name&gt; — Delete a note\n"
    "/filter &lt;keyword&gt; &lt;reply&gt; — Auto-reply when a keyword is sent\n"
    "/stop &lt;keyword&gt; — Remove an auto-reply filter\n"
    "/filters — List all active filters\n\n"

    "<b>📊 Analytics (admin only)</b>\n"
    "/stats — Member count, messages, and activity summary\n"
    "/activity — Daily message chart for the past 7 days\n"
    "/top — Top 10 most active members\n"
    "/modlog — Recent moderation actions\n"
    "/insights — Churn risk and engagement signals\n"
    "/churnrisk — Members who went quiet after being active\n"
    "/health — Community health score (0–100) with breakdown\n"
    "/activation — % of new members who posted within 24h/72h/7d\n"
    "/segment — Members grouped by activity: new/engaged/atrisk/dormant/churned\n"
    "/distinct [days] — Unique posters in the last N days (default 7)\n"
    "/export [days] — Download a CSV of daily stats\n"
    "/cohorts — CSV of weekly join cohorts vs activity at D7/D14/D30\n"
    "/funnel [weeks] — Activation funnel from join to first post\n"
    "/digestnow [daily|weekly] — Send the digest report immediately\n\n"

    "<b>🔗 Federations</b>\n"
    "/newfed &lt;name&gt; — Create a ban federation\n"
    "/joinfed &lt;id&gt; — Join your group to a federation\n"
    "/leavefed — Leave the current federation\n"
    "/fban @user — Federation-ban a user across all member groups\n"
    "/unfban @user — Lift a federation ban\n"
    "/fedinfo — Show federation details and member groups\n\n"

    "<b>⭐ Karma</b>\n"
    "/rep @user — Give reputation to a member\n"
    "/topkarma — Leaderboard of top-reputation members"
)

_COMMAND_HELP = {
    "ban": "/ban — Reply to a message or use /ban @username.\nPermanently removes the user and prevents them from rejoining.",
    "unban": "/unban @username or reply — Lifts a ban so the user can rejoin.",
    "kick": "/kick — Removes the user. Unlike /ban, they can come back by joining again.",
    "mute": "/mute [@user] [duration] — Silences a user.\nDuration examples: 1h, 2d, 30m. Omit for permanent mute.",
    "unmute": "/unmute — Reply to a muted user to restore their ability to send messages.",
    "warn": "/warn — Reply to a message to warn its author.\nAt the warn limit (set with /setwarnlimit), the configured action fires automatically.",
    "unwarn": "/unwarn — Reply to a user to remove their most recent warning.",
    "warns": "/warns [@user] — Shows how many warnings a user has and the current limit.",
    "setwelcome": "/setwelcome &lt;message&gt; — Sets the message sent when someone joins.\nVariables: {first_name} {last_name} {username} {group} {count}",
    "setgoodbye": "/setgoodbye &lt;message&gt; — Sets the message sent when someone leaves.\nSame variables as /setwelcome.",
    "lock": "/lock &lt;type&gt; — Block a content type for non-admins.\nTypes: photo video audio document sticker gif poll link forward voice",
    "unlock": "/unlock &lt;type&gt; — Remove a content lock.",
    "locks": "/locks — Lists every content type that is currently locked.",
    "addblacklist": "/addblacklist &lt;word or phrase&gt; — Any message containing this text is deleted automatically.",
    "rmblacklist": "/rmblacklist &lt;word&gt; — Removes a word from the blacklist.",
    "blacklist": "/blacklist — Shows all currently banned words/phrases.",
    "setflood": "/setflood &lt;count&gt; [window] — Auto-punish if a user sends count messages within window seconds.\nExample: /setflood 5 10",
    "setwarnlimit": "/setwarnlimit &lt;n&gt; — Set how many warnings trigger the punishment (default 3).",
    "setwarnaction": "/setwarnaction &lt;ban|kick|mute&gt; — What happens when the warn limit is reached.",
    "setwarnexpiry": "/setwarnexpiry &lt;days&gt; — Warnings older than this many days are ignored (0 = warnings never expire).",
    "setlog": "/setlog &lt;channel_id&gt; — Forward mod actions (ban, kick, warn, etc.) to this channel.",
    "captcha": "/captcha &lt;on|off&gt; — Require new members to click a button to prove they're human.",
    "slowmode": "/slowmode &lt;off|10s|30s|1m|5m|15m|1h&gt; — Sets how long members must wait between messages.",
    "setdrip": "/setdrip &lt;on|off&gt; — When on, the bot DMs new members who haven't posted yet at day 3 and day 7 with onboarding tips.",
    "cas": "/cas &lt;on|off&gt; — Combot Anti-Spam integration. Automatically bans users flagged in the CAS database the moment they join.",
    "schedule": "/schedule &lt;when&gt; &lt;message text&gt; — Schedule a message to be posted in this group.\nwhen examples: 30m · 2h · 1d · 1w · 2026-12-31 18:00",
    "schedules": "/schedules — Lists all messages waiting to be posted, with their IDs and scheduled times.",
    "cancelschedule": "/cancelschedule &lt;id&gt; — Cancels a scheduled message before it fires.",
    "save": "/save &lt;name&gt; [text] — Save a note. Reply to a message to save that message as the note.",
    "get": "/get &lt;name&gt; — Posts the saved note in the chat.",
    "notes": "/notes — Lists all saved note names.",
    "clear": "/clear &lt;name&gt; — Deletes a saved note.",
    "filter": "/filter &lt;keyword&gt; &lt;reply&gt; — When anyone sends a message containing keyword, the bot replies with reply.",
    "stop": "/stop &lt;keyword&gt; — Removes an auto-reply filter.",
    "filters": "/filters — Lists all active keyword filters.",
    "stats": "/stats — Shows member count, total messages, and a quick activity summary.",
    "activity": "/activity — Bar chart of daily message counts for the past 7 days.",
    "top": "/top — The 10 most active members by message count.",
    "modlog": "/modlog — Recent bans, kicks, mutes, and warns with dates.",
    "insights": "/insights — Highlights members at risk of churning and other engagement signals.",
    "churnrisk": "/churnrisk — Members who posted regularly but have gone quiet for 14+ days.",
    "health": "/health — A 0–100 community health score based on growth, activation, reply depth, and posting breadth.",
    "activation": "/activation — What % of members who joined in the last 30 days sent their first message within 24h, 72h, and 7 days.",
    "segment": "/segment [new|engaged|atrisk|dormant|churned] — Segment members by activity.\nnew: joined ≤7d · engaged: posted this week · atrisk: active then quiet 14+d · dormant: never posted >30d · churned: left after posting",
    "distinct": "/distinct [days] — Count of unique members who posted at least once in the last N days (default 7).",
    "export": "/export [days] — Sends a CSV file with daily stats (joins, leaves, messages, unique posters, replies). Default 30 days.",
    "cohorts": "/cohorts — CSV of weekly join cohorts showing how many members from each week were active at D7, D14, and D30.",
    "funnel": "/funnel [weeks] — Shows what % of new members reached each activation milestone (joined → first message → 3rd message).",
    "digestnow": "/digestnow [daily|weekly] — Immediately sends the activity digest report instead of waiting for the scheduled time.",
    "newfed": "/newfed &lt;name&gt; — Creates a new ban federation with you as the owner. Share the federation ID with other group admins.",
    "joinfed": "/joinfed &lt;federation_id&gt; — Links this group to a federation so federation bans apply here.",
    "leavefed": "/leavefed — Disconnects this group from the federation.",
    "fban": "/fban @user [reason] — Bans a user from all groups in the federation simultaneously.",
    "unfban": "/unfban @user — Lifts a federation ban so the user can rejoin federation groups.",
    "fedinfo": "/fedinfo — Shows the federation name, ID, owner, and list of member groups.",
    "rep": "/rep @user — Give +1 reputation to a member (reply or mention).",
    "topkarma": "/topkarma — Shows the 10 members with the highest reputation in this group.",
}


def _send_main_menu(chat_id):
    import json
    tg.api_call("sendMessage", {
        "chat_id": chat_id,
        "text": _WELCOME_TEXT,
        "parse_mode": "HTML",
        "reply_markup": json.dumps(_MAIN_MENU_KEYBOARD),
    })


def handle_menu_callback(cb):
    import json
    cq_id = cb["id"]
    data = cb.get("data", "")
    msg = cb.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    message_id = msg.get("message_id")

    if not data.startswith("menu:") or not chat_id or not message_id:
        return False

    section = data[len("menu:"):]
    tg.answer_callback_query(cq_id)

    if section == "main":
        tg.try_call("editMessageText", {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": _WELCOME_TEXT,
            "parse_mode": "HTML",
            "reply_markup": json.dumps(_MAIN_MENU_KEYBOARD),
        })
    elif section in _MENU_SECTIONS:
        tg.try_call("editMessageText", {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": _MENU_SECTIONS[section],
            "parse_mode": "HTML",
            "reply_markup": json.dumps(_BACK_KEYBOARD),
        })
    return True


def handle_private(message):
    text = message.get("text") or ""
    chat_id = message["chat"]["id"]
    print(f"[private] chat_id={chat_id} text={text!r}", flush=True)
    parts = text.split()
    if not parts:
        return
    cmd = parts[0].split("@")[0].lower()
    if cmd == "/start":
        _send_main_menu(chat_id)
    elif cmd == "/help":
        if len(parts) > 1:
            key = parts[1].lstrip("/").lower()
            detail = _COMMAND_HELP.get(key)
            if detail:
                tg.api_call("sendMessage", {"chat_id": chat_id, "text": detail, "parse_mode": "HTML"})
            else:
                tg.api_call("sendMessage", {"chat_id": chat_id,
                    "text": f"No help entry for <code>{key}</code>. Send /start to see all commands.",
                    "parse_mode": "HTML"})
        else:
            _send_main_menu(chat_id)


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
            user_id = new_member["id"]
            if federation.check_fban_on_join(state, chat_id, user_id):
                tg.ban_chat_member(chat_id, user_id)
                storage.append_event(chat_id, "fban_autoban", user_id=user_id)
                return
            if cas.check_on_join(state, chat_id, user_id):
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
        if handle_menu_callback(cb):
            pass
        elif not community.handle_welcome_callback(state, cb):
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
