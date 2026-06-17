from datetime import datetime, timedelta, timezone

from .. import storage


def daily_series(group, days=7):
    """Return [(date_str, messages, joins, leaves), ...] for the last `days` days, oldest first."""
    today = datetime.now(timezone.utc).date()
    out = []
    for i in range(days - 1, -1, -1):
        day = (today - timedelta(days=i)).isoformat()
        stats = group["stats"]["daily"].get(day, {"messages": 0, "joins": 0, "leaves": 0})
        out.append((day, stats.get("messages", 0), stats.get("joins", 0), stats.get("leaves", 0)))
    return out


def hourly_activity(group):
    """Return a 24-length list of message counts by UTC hour-of-day, all-time."""
    return group["stats"].get("hourly", [0] * 24)


def active_member_count(group):
    return sum(1 for m in group["members"].values() if m.get("left_date") is None)


def top_members(group, n=10, by="message_count"):
    ranked = sorted(group["members"].items(), key=lambda kv: kv[1].get(by, 0), reverse=True)
    return ranked[:n]


def net_growth(group, days=7):
    series = daily_series(group, days)
    joins = sum(j for _, _, j, _ in series)
    leaves = sum(l for _, _, _, l in series)
    return joins, leaves, joins - leaves


def record_message_stat(group, member, ts=None):
    ts = ts or storage.now_ts()
    day = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
    daily = group["stats"]["daily"].setdefault(day, {"messages": 0, "joins": 0, "leaves": 0})
    daily["messages"] += 1

    hourly = group["stats"].setdefault("hourly", [0] * 24)
    hour = datetime.fromtimestamp(ts, tz=timezone.utc).hour
    hourly[hour] += 1

    member["message_count"] += 1
    member["last_active"] = ts
