import sys
import time
import traceback

from v4ngrd import config, storage, tg, dispatch, sweeps

LOOP_SECONDS = 55      # run this long per job; cron fires every 60s as watchdog
POLL_TIMEOUT = 20      # Telegram long-poll: block up to 20s waiting for updates


def main():
    if not config.BOT_TOKEN:
        raise SystemExit("BOT_TOKEN environment variable is not set.")

    state = storage.load_state()
    deadline = time.monotonic() + LOOP_SECONDS

    try:
        while True:
            remaining = deadline - time.monotonic()
            # leave 3 s for sweeps + state save before the job ends
            poll_secs = min(POLL_TIMEOUT, max(1, int(remaining) - 3))
            if remaining <= 3:
                break

            updates = tg.get_updates(state["last_update_id"] + 1, timeout=poll_secs)
            for update in updates:
                try:
                    dispatch.handle_update(state, update)
                except Exception:
                    print(f"Error handling update {update.get('update_id')}:",
                          file=sys.stderr)
                    traceback.print_exc()
                finally:
                    state["last_update_id"] = update["update_id"]
    finally:
        sweeps.run_all(state)
        storage.save_state(state)


if __name__ == "__main__":
    main()
