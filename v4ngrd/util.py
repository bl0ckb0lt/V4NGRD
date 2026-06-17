import re

from . import config

DURATION_RE = re.compile(r"^(\d+)([hmdw])$")


def parse_duration(text):
    """Parse '1h', '30m', '2d', '1w' -> seconds. Returns None if invalid."""
    if not text:
        return None
    match = DURATION_RE.match(text.strip().lower())
    if not match:
        return None
    amount, unit = match.groups()
    return int(amount) * config.DEFAULT_MUTE_SECONDS[unit]


def mention(user_id, name):
    safe = escape_html(name or str(user_id))
    return f'<a href="tg://user?id={user_id}">{safe}</a>'


def escape_html(text):
    if text is None:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def render_template(template, **kwargs):
    out = template
    for key, value in kwargs.items():
        out = out.replace("{" + key + "}", str(value))
    return out


def extract_target(message, args):
    """Determine the target user of an admin command.

    Priority: reply-to message sender, then @username / numeric id as first arg.
    Returns (user_id, display_name, remaining_args) or (None, None, args).
    """
    reply = message.get("reply_to_message")
    if reply and reply.get("from"):
        sender = reply["from"]
        return sender["id"], display_name(sender), args

    if args:
        first = args[0]
        if first.startswith("@"):
            return None, first, args[1:]
        if first.lstrip("-").isdigit():
            return int(first), first, args[1:]

    return None, None, args


def display_name(user):
    name = user.get("first_name", "")
    if user.get("last_name"):
        name += " " + user["last_name"]
    return name.strip() or user.get("username", "") or str(user.get("id", ""))


def is_command(text, name):
    if not text or not text.startswith("/"):
        return False
    head = text.split()[0]
    head = head.split("@")[0]
    return head[1:].lower() == name


def command_args(text):
    parts = text.split()
    return parts[1:] if len(parts) > 1 else []
