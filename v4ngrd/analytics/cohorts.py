from datetime import datetime, timezone

from .. import storage


def _week_key(ts):
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    year, week, _ = dt.isocalendar()
    return f"{year}-W{week:02d}"


def retention_cohorts(group, weeks=8):
    """Group members by join-week; for each cohort report size, % still in the
    group, and % who ever posted (vs pure lurkers)."""
    cohorts = {}
    now = storage.now_ts()
    cutoff = now - weeks * 7 * 86400

    for member in group["members"].values():
        join_date = member.get("join_date")
        if not join_date or join_date < cutoff:
            continue
        key = _week_key(join_date)
        bucket = cohorts.setdefault(key, {"joined": 0, "retained": 0, "ever_posted": 0})
        bucket["joined"] += 1
        if member.get("left_date") is None:
            bucket["retained"] += 1
        if member.get("message_count", 0) > 0:
            bucket["ever_posted"] += 1

    rows = []
    for week in sorted(cohorts):
        b = cohorts[week]
        retained_pct = round(100 * b["retained"] / b["joined"]) if b["joined"] else 0
        posted_pct = round(100 * b["ever_posted"] / b["joined"]) if b["joined"] else 0
        rows.append({
            "week": week, "joined": b["joined"],
            "retained_pct": retained_pct, "posted_pct": posted_pct,
        })
    return rows
