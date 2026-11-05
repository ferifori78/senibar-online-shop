"""Posting shop activity to a Telegram channel.

A live feed of the shop for the roaster: an order placed, a ticket opened, a
new customer, and an hourly summary of traffic. Separate from `providers.py`
because this is not a customer channel — nothing here is ever sent to a
customer, and confusing the two is how an internal note ends up on someone's
phone.

Telegram allows roughly 20 messages a minute to one channel and throttles a
bot that exceeds it, which is why site visits are summarised rather than
posted one by one.
"""

import logging

from django.conf import settings

logger = logging.getLogger("senobar.telegram")

API = "https://api.telegram.org/bot{token}/sendMessage"

# Telegram rejects a message over 4096 characters outright.
MAX_LEN = 4000


class TelegramError(Exception):
    """The channel refused the message, or was unreachable."""


def is_configured():
    return bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID)


def escape(text):
    """Escape the characters MarkdownV2 treats as syntax.

    Persian text routinely contains dashes, dots and parentheses, any of which
    would otherwise make Telegram reject the whole message as malformed
    markup — and the failure looks like "the bot stopped working" rather than
    like a formatting problem.
    """
    out = []
    for ch in str(text or ""):
        if ch in r"_*[]()~`>#+-=|{}.!\\":
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "".join(out)


def send(text, *, silent=False):
    """Post one message to the channel.

    Returns False when Telegram is not configured, rather than raising: the
    feed is an convenience, and a shop with no bot token must still be able to
    take orders.
    """
    if not is_configured():
        return False

    import requests

    payload = {
        "chat_id": settings.TELEGRAM_CHAT_ID,
        "text": text[:MAX_LEN],
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": True,
        # Digests arrive on the hour and should not buzz every phone.
        "disable_notification": bool(silent),
    }

    try:
        response = requests.post(
            API.format(token=settings.TELEGRAM_BOT_TOKEN),
            json=payload,
            timeout=settings.TELEGRAM_TIMEOUT,
        )
    except Exception as exc:
        raise TelegramError(f"Telegram unreachable: {exc}") from exc

    try:
        body = response.json()
    except ValueError:
        raise TelegramError(
            f"Telegram returned non-JSON (HTTP {response.status_code})."
        ) from None

    if not body.get("ok"):
        # `description` names the real cause — a bad token, a chat the bot was
        # never added to, or markup Telegram could not parse.
        raise TelegramError(
            f"Telegram refused the message (HTTP {response.status_code}): "
            f"{body.get('description')!r}"
        )

    return True
