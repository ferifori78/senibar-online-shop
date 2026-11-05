"""Delivery drivers for SMS.

Email goes through Django's own backend, which already has a console driver.
SMS has no such thing, so this module provides the same shape: a driver picked
by settings, with a console default that prints instead of sending.
"""

import logging

from django.conf import settings

from config.digits import digits_only

logger = logging.getLogger("senobar.notifications")


class SMSError(Exception):
    """The provider refused the message or was unreachable."""


class BaseSMSBackend:
    name = "base"

    def send(self, *, to, body):
        raise NotImplementedError

    def send_verify(self, *, to, code, template_id=None, parameters=None):
        """Send a one-time code through the provider's verify channel.

        Separate from `send` because Iranian providers route verification
        codes over service lines, which reach numbers that have opted out of
        advertising SMS and are not subject to the same delivery delays. A
        provider without that channel falls back to an ordinary message.
        """
        return self.send(to=to, body=f"کد ورود شما به صنوبر: {code}")


class ConsoleSMSBackend(BaseSMSBackend):
    """Logs the message. The default in development, and in tests."""

    name = "console"

    def send(self, *, to, body):
        logger.info("SMS -> %s\n%s", to, body)
        return {"provider": "console", "to": to, "status": "logged"}

    def send_verify(self, *, to, code, template_id=None, parameters=None):
        # The code is logged so a developer can actually complete a login
        # locally without a provider account.
        logger.info("SMS VERIFY -> %s  code=%s", to, code)
        return {"provider": "console", "to": to, "code": str(code), "status": "logged"}


class KavenegarSMSBackend(BaseSMSBackend):
    """Kavenegar, a common Iranian SMS provider.

    Not exercised in tests — it needs a real API key — but written out so
    switching is a settings change rather than a code change.
    """

    name = "kavenegar"
    ENDPOINT = "https://api.kavenegar.com/v1/{key}/sms/send.json"

    def __init__(self):
        self.api_key = settings.KAVENEGAR_API_KEY
        if not self.api_key:
            raise SMSError("KAVENEGAR_API_KEY is not configured.")

    def send(self, *, to, body):
        import requests

        try:
            response = requests.post(
                self.ENDPOINT.format(key=self.api_key),
                data={"receptor": to, "message": body, "sender": settings.SMS_SENDER},
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise SMSError(f"SMS provider unreachable: {exc}") from exc

        status = (payload.get("return") or {}).get("status")
        if status != 200:
            raise SMSError(f"SMS rejected: {payload.get('return')}")
        return payload


class SmsIrBackend(BaseSMSBackend):
    """SMS.ir — https://api.sms.ir/v1

    Two channels, deliberately kept apart:

    * `send` posts a free-text message on the account's own line. Used for
      order-status notices.
    * `send_verify` fills a template the shop has registered in the panel.
      One-time codes and the welcome greeting go this way: template messages
      ride service lines, so they reach customers who have blocked
      advertising SMS, and they are prioritised by the operators.

    Codes are returned by the API as a `status` field that is 1 on success;
    an HTTP 200 alone does not mean the message was accepted.
    """

    name = "smsir"
    BASE = "https://api.sms.ir/v1"

    # From the provider's table. Only the ones a caller can act on are named;
    # the rest fall through to the raw message.
    STATUS_TEXT = {
        10: "کلید وب‌سرویس نامعتبر است.",
        11: "کلید وب‌سرویس غیرفعال است.",
        12: "کلید وب‌سرویس محدود به آی‌پی‌های تعریف‌شده است.",
        13: "حساب کاربری غیرفعال است.",
        14: "حساب کاربری در حالت تعلیق است.",
        20: "تعداد درخواست بیشتر از حد مجاز است.",
        101: "شماره خط نامعتبر است.",
        102: "اعتبار پنل پیامک کافی نیست.",
        104: "شماره موبایل نادرست است.",
        113: "قالب پیامک یافت نشد.",
        114: "مقدار پارامتر بیش از ۲۵ کاراکتر است.",
        115: "شماره موبایل در لیست سیاه سامانه است.",
        116: "نام پارامتر قالب مقداردهی نشده است.",
    }

    def __init__(self):
        self.api_key = settings.SMSIR_API_KEY
        if not self.api_key:
            raise SMSError("SMSIR_API_KEY is not configured.")
        self.line_number = settings.SMSIR_LINE_NUMBER

    def _headers(self):
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-key": self.api_key,
        }

    def _post(self, path, payload):
        import time

        import requests

        started = time.monotonic()
        try:
            response = requests.post(
                f"{self.BASE}{path}",
                json=payload,
                headers=self._headers(),
                timeout=settings.SMSIR_TIMEOUT,
            )
        except Exception as exc:
            # Network-level: worth retrying, so it stays an SMSError.
            raise SMSError(f"SMS provider unreachable: {exc}") from exc

        # How long the provider took to accept the message. Logged because a
        # slow SMS has two very different causes that look identical from the
        # outside: a slow call here, or a fast accept and a slow delivery on
        # the operator's side. Only this number tells them apart.
        elapsed = time.monotonic() - started
        log = logger.warning if elapsed > 3 else logger.info
        log("SMS.ir %s accepted in %.2fs", path, elapsed)

        try:
            body = response.json()
        except ValueError:
            raise SMSError(
                f"SMS provider returned non-JSON (HTTP {response.status_code})."
            ) from None

        status = body.get("status")
        if status != 1:
            detail = self.STATUS_TEXT.get(status) or body.get("message") or "خطای نامشخص"
            # The provider's own message is kept alongside the translation: a
            # status the table does not know about is exactly the case where
            # the log has to be enough to diagnose from, without a redeploy.
            raise SMSError(
                f"SMS rejected (HTTP {response.status_code}, status {status}): "
                f"{detail} — {body.get('message')!r} on {path}"
            )

        return body.get("data") or {}

    def send(self, *, to, body):
        # The line number is typed as a number by the API; a quoted string is
        # rejected as an invalid line (status 101). Sent as text only if it is
        # not all digits, so a malformed setting still reaches the provider and
        # produces its own error rather than a TypeError here.
        line = int(self.line_number) if str(self.line_number).isdigit() else self.line_number
        payload = {
            "lineNumber": line,
            "messageText": body,
            "mobiles": [_normalise(to)],
        }
        return self._post("/send/bulk", payload)

    def send_verify(self, *, to, code, template_id=None, parameters=None):
        """Fill a registered template. `parameters` overrides the default,
        which sends the code under the configured parameter name."""
        template = template_id or settings.SMSIR_VERIFY_TEMPLATE_ID
        if not template:
            raise SMSError("SMSIR_VERIFY_TEMPLATE_ID is not configured.")

        if parameters is None:
            parameters = [{"name": settings.SMSIR_VERIFY_PARAM, "value": str(code)}]

        payload = {
            "mobile": _normalise(to),
            "templateId": int(template),
            "parameters": _clip(parameters),
        }
        return self._post("/send/verify", payload)


# The provider rejects the whole message with status 114 when any parameter is
# longer than this. Enforced here rather than at each call site: a caller that
# forgets loses the message entirely, and the failure only shows up in
# production against a name that happens to be long.
PARAM_MAX = 25


def _clip(parameters):
    """Trim every template parameter to the provider's limit."""
    return [
        {"name": p["name"], "value": str(p.get("value") or "")[:PARAM_MAX]}
        for p in parameters
    ]


def _normalise(number):
    """Reduce any form a customer types to what SMS.ir expects: 9121234567.

    The provider types mobile numbers as int64, so a leading zero is not part
    of the format and a number sent as 09121234567 is rejected. Accepts the
    forms that actually reach us — 0912…, +98912…, 98912…, 912… — and strips
    the country code and the trunk zero from all of them.

    Only SMS.ir uses this. Kavenegar wants the 0912… form and is passed the
    stored number unchanged.
    """
    # `digits_only`, not `str.isdigit()`: the latter is True for Persian and
    # Arabic-Indic numerals, so a number typed as ۰۹۱۲… would survive the
    # filter unchanged and reach the provider in a script it cannot read.
    digits = digits_only(number)
    if digits.startswith("0098"):
        digits = digits[4:]
    elif digits.startswith("98") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    return digits


_BACKENDS = {
    "console": ConsoleSMSBackend,
    "kavenegar": KavenegarSMSBackend,
    "smsir": SmsIrBackend,
}


def get_sms_backend(name=None):
    name = name or settings.SMS_BACKEND
    try:
        return _BACKENDS[name]()
    except KeyError as exc:
        raise SMSError(f"Unknown SMS backend: {name}") from exc


def send_sms(*, to, body):
    """Send one message. Raises SMSError so the calling task can retry."""
    if not to:
        raise SMSError("No phone number to send to.")
    return get_sms_backend().send(to=to, body=body)


def send_verify_sms(*, to, code, template_id=None, parameters=None):
    """Send a one-time code (or any template) through the verify channel."""
    if not to:
        raise SMSError("No phone number to send to.")
    return get_sms_backend().send_verify(
        to=to, code=code, template_id=template_id, parameters=parameters
    )
