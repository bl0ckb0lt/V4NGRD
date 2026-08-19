from .features import captcha
from .analytics import community
from .commands import schedule as schedule_cmd
from . import tg

_BOT_COMMANDS = [
    {"command": "start",          "description": "Show the command menu"},
    {"command": "help",           "description": "Help for a command: /help ban"},
    {"command": "ban",            "description": "Ban a user (reply or @username)"},
    {"command": "kick",           "description": "Remove a user (they can rejoin)"},
    {"command": "mute",           "description": "Silence a user"},
    {"command": "warn",           "description": "Issue a warning"},
    {"command": "warns",          "description": "Show a user's warning count"},
    {"command": "stats",          "description": "Activity and member stats"},
    {"command": "top",            "description": "Top 10 most active members"},
    {"command": "health",         "description": "Community health score"},
    {"command": "segment",        "description": "Member activity segments"},
    {"command": "export",         "description": "Download stats CSV"},
    {"command": "schedule",       "description": "Schedule a message: /schedule 1h text"},
    {"command": "schedules",      "description": "List scheduled messages"},
    {"command": "setwelcome",     "description": "Set the join welcome message"},
    {"command": "lock",           "description": "Lock a content type"},
    {"command": "captcha",        "description": "Toggle join captcha on/off"},
    {"command": "slowmode",       "description": "Set slow mode delay"},
    {"command": "cas",            "description": "Toggle CAS anti-spam"},
    {"command": "save",           "description": "Save a note"},
    {"command": "notes",          "description": "List saved notes"},
    {"command": "newfed",         "description": "Create a ban federation"},
    {"command": "fban",           "description": "Federation-ban a user"},
    {"command": "rep",            "description": "Give reputation to a member"},
    {"command": "topkarma",       "description": "Karma leaderboard"},
]


def run_all(state):
    tg.set_my_commands(_BOT_COMMANDS)
    for chat_id in list(state["groups"].keys()):
        captcha.sweep(state, int(chat_id))
    community.daily_rollup_all(state)
    community.drip_sweep(state)
    community.warn_expiry_sweep(state)
    schedule_cmd.sweep(state)
