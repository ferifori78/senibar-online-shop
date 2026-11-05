"""Issuing and checking one-time codes.

Kept out of the views so the rules — how long a code lives, how often one may
be asked for, how many guesses it survives — are in one readable place rather
than spread through request handling.
"""

import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.utils import timezone

from config.digits import digits_only

from .models import PhoneOTP


class OTPError(Exception):
    """Something the customer should be told about, in Persian."""

    def __init__(self, message, *, retry_after=None):
        super().__init__(message)
        self.message = message
        # Seconds until the next attempt is allowed, when that is the reason.
        self.retry_after = retry_after


def normalise_phone(raw):
    """Reduce the forms customers type to a single stored shape: 09xxxxxxxxx.

    Without this, `09121234567`, `+989121234567` and `۰۹۱۲۱۲۳۴۵۶۷` would be
    three different accounts for one person.
    """
    digits = digits_only(raw or "")
    if digits.startswith("98") and len(digits) == 12:
        digits = "0" + digits[2:]
    elif digits.startswith("9") and len(digits) == 10:
        digits = "0" + digits
    return digits


def is_valid_phone(phone):
    """An Iranian mobile number: 11 digits beginning 09."""
    return len(phone) == 11 and phone.startswith("09") and phone.isdigit()


def generate_code():
    """A numeric code of the configured length.

    `secrets`, not `random`: the latter is seeded predictably and its output
    can be reconstructed from earlier values, which for a login code means an
    attacker who requests a few codes could compute someone else's.
    """
    upper = 10 ** settings.OTP_CODE_LENGTH
    return str(secrets.randbelow(upper)).zfill(settings.OTP_CODE_LENGTH)


def issue(phone, *, ip=None, purpose=PhoneOTP.Purpose.LOGIN):
    """Create and store a code for `phone`, returning (otp, raw_code).

    Raises OTPError when the number has asked too often. The caller sends the
    raw code; only its hash is kept, so this is the one moment it exists.
    """
    now = timezone.now()

    recent = PhoneOTP.objects.filter(
        phone=phone, purpose=purpose, created_at__gte=now - timedelta(hours=1)
    )

    # Resend throttle first: it produces the more useful message of the two,
    # and it is the limit an ordinary impatient customer actually hits.
    latest = recent.order_by("-created_at").first()
    if latest:
        elapsed = (now - latest.created_at).total_seconds()
        wait = settings.OTP_RESEND_SECONDS - elapsed
        if wait > 0:
            raise OTPError(
                f"برای دریافت کد جدید {int(wait)} ثانیه صبر کنید.",
                retry_after=int(wait),
            )

    if recent.count() >= settings.OTP_MAX_PER_HOUR:
        raise OTPError(
            "تعداد درخواست کد بیش از حد مجاز است. یک ساعت دیگر دوباره تلاش کنید.",
            retry_after=3600,
        )

    raw = generate_code()
    otp = PhoneOTP.objects.create(
        phone=phone,
        code_hash=make_password(raw),
        purpose=purpose,
        requested_ip=ip,
        expires_at=now + timedelta(seconds=settings.OTP_TTL_SECONDS),
    )
    return otp, raw


def verify(phone, code, *, purpose=PhoneOTP.Purpose.LOGIN):
    """Check a submitted code against the newest live one for this number.

    Only the newest is considered: asking for a second code must invalidate
    the first in practice, or two codes would be usable at once and the
    rate limit would buy an attacker more guesses rather than fewer.
    """
    otp = (
        PhoneOTP.objects.filter(phone=phone, purpose=purpose, is_used=False)
        .order_by("-created_at")
        .first()
    )

    if otp is None:
        raise OTPError("کدی برای این شماره صادر نشده است. دوباره درخواست کنید.")

    if otp.is_expired:
        raise OTPError("این کد منقضی شده است. کد جدیدی درخواست کنید.")

    if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
        raise OTPError("تعداد تلاش‌های نادرست بیش از حد مجاز است. کد جدیدی بگیرید.")

    if not otp.check_code(code):
        left = max(0, settings.OTP_MAX_ATTEMPTS - otp.attempts)
        if left == 0:
            raise OTPError("کد نادرست است و این کد باطل شد. کد جدیدی بگیرید.")
        raise OTPError(f"کد وارد شده نادرست است. {left} تلاش باقی مانده است.")

    return otp
