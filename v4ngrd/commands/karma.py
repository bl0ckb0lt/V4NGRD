from .. import storage, tg, util


def cmd_rep(state, chat_id, message, args):
    actor = message["from"]
    reply = message.get("reply_to_message")
    if not reply or not reply.get("from"):
        return tg.send_message(chat_id, "Reply to a user's message with /rep to give them reputation.")

    target = reply["from"]
    if target["id"] == actor["id"]:
        return tg.send_message(chat_id, "You can't rep yourself.")

    group = storage.get_group(state, chat_id)
    member = storage.get_member(group, target["id"], defaults={
        "first_name": target.get("first_name", ""), "username": target.get("username", ""),
    })
    member["rep"] += 1
    storage.append_event(chat_id, "karma_rep", user_id=target["id"], actor_id=actor["id"])
    tg.send_message(chat_id, f"{util.mention(target['id'], util.display_name(target))} now has {member['rep']} reputation.")


def cmd_topkarma(state, chat_id, message, args):
    group = storage.get_group(state, chat_id)
    ranked = sorted(group["members"].items(), key=lambda kv: kv[1].get("rep", 0), reverse=True)[:10]
    if not ranked:
        return tg.send_message(chat_id, "No reputation data yet.")
    lines = [f"{i+1}. {util.escape_html(m.get('first_name') or uid)} — {m.get('rep', 0)} rep"
             for i, (uid, m) in enumerate(ranked)]
    tg.send_message(chat_id, "<b>Top reputation</b>\n" + "\n".join(lines))
