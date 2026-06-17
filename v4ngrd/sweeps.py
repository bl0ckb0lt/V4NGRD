from .features import captcha


def run_all(state):
    for chat_id in list(state["groups"].keys()):
        captcha.sweep(state, int(chat_id))
