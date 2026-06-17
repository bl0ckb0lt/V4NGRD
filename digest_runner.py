import sys

from v4ngrd import config, storage
from v4ngrd.analytics import digest


def main():
    if not config.BOT_TOKEN:
        raise SystemExit("BOT_TOKEN environment variable is not set.")

    period = sys.argv[1] if len(sys.argv) > 1 else "daily"
    if period not in ("daily", "weekly"):
        raise SystemExit("period must be 'daily' or 'weekly'")

    state = storage.load_state()
    for chat_id in list(state["groups"].keys()):
        digest.send_digest(state, int(chat_id), period)
    storage.save_state(state)


if __name__ == "__main__":
    main()
