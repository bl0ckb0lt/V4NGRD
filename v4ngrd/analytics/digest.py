import os

from .. import storage, tg, util
from . import core, charts, insights


def build_text(group, title_prefix="Daily digest"):
    series = core.daily_series(group, 7)
    joins, leaves, net = core.net_growth(group, 7)
    total_msgs = sum(m for _, m, _, _ in series)
    active_members = core.active_member_count(group)

    lines = [
        f"<b>{util.escape_html(title_prefix)} — {util.escape_html(group.get('title') or '')}</b>",
        "",
        f"Members: {active_members}",
        f"Messages (7d): {total_msgs}",
        f"Joins (7d): {joins} | Leaves (7d): {leaves} | Net: {'+' if net >= 0 else ''}{net}",
        "",
        "<b>Insights</b>",
    ]
    lines += [f"- {util.escape_html(i)}" for i in insights.generate(group)]

    top = core.top_members(group, n=5)
    if top:
        lines.append("")
        lines.append("<b>Top contributors (7d totals)</b>")
        for user_id, member in top:
            name = member.get("first_name") or user_id
            lines.append(f"- {util.escape_html(name)}: {member.get('message_count', 0)} msgs")

    return "\n".join(lines)


def send_digest(state, chat_id, period="daily"):
    group = storage.get_group(state, chat_id)
    title_prefix = "Daily digest" if period == "daily" else "Weekly digest"
    text = build_text(group, title_prefix)

    series = core.daily_series(group, 14 if period == "weekly" else 7)
    labels = [d for d, _, _, _ in series]
    values = [m for _, m, _, _ in series]
    chart_path = charts.fetch_chart(charts.line_chart(labels, {"messages": values}, "Message activity"))

    if chart_path:
        tg.send_photo(chat_id, chart_path, caption=text)
        os.remove(chart_path)
    else:
        tg.send_message(chat_id, text)
