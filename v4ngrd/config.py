import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

STATE_PATH = os.environ.get("STATE_PATH", "group_state.json")
FED_PATH = os.environ.get("FED_PATH", "federation_state.json")
EVENTS_DIR = os.environ.get("EVENTS_DIR", "data/events")

DEFAULT_WARN_LIMIT = 3
DEFAULT_WARN_ACTION = "ban"  # ban | kick | mute
DEFAULT_FLOOD_LIMIT = 5
DEFAULT_FLOOD_WINDOW_SEC = 10
DEFAULT_FLOOD_ACTION = "mute"
DEFAULT_CAPTCHA_TIMEOUT_SEC = 5 * 60
DEFAULT_MUTE_SECONDS = {"h": 3600, "m": 60, "d": 86400, "w": 604800}

CONTENT_LOCK_TYPES = [
    "sticker", "gif", "link", "document", "video",
    "photo", "audio", "voice", "forward", "poll",
]

QUICKCHART_BASE = "https://quickchart.io/chart"
