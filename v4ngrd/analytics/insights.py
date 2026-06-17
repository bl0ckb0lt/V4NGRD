from . import core, churn


def _pct_change(old, new):
    if old == 0:
        return 100 if new > 0 else 0
    return round(100 * (new - old) / old)


def generate(group):
    insights = []

    last7 = core.daily_series(group, 7)
    prev7 = core.daily_series(group, 14)[:7]
    msgs_now = sum(m for _, m, _, _ in last7)
    msgs_prev = sum(m for _, m, _, _ in prev7)
    joins_now = sum(j for _, _, j, _ in last7)
    joins_prev = sum(j for _, _, j, _ in prev7)
    leaves_now = sum(l for _, _, _, l in last7)
    leaves_prev = sum(l for _, _, _, l in prev7)

    msg_change = _pct_change(msgs_prev, msgs_now)
    if abs(msg_change) >= 15:
        direction = "up" if msg_change > 0 else "down"
        insights.append(f"Message activity is {direction} {abs(msg_change)}% vs the prior 7 days.")

    join_change = _pct_change(joins_prev, joins_now)
    if abs(join_change) >= 20 and (joins_now or joins_prev):
        direction = "up" if join_change > 0 else "down"
        insights.append(f"New joins are {direction} {abs(join_change)}% week-over-week ({joins_now} this week).")

    if leaves_now > 0 and leaves_now >= max(3, leaves_prev * 1.5):
        insights.append(f"Leaves spiked to {leaves_now} this week (was {leaves_prev}) — worth checking for a recent cause.")

    hourly = core.hourly_activity(group)
    if any(hourly):
        peak_hour = hourly.index(max(hourly))
        insights.append(f"Peak activity hour is {peak_hour:02d}:00 UTC — good time to schedule announcements.")

    at_risk = churn.at_risk_members(group, n=5)
    if at_risk:
        insights.append(f"{len(at_risk)} previously active member(s) have gone quiet for 14+ days — consider re-engaging them.")

    if not insights:
        insights.append("No notable changes this week.")
    return insights
