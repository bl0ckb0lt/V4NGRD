from v4ngrd import config, storage, dispatch, sweeps


def main():
    if not config.BOT_TOKEN:
        raise SystemExit("BOT_TOKEN environment variable is not set.")

    state = storage.load_state()
    try:
        dispatch.process_updates(state)
    finally:
        sweeps.run_all(state)
        storage.save_state(state)


if __name__ == "__main__":
    main()
