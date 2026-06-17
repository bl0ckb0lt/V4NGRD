from .. import storage

QUIET_THRESHOLD_SEC = 14 * 86400
ACTIVE_MIN_MESSAGES = 3


def at_risk_members(group, n=15):
    """Previously-active members who have gone quiet but haven't left."""
    now = storage.now_ts()
    risky = []
    for user_id, member in group["members"].items():
        if member.get("left_date") is not None:
            continue
        if member.get("message_count", 0) < ACTIVE_MIN_MESSAGES:
            continue
        idle_for = now - member.get("last_active", now)
        if idle_for >= QUIET_THRESHOLD_SEC:
            risky.append({
                "user_id": user_id,
                "name": member.get("first_name") or user_id,
                "idle_days": idle_for // 86400,
                "message_count": member.get("message_count", 0),
            })
    risky.sort(key=lambda r: r["idle_days"], reverse=True)
    return risky[:n]


def churned_active_members(group, n=15):
    """Members who were active contributors and then left, the highest-value losses."""
    churned = []
    for user_id, member in group["members"].items():
        if member.get("left_date") is None:
            continue
        if member.get("message_count", 0) < ACTIVE_MIN_MESSAGES:
            continue
        churned.append({
            "user_id": user_id,
            "name": member.get("first_name") or user_id,
            "message_count": member.get("message_count", 0),
            "left_date": member["left_date"],
        })
    churned.sort(key=lambda r: r["message_count"], reverse=True)
    return churned[:n]
