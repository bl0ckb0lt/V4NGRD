"""Combot Anti-Spam (CAS) integration. Checks new joiners against cas.chat public API."""
import json
import subprocess

from .. import storage, tg

CAS_API = "https://api.cas.chat/check"


def is_cas_banned(user_id):
    """Query CAS API. Returns (banned: bool, offenses: int)."""
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "5", f"{CAS_API}?user_id={user_id}"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            return False, 0
        data = json.loads(result.stdout)
        if data.get("ok"):
            offenses = data.get("result", {}).get("offenses", 1)
            return True, offenses
        return False, 0
    except Exception:
        return False, 0


def check_on_join(state, chat_id, user_id):
    """
    Check a new member against CAS. Bans and returns True if flagged.
    No-op and returns False if cas_enabled is off or user is clean.
    """
    group = storage.get_group(state, chat_id)
    if not group["settings"].get("cas_enabled"):
        return False
    banned, offenses = is_cas_banned(user_id)
    if not banned:
        return False
    tg.ban_chat_member(chat_id, user_id)
    storage.append_event(chat_id, "cas_ban", user_id=user_id, meta={"offenses": offenses})
    s = "s" if offenses != 1 else ""
    tg.send_message(chat_id, f"Banned a CAS-flagged user ({offenses} prior offense{s}).")
    return True
