import csv
import os
import tempfile

from .. import storage, tg, util
from ..analytics import core, charts, cohorts, churn, insights, digest


def _require_admin(message, chat_id):
    return tg.is_admin(chat_id, message["from"]["id"])


def cmd_stats(state, chat_id, message, args):
    group = storage.get_group(state, chat_id)
    series = core.daily_series(group, 7)
    joins, leaves, net = core.net_growth(group, 7)
    total_msgs = sum(m for _, m, _, _ in series)
    active_members = core.active_member_count(group)

    text = (
        f"<b>Stats for {util.escape_html(group.get('title') or 'this group')}</b>\n"
        f"Members: {active_members}\n"
        f"Messages (7d): {total_msgs}\n"
        f"Joins (7d): {joins} | Leaves (7d): {leaves} | Net: {'+' if net >= 0 else ''}{net}"
    )
    tg.send_message(chat_id, text)


def cmd_activity(state, chat_id, message, args):
    group = storage.get_group(state, chat_id)

    hourly = core.hourly_activity(group)
    hour_labels = [f"{h:02d}" for h in range(24)]
    hourly_path = charts.fetch_chart(charts.bar_chart(hour_labels, hourly, "Activity by hour (UTC)"))
    if hourly_path:
        tg.send_photo(chat_id, hourly_path, caption="Hourly activity (all-time, UTC)")
        os.remove(hourly_path)

    series = core.daily_series(group, 7)
    labels = [d for d, _, _, _ in series]
    values = [m for _, m, _, _ in series]
    daily_path = charts.fetch_chart(charts.line_chart(labels, {"messages": values}, "Last 7 days"))
    if daily_path:
        tg.send_photo(chat_id, daily_path, caption="7-day message activity")
        os.remove(daily_path)

    if not hourly_path and not daily_path:
        tg.send_message(chat_id, "Could not render charts right now.")


def cmd_top(state, chat_id, message, args):
    group = storage.get_group(state, chat_id)
    top = core.top_members(group, n=10)
    if not top:
        return tg.send_message(chat_id, "No activity yet.")
    lines = [f"{i+1}. {util.escape_html(m.get('first_name') or uid)} — {m.get('message_count', 0)} msgs"
             for i, (uid, m) in enumerate(top)]
    tg.send_message(chat_id, "<b>Top members</b>\n" + "\n".join(lines))


def cmd_modlog(state, chat_id, message, args):
    group = storage.get_group(state, chat_id)
    entries = group["modlog"][-10:]
    if not entries:
        return tg.send_message(chat_id, "No mod actions logged yet.")
    lines = []
    for e in reversed(entries):
        target = util.escape_html(e.get("target_name") or str(e.get("target_id") or ""))
        lines.append(f"<b>{util.escape_html(e['action'])}</b> — {target}"
                      + (f" ({util.escape_html(e['reason'])})" if e.get("reason") else ""))
    tg.send_message(chat_id, "<b>Recent mod actions</b>\n" + "\n".join(lines))


def cmd_digestnow(state, chat_id, message, args):
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    period = args[0] if args and args[0] in ("daily", "weekly") else "daily"
    digest.send_digest(state, chat_id, period)


def cmd_insights(state, chat_id, message, args):
    group = storage.get_group(state, chat_id)
    lines = [f"- {util.escape_html(i)}" for i in insights.generate(group)]
    tg.send_message(chat_id, "<b>Insights</b>\n" + "\n".join(lines))


def cmd_cohorts(state, chat_id, message, args):
    group = storage.get_group(state, chat_id)
    rows = cohorts.retention_cohorts(group)
    if not rows:
        return tg.send_message(chat_id, "Not enough join history yet.")
    lines = [f"{r['week']}: {r['joined']} joined, {r['retained_pct']}% retained, {r['posted_pct']}% ever posted"
             for r in rows]
    tg.send_message(chat_id, "<b>Retention cohorts (by join week)</b>\n" + "\n".join(lines))


def cmd_churnrisk(state, chat_id, message, args):
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    group = storage.get_group(state, chat_id)
    risky = churn.at_risk_members(group)
    if not risky:
        return tg.send_message(chat_id, "No at-risk members detected.")
    lines = [f"- {util.escape_html(str(r['name']))}: quiet for {r['idle_days']}d, {r['message_count']} lifetime msgs"
             for r in risky]
    tg.send_message(chat_id, "<b>Churn risk (previously active, now quiet 14+ days)</b>\n" + "\n".join(lines))


def cmd_export(state, chat_id, message, args):
    if not _require_admin(message, chat_id):
        return tg.send_message(chat_id, "Only admins can do that.")
    days = int(args[0]) if args and args[0].isdigit() else 30
    since_ts = storage.now_ts() - days * 86400

    events = list(storage.read_events(chat_id=chat_id, since_ts=since_ts))

    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ts", "type", "user_id", "actor_id", "reason"])
        for e in events:
            writer.writerow([e["ts"], e["type"], e.get("user_id"), e.get("actor_id"), e.get("reason") or ""])

    tg.send_document(chat_id, path, caption=f"Export: last {days} days, {len(events)} events.")
    os.remove(path)
