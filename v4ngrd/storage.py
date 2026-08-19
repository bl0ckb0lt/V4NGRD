import json
import os
import time
from datetime import datetime, timezone

from . import config

DEFAULT_SETTINGS = {
    "welcome_message": "Welcome {first_name} to {group}! You are member #{count}.",
    "goodbye_message": "{first_name} has left {group}.",
    "warn_limit": config.DEFAULT_WARN_LIMIT,
    "warn_action": config.DEFAULT_WARN_ACTION,
    "antiflood": {
        "limit": config.DEFAULT_FLOOD_LIMIT,
        "window_sec": config.DEFAULT_FLOOD_WINDOW_SEC,
        "action": config.DEFAULT_FLOOD_ACTION,
    },
    "locks": {t: False for t in config.CONTENT_LOCK_TYPES},
    "blacklist_words": [],
    "captcha_enabled": False,
    "captcha_timeout_sec": config.DEFAULT_CAPTCHA_TIMEOUT_SEC,
    "log_channel_id": None,
    "federation_id": None,
    "orientation_text": None,
}


def now_ts():
    return int(time.time())


def today_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def month_key(ts=None):
    dt = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else datetime.now(timezone.utc)
    return dt.strftime("%Y-%m")


def empty_group():
    return {
        "title": "",
        "settings": json.loads(json.dumps(DEFAULT_SETTINGS)),
        "members": {},
        "notes": {},
        "filters": {},
        "stats": {"daily": {}},
        "modlog": [],
    }


def empty_state():
    return {"groups": {}, "last_update_id": 0}


def load_state():
    if not os.path.exists(config.STATE_PATH):
        return empty_state()
    with open(config.STATE_PATH, "r", encoding="utf-8") as f:
        try:
            state = json.load(f)
        except json.JSONDecodeError:
            return empty_state()
    state.setdefault("groups", {})
    state.setdefault("last_update_id", 0)
    return state


def save_state(state):
    tmp_path = config.STATE_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, config.STATE_PATH)


def get_group(state, chat_id):
    key = str(chat_id)
    if key not in state["groups"]:
        state["groups"][key] = empty_group()
    return state["groups"][key]


def get_member(group, user_id, defaults=None):
    key = str(user_id)
    if key not in group["members"]:
        group["members"][key] = {
            "first_name": "", "username": "", "join_date": now_ts(),
            "warns": 0, "muted_until": None, "message_count": 0,
            "last_active": now_ts(), "rep": 0, "captcha_deadline": None,
            "captcha_verified": True, "recent_msgs": [], "left_date": None,
            # Community analytics fields
            "invite_source": None,
            "clicked_welcome_at": None,
            "first_message_at": None,
            "third_message_at": None,
        }
        if defaults:
            state_member = group["members"][key]
            state_member.update(defaults)
    return group["members"][key]


def append_event(chat_id, event_type, user_id=None, actor_id=None, reason=None, meta=None):
    os.makedirs(config.EVENTS_DIR, exist_ok=True)
    ts = now_ts()
    record = {
        "ts": ts,
        "chat_id": str(chat_id),
        "type": event_type,
        "user_id": str(user_id) if user_id is not None else None,
        "actor_id": str(actor_id) if actor_id is not None else None,
        "reason": reason,
        "meta": meta or {},
    }
    path = os.path.join(config.EVENTS_DIR, f"{month_key(ts)}.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def read_events(months=None, chat_id=None, types=None, since_ts=None, until_ts=None):
    """Yield event dicts from the event log, optionally filtered."""
    if not os.path.isdir(config.EVENTS_DIR):
        return
    files = sorted(os.listdir(config.EVENTS_DIR))
    if months:
        files = [f for f in files if f[:-len(".jsonl")] in months]
    for fname in files:
        if not fname.endswith(".jsonl"):
            continue
        path = os.path.join(config.EVENTS_DIR, fname)
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if chat_id is not None and record.get("chat_id") != str(chat_id):
                    continue
                if types and record.get("type") not in types:
                    continue
                if since_ts is not None and record["ts"] < since_ts:
                    continue
                if until_ts is not None and record["ts"] > until_ts:
                    continue
                yield record


def load_federations():
    if not os.path.exists(config.FED_PATH):
        return {"federations": {}}
    with open(config.FED_PATH, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {"federations": {}}


def save_federations(data):
    tmp_path = config.FED_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, config.FED_PATH)
