from . import storage, tg, util


def record(state, chat_id, action, target_id=None, target_name=None,
           actor_id=None, actor_name=None, reason=None):
    group = storage.get_group(state, chat_id)
    entry = {
        "ts": storage.now_ts(),
        "action": action,
        "target_id": target_id,
        "target_name": target_name,
        "actor_id": actor_id,
        "actor_name": actor_name,
        "reason": reason,
    }
    group["modlog"].append(entry)
    group["modlog"] = group["modlog"][-500:]

    storage.append_event(
        chat_id, f"mod_{action}", user_id=target_id, actor_id=actor_id,
        reason=reason,
    )

    log_channel_id = group["settings"].get("log_channel_id")
    if log_channel_id:
        text = (
            f"<b>{util.escape_html(action.upper())}</b>\n"
            f"Target: {util.mention(target_id, target_name) if target_id else util.escape_html(target_name)}\n"
            f"By: {util.escape_html(actor_name or 'system')}\n"
        )
        if reason:
            text += f"Reason: {util.escape_html(reason)}\n"
        tg.send_message(log_channel_id, text)

    return entry
