# V4NGRD

Serverless Telegram group management bot. No server, no database — state lives in
git-committed JSON, processing runs on GitHub Actions cron, all Telegram API calls go
through `curl` (no third-party Python dependencies).

## Setup

1. Create a bot with [@BotFather](https://t.me/BotFather), get the token.
2. Add a repo secret `BOT_TOKEN` with that token (Settings → Secrets and variables → Actions).
3. Add the bot to your group(s) as an admin (needs ban/restrict/delete permissions).
4. The `poll` workflow runs every 2 minutes and processes new updates. The `digest`
   workflow posts a daily/weekly report to each managed group.
5. To trigger a digest on demand: Actions → V4NGRD digest → Run workflow.

## Architecture

- `group_manager.py` — entrypoint, runs one poll cycle (fetch updates, dispatch, sweep, save).
- `digest_runner.py` — entrypoint for the scheduled digest report.
- `v4ngrd/tg.py` — Telegram Bot API wrapper via `curl` subprocess.
- `v4ngrd/storage.py` — state persistence. Two layers:
  - `group_state.json` — current-state snapshot (members, settings, notes, modlog), overwritten atomically each run.
  - `data/events/YYYY-MM.jsonl` — append-only event log (joins, leaves, bans, warns, floods, fbans, etc.). Never overwritten, so a bug in the snapshot logic can never destroy history — it can always be replayed from here. This is also the data source for `/export`, retention cohorts, and churn analysis.
- `v4ngrd/features/` — message-time behaviors: antiflood, blacklist, content locks, keyword filters, welcome/goodbye, captcha gate, karma/reputation.
- `v4ngrd/commands/` — `/command` handlers, grouped by area (moderation, settings, notes, federation, analytics, karma).
- `v4ngrd/analytics/` — stats aggregation, retention cohorts, churn-risk detection, plain-language insights, chart rendering (via [QuickChart](https://quickchart.io), no plotting library needed), and the digest builder.

Every moderation action is also a git commit, so the commit history doubles as a
tamper-evident audit trail independent of the JSON state.

## Commands

**Moderation:** `/ban /unban /kick /mute /unmute /warn /unwarn /warns`

**Settings:** `/setwelcome /setgoodbye /lock /unlock /locks /addblacklist /rmblacklist
/blacklist /setflood /setwarnlimit /setwarnaction /setlog /captcha`

**Filters & notes:** `/filter /stop /filters /save /get /notes /clear` (plus `#name` shortcut)

**Federations:** `/newfed /joinfed /leavefed /fban /unfban /fedinfo` — shared cross-group banlist.

**Analytics:** `/stats /activity /top /modlog /insights /cohorts /churnrisk /export [days]
/digestnow [daily|weekly]`

**Karma:** `/rep` (reply to a message to give +1), `/topkarma`. Also responds to message
reactions automatically.

## Local testing

No live network needed for logic checks — `tg.try_call` and `tg.download_file_via_url`
can be monkeypatched to exercise `v4ngrd.dispatch.handle_message` directly with
constructed Telegram update dicts.
