import json
import subprocess

from . import config


class TelegramError(Exception):
    pass


def api_call(method, params=None, files=None, timeout=30):
    """Call a Telegram Bot API method via curl. No shell=True, args passed as a list."""
    url = f"{config.API_BASE}/{method}"
    cmd = ["curl", "-s", "--max-time", str(timeout)]

    if files:
        for key, value in (params or {}).items():
            if value is None:
                continue
            cmd += ["-F", f"{key}={_stringify(value)}"]
        for key, path in files.items():
            cmd += ["-F", f"{key}=@{path}"]
        cmd += [url]
    else:
        cmd += ["-X", "POST", url, "-H", "Content-Type: application/json",
                "-d", json.dumps(params or {})]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise TelegramError(f"curl failed for {method}: {result.stderr.strip()}")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise TelegramError(f"bad response for {method}: {result.stdout[:300]}")

    if not data.get("ok"):
        raise TelegramError(f"{method} failed: {data.get('description')}")
    return data["result"]


def _stringify(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)


def try_call(method, params=None, files=None):
    """Same as api_call but swallows TelegramError, returning None on failure."""
    try:
        return api_call(method, params, files)
    except TelegramError:
        return None


def get_updates(offset, timeout=0):
    return api_call("getUpdates", {
        "offset": offset,
        "timeout": timeout,
        "allowed_updates": json.dumps([
            "message", "edited_message", "callback_query",
            "chat_member", "my_chat_member", "message_reaction",
        ]),
    })


def send_message(chat_id, text, reply_to=None, parse_mode="HTML",
                  reply_markup=None, disable_notification=False):
    params = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_notification": disable_notification,
    }
    if reply_to:
        params["reply_to_message_id"] = reply_to
    if reply_markup:
        params["reply_markup"] = json.dumps(reply_markup)
    return try_call("sendMessage", params)


def edit_message_text(chat_id, message_id, text, parse_mode="HTML", reply_markup=None):
    params = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    if reply_markup:
        params["reply_markup"] = json.dumps(reply_markup)
    return try_call("editMessageText", params)


def delete_message(chat_id, message_id):
    return try_call("deleteMessage", {"chat_id": chat_id, "message_id": message_id})


def send_photo(chat_id, photo_path, caption=None):
    params = {"chat_id": chat_id}
    if caption:
        params["caption"] = caption
    return try_call("sendPhoto", params, files={"photo": photo_path})


def send_document(chat_id, doc_path, caption=None):
    params = {"chat_id": chat_id}
    if caption:
        params["caption"] = caption
    return try_call("sendDocument", params, files={"document": doc_path})


def ban_chat_member(chat_id, user_id, until_date=None, revoke_messages=False):
    params = {"chat_id": chat_id, "user_id": user_id, "revoke_messages": revoke_messages}
    if until_date:
        params["until_date"] = until_date
    return try_call("banChatMember", params)


def unban_chat_member(chat_id, user_id, only_if_banned=True):
    return try_call("unbanChatMember", {
        "chat_id": chat_id, "user_id": user_id, "only_if_banned": only_if_banned,
    })


def restrict_chat_member(chat_id, user_id, permissions, until_date=None):
    params = {
        "chat_id": chat_id,
        "user_id": user_id,
        "permissions": json.dumps(permissions),
    }
    if until_date:
        params["until_date"] = until_date
    return try_call("restrictChatMember", params)


MUTE_PERMISSIONS = {
    "can_send_messages": False,
    "can_send_audios": False,
    "can_send_documents": False,
    "can_send_photos": False,
    "can_send_videos": False,
    "can_send_video_notes": False,
    "can_send_voice_notes": False,
    "can_send_polls": False,
    "can_send_other_messages": False,
    "can_add_web_page_previews": False,
}

UNMUTE_PERMISSIONS = {k: True for k in MUTE_PERMISSIONS}


def mute_chat_member(chat_id, user_id, until_date=None):
    return restrict_chat_member(chat_id, user_id, MUTE_PERMISSIONS, until_date)


def unmute_chat_member(chat_id, user_id):
    return restrict_chat_member(chat_id, user_id, UNMUTE_PERMISSIONS)


def get_chat_member(chat_id, user_id):
    return try_call("getChatMember", {"chat_id": chat_id, "user_id": user_id})


def get_chat(chat_id):
    return try_call("getChat", {"chat_id": chat_id})


def answer_callback_query(callback_query_id, text=None, show_alert=False):
    params = {"callback_query_id": callback_query_id, "show_alert": show_alert}
    if text:
        params["text"] = text
    return try_call("answerCallbackQuery", params)


def set_slow_mode(chat_id, slow_mode_delay):
    """Set slow mode delay in seconds. Valid values: 0,10,30,60,300,900,3600,21600,86400."""
    return try_call("setChatSlowModeDelay", {"chat_id": chat_id, "slow_mode_delay": slow_mode_delay})


def set_my_commands(commands):
    """Register bot commands with Telegram (shown in the / picker).
    commands: list of {"command": str, "description": str}
    """
    return try_call("setMyCommands", {"commands": json.dumps(commands)})


def is_admin(chat_id, user_id):
    member = get_chat_member(chat_id, user_id)
    if not member:
        return False
    return member.get("status") in ("creator", "administrator")


def download_file_via_url(url, dest_path, timeout=30):
    cmd = ["curl", "-s", "--max-time", str(timeout), "-o", dest_path, url]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0
