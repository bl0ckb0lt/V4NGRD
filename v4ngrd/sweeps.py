from .features import captcha
from .analytics import community


def run_all(state):
    for chat_id in list(state["groups"].keys()):
        captcha.sweep(state, int(chat_id))
    community.daily_rollup_all(state)
    community.drip_sweep(state)
    community.warn_expiry_sweep(state)
