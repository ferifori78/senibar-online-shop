"""Login and registration by one-time code.

The password flow in `views.py` is untouched: this is a second door into the
same accounts, not a replacement. A customer who signed up with an email keeps
that login, and the admin panel still needs it.
"""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from .otp import OTPError, is_valid_phone, issue, normalise_phone, verify
from .views import issue_tokens

logger = logging.getLogger("senobar.accounts")
User = get_user_model()


class OTPRequestThrottle(AnonRateThrottle):
    """A ceiling per IP, on top of the per-number limit in `otp.issue`.

    The per-number limit stops one customer being spammed; this stops one
    machine walking through many numbers to burn the shop's SMS credit.
    """

    scope = "otp"


def _client_ip(request):
    # Behind nginx, so the forwarded header is the real client. Only the first
    # entry is ours — the rest can be forged by the caller.
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


@api_view(["POST"])
@permission_classes((AllowAny,))
@throttle_classes([OTPRequestThrottle])
def request_code(request):
    """Send a login code to a phone number."""
    phone = normalise_phone(request.data.get("phone"))

    if not is_valid_phone(phone):
        return Response(
            {"phone": "شماره موبایل باید ۱۱ رقم و با ۰۹ شروع شود."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        otp, raw = issue(phone, ip=_client_ip(request))
    except OTPError as exc:
        return Response(
            {"detail": exc.message, "retry_after": exc.retry_after},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    # Sent inline rather than through Celery: the customer is staring at the
    # screen waiting for it, and a queued task that fails silently would leave
    # them on a code entry form with no code coming.
    from notifications.providers import SMSError, send_verify_sms

    try:
        send_verify_sms(to=phone, code=raw)
    except SMSError as exc:
        logger.error("OTP send failed for %s: %s", phone, exc)
        # The row stays; the customer can ask again once the resend window
        # passes. Deleting it here would let a broken provider be used to
        # bypass the rate limit.
        return Response(
            {"detail": "ارسال پیامک ناموفق بود. کمی بعد دوباره تلاش کنید."},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    return Response(
        {
            # Whether this number already has an account, so the client can
            # ask a new customer for their name on the next screen.
            "is_new": not User.objects.filter(phone=phone).exists(),
            "expires_in": (otp.expires_at - otp.created_at).seconds,
            # So the client can disable its resend button for exactly as long
            # as the server will refuse anyway.
            "resend_after": settings.OTP_RESEND_SECONDS,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes((AllowAny,))
def verify_code(request):
    """Exchange a correct code for tokens, creating the account if new."""
    phone = normalise_phone(request.data.get("phone"))
    code = str(request.data.get("code") or "").strip()

    if not is_valid_phone(phone):
        return Response(
            {"phone": "شماره موبایل نامعتبر است."}, status=status.HTTP_400_BAD_REQUEST
        )
    if not code:
        return Response({"code": "کد را وارد کنید."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        verify(phone, code)
    except OTPError as exc:
        return Response({"detail": exc.message}, status=status.HTTP_400_BAD_REQUEST)

    user, created = _get_or_create_user(phone, request.data.get("name"))

    if not user.is_active:
        # Checked after the code, so a disabled account cannot be probed by
        # the difference in response.
        return Response(
            {"detail": "این حساب غیرفعال است. با پشتیبانی تماس بگیرید."},
            status=status.HTTP_403_FORBIDDEN,
        )

    payload = issue_tokens(user)
    payload["created"] = created
    return Response(payload, status=status.HTTP_200_OK)


def _get_or_create_user(phone, name=None):
    """Find the account for a verified number, or make one.

    `phone` is not unique on the user model — an email-registered customer may
    have typed the same number — so the newest match wins rather than the
    query raising. Picking deterministically matters: an ambiguous login that
    sometimes lands in a different account is worse than either choice.
    """
    existing = User.objects.filter(phone=phone).order_by("-date_joined").first()
    if existing:
        return existing, False

    with transaction.atomic():
        # The model requires a unique email; a phone-only customer has none,
        # so a placeholder on an unroutable domain stands in. `.invalid` is
        # reserved by RFC 2606 precisely so it can never be delivered to.
        user = User.objects.create_user(
            email=f"{phone}@phone.senobar.invalid",
            password=None,          # unusable password: this account logs in by code
            phone=phone,
            first_name=(name or "").strip()[:60],
        )
    return user, True
