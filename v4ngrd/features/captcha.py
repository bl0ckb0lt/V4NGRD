from .. import storage, tg, util, modlog


def start(state, chat_id, user_id, welcome_text):
    group = storage.get_group(state, chat_id)
    member = storage.get_member(group, user_id)
    timeout = group["settings"]["captcha_timeout_sec"]

    tg.restrict_chat_member(chat_id, user_id, tg.MUTE_PERMISSIONS)
    member["captcha_verified"] = False
    member["captcha_deadline"] = storage.now_ts() + timeout

    keyboard = {"inline_keyboard": [[
        {"text": "I'm not a robot", "callback_data": f"captcha:{user_id}"}
    ]]}
    text = welcome_text + f"\n\nPlease tap the button below within {timeout // 60} minutes to start chatting."
    sent = tg.send_message(chat_id, text, reply_markup=keyboard)
    if sent:
        member["captcha_msg_id"] = sent.get("message_id")


def handle_callback(state, callback_query):
    data = callback_query.get("data", "")
    if not data.startswith("captcha:"):
        return False

    target_user_id = data.split(":", 1)[1]
    clicker = callback_query["from"]
    chat = callback_query["message"]["chat"]
    chat_id = chat["id"]

    if str(clicker["id"]) != target_user_id:
        tg.answer_callback_query(callback_query["id"], "This isn't your captcha.", show_alert=True)
        return True

    group = storage.get_group(state, chat_id)
    member = storage.get_member(group, clicker["id"])
    member["captcha_verified"] = True
    member["captcha_deadline"] = None

    tg.unmute_chat_member(chat_id, clicker["id"])
    tg.answer_callback_query(callback_query["id"], "Verified, welcome!")
    tg.edit_message_text(chat_id, callback_query["message"]["message_id"],
                          f"{util.mention(clicker['id'], util.display_name(clicker))} is verified.")
    storage.append_event(chat_id, "captcha_pass", user_id=clicker["id"])
    return True


def sweep(state, chat_id):
    """Kick members who never verified before their captcha deadline."""
    group = storage.get_group(state, chat_id)
    now = storage.now_ts()
    for user_id_str, member in list(group["members"].items()):
        deadline = member.get("captcha_deadline")
        if deadline is None or member.get("captcha_verified"):
            continue
        if now < deadline:
            continue

        user_id = int(user_id_str)
        tg.ban_chat_member(chat_id, user_id)
        tg.unban_chat_member(chat_id, user_id)
        member["captcha_deadline"] = None
        storage.append_event(chat_id, "captcha_timeout", user_id=user_id)
        modlog.record(state, chat_id, "captcha_timeout_kick", user_id, member.get("first_name"),
                      reason="did not verify in time")
        msg_id = member.get("captcha_msg_id")
        if msg_id:
            tg.delete_message(chat_id, msg_id)
