from .. import storage, tg, util
from ..analytics import community
from . import captcha


def handle_join(state, chat_id, message):
    group = storage.get_group(state, chat_id)
    for new_member in message.get("new_chat_members", []):
        if new_member.get("is_bot"):
            continue
        member = storage.get_member(group, new_member["id"], defaults={
            "first_name": new_member.get("first_name", ""),
            "username": new_member.get("username", ""),
            "join_date": storage.now_ts(),
        })
        member["first_name"] = new_member.get("first_name", "")
        member["username"] = new_member.get("username", "")
        member["left_date"] = None

        storage.append_event(chat_id, "join", user_id=new_member["id"])
        day = storage.today_str()
        daily = group["stats"]["daily"].setdefault(day, {"messages": 0, "joins": 0, "leaves": 0})
        daily["joins"] += 1

        text = util.render_template(
            group["settings"]["welcome_message"],
            first_name=util.escape_html(new_member.get("first_name", "")),
            username=util.escape_html(new_member.get("username", "") or "no username"),
            group=util.escape_html(group.get("title") or "the group"),
            count=len(group["members"]),
        )

        if group["settings"]["captcha_enabled"]:
            captcha.start(state, chat_id, new_member["id"], text)
        else:
            reply_markup = {"inline_keyboard": [[
                {"text": "Start here ▶", "callback_data": f"welcome:{new_member['id']}"}
            ]]}
            tg.send_message(chat_id, text, reply_markup=reply_markup)


def handle_leave(state, chat_id, message):
    left = message.get("left_chat_member")
    if not left or left.get("is_bot"):
        return
    group = storage.get_group(state, chat_id)
    member = group["members"].get(str(left["id"]))
    display = member["first_name"] if member else left.get("first_name", "")
    if member:
        member["left_date"] = storage.now_ts()

    storage.append_event(chat_id, "leave", user_id=left["id"])
    day = storage.today_str()
    daily = group["stats"]["daily"].setdefault(day, {"messages": 0, "joins": 0, "leaves": 0})
    daily["leaves"] += 1

    text = util.render_template(
        group["settings"]["goodbye_message"],
        first_name=util.escape_html(display),
        username=util.escape_html(left.get("username", "") or "no username"),
        group=util.escape_html(group.get("title") or "the group"),
        count=len(group["members"]),
    )
    tg.send_message(chat_id, text)
