"""Asynchronous notifications.

Every task here is idempotent: it records what it sent and skips a repeat of
the same event. That matters because CELERY_TASK_ACKS_LATE re-queues a task
whose worker died mid-run, so "exactly once" is not something the broker gives
us — the database has to.
"""

import logging

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail

from .models import Notification
from .providers import SMSError, send_sms, send_verify_sms

logger = logging.getLogger("senobar.notifications")

User = get_user_model()

# Retry on transient failures — an unreachable SMS gateway usually recovers.
RETRY_KWARGS = {
    "autoretry_for": (SMSError, ConnectionError, TimeoutError),
    "retry_backoff": 30,       # 30s, 60s, 120s…
    "retry_backoff_max": 600,
    "retry_jitter": True,
    "max_retries": 4,
}


def _deliver_email(*, user, kind, subject, body, dedupe_key="", recipient=None):
    """Send one email and log it. Returns the Notification, or None if the
    same event was already delivered."""
    address = recipient or (user.email if user else None)
    if not address:
        logger.warning("No email address for %s notification", kind)
        return None

    if Notification.already_sent(channel=Notification.Channel.EMAIL, dedupe_key=dedupe_key):
        logger.info("Skipping duplicate %s email for %s", kind, dedupe_key)
        return None

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[address],
            fail_silently=False,
        )
    except Exception as exc:
        Notification.objects.create(
            user=user, channel=Notification.Channel.EMAIL, kind=kind,
            status=Notification.Status.FAILED, recipient=address,
            subject=subject, body=body, error=str(exc)[:255], dedupe_key=dedupe_key,
        )
        raise

    return Notification.objects.create(
        user=user, channel=Notification.Channel.EMAIL, kind=kind,
        status=Notification.Status.SENT, recipient=address,
        subject=subject, body=body, dedupe_key=dedupe_key,
    )


def _deliver_sms(
    *, user, kind, body, dedupe_key="", recipient=None,
    template_id=None, parameters=None,
):
    """Send one SMS and log it. Missing phone numbers are not an error — most
    customers give an email only.

    With `template_id`, the message goes through the provider's verify channel
    instead of a plain send: template messages ride service lines, so they
    reach customers who have blocked advertising SMS. `body` is still recorded
    as what the customer will have seen, so the log stays readable.
    """
    number = recipient or (user.phone if user else None)
    if not number:
        return None

    if Notification.already_sent(channel=Notification.Channel.SMS, dedupe_key=dedupe_key):
        logger.info("Skipping duplicate %s SMS for %s", kind, dedupe_key)
        return None

    try:
        if template_id:
            send_verify_sms(
                to=number, code=None, template_id=template_id, parameters=parameters
            )
        else:
            # The bulk line is minutes-to-hours slower than the service line and
            # never reaches customers who have blocked advertising SMS, so every
            # message type registers a template. Landing here means one is not
            # configured — worth saying loudly, because the symptom is "the SMS
            # arrives very late" rather than an error anyone would notice.
            logger.warning(
                "%s SMS is falling back to the slow bulk line: no template id "
                "configured for it. Check the SMSIR_*_TEMPLATE_ID settings.",
                kind,
            )
            send_sms(to=number, body=body)
    except SMSError as exc:
        Notification.objects.create(
            user=user, channel=Notification.Channel.SMS, kind=kind,
            status=Notification.Status.FAILED, recipient=number,
            body=body, error=str(exc)[:255], dedupe_key=dedupe_key,
        )
        raise

    return Notification.objects.create(
        user=user, channel=Notification.Channel.SMS, kind=kind,
        status=Notification.Status.SENT, recipient=number,
        body=body, dedupe_key=dedupe_key,
    )


# ==========================================================================
# 1. Welcome, after registration
# ==========================================================================

WELCOME_EMAIL = """{name} عزیز، خوش آمدید.

حساب شما در صنوبر ساخته شد.

ما قهوه را پس از ثبت سفارش رست می‌کنیم، نه پیش از آن. یعنی آنچه به دستتان
می‌رسد چند روزه است، نه چند ماهه. تاریخ رست هر لات روی صفحه‌ی همان قهوه ثبت
است و در سفارش شما هم می‌آید.

فهرست قهوه‌ها: {url}/products

— صنوبر
"""

# The wording lives in the SMS.ir panel as a registered template; this mirrors
# it only so the notification log reads sensibly.
WELCOME_SMS = "{name} عزیز به خانواده صنوبر خوش آمدید"


@shared_task(name="notifications.send_welcome", bind=True, **RETRY_KWARGS)
def send_welcome(self, user_id):
    """Greet a new customer over email, and SMS if we have a number."""
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        # The account was deleted between signup and this task running.
        logger.warning("send_welcome: user %s no longer exists", user_id)
        return {"skipped": "user_missing"}

    name = user.display_name
    key = f"welcome:{user.pk}"

    email = _deliver_email(
        user=user,
        kind=Notification.Kind.WELCOME,
        subject="به صنوبر خوش آمدید",
        body=WELCOME_EMAIL.format(name=name, url=settings.FRONTEND_URL),
        dedupe_key=key,
    )
    # The template parameter is capped at 25 characters by the provider, and a
    # long display name would otherwise be rejected outright (status 114).
    contact = name[:25]
    sms = _deliver_sms(
        user=user,
        kind=Notification.Kind.WELCOME,
        body=WELCOME_SMS.format(name=contact),
        dedupe_key=key,
        template_id=settings.SMSIR_WELCOME_TEMPLATE_ID or None,
        parameters=[{"name": settings.SMSIR_WELCOME_PARAM, "value": contact}],
    )

    return {"user": user.pk, "email": bool(email), "sms": bool(sms)}


# ==========================================================================
# 2. Order status changed
# ==========================================================================

# What each stage means to the customer. Statuses the customer doesn't need to
# hear about (`ground`, an internal step) are deliberately absent.
STATUS_MESSAGES = {
    "roasting": (
        "سفارش {number} در حال رست است",
        "قهوه شما امروز رست می‌شود و پس از استراحت کوتاه ارسال خواهد شد.",
    ),
    "ground": (
        "سفارش {number} آسیاب شد",
        "قهوه شما با آسیاب انتخابی‌تان آماده شد و در حال بسته‌بندی است.",
    ),
    "packed": (
        "سفارش {number} بسته‌بندی شد",
        "سفارش شما بسته‌بندی شد و آماده تحویل به پست است.",
    ),
    "shipped": (
        "سفارش {number} ارسال شد",
        "سفارش شما تحویل پست شد.{tracking}",
    ),
    "delivered": (
        "سفارش {number} تحویل شد",
        "سفارش شما تحویل داده شد. نوش جان.",
    ),
    "cancelled": (
        "سفارش {number} لغو شد",
        "سفارش شما لغو شد. اگر مبلغی پرداخت شده باشد، طی ۷۲ ساعت بازگردانده می‌شود.",
    ),
    "refunded": (
        "سفارش {number} مسترد شد",
        "مبلغ سفارش شما مسترد شد.",
    ),
}

# The registered template says «سفارش شما در مرحله #ORDER_STATUS# است.», so the
# parameter is a stage name, not a sentence. Kept separate from the wording
# above, which is what the email says: these have to fit in 25 characters.
STATUS_STAGE = {
    "roasting": "رست",
    "ground": "آسیاب",
    "packed": "بسته‌بندی",
    "shipped": "ارسال",
    "delivered": "تحویل",
    "cancelled": "لغو",
    "refunded": "استرداد",
}


@shared_task(name="notifications.order_status_changed", bind=True, **RETRY_KWARGS)
def order_status_changed(self, order_id, new_status):
    """Tell a customer their order moved.

    The status is passed in rather than read off the order, so a notification
    describes the transition that actually happened even if the order has since
    moved on again.
    """
    from orders.models import Order

    try:
        order = Order.objects.select_related("user").get(pk=order_id)
    except Order.DoesNotExist:
        logger.warning("order_status_changed: order %s no longer exists", order_id)
        return {"skipped": "order_missing"}

    template = STATUS_MESSAGES.get(new_status)
    if template is None:
        # An internal step. Nothing to say.
        return {"skipped": "no_message_for_status", "status": new_status}

    subject_template, body_template = template
    tracking = ""
    if new_status == "shipped" and order.tracking_code:
        tracking = f" کد رهگیری: {order.tracking_code}"

    subject = subject_template.format(number=order.number)
    body = body_template.format(number=order.number, tracking=tracking)
    key = f"order:{order.number}:{new_status}"

    full_body = (
        f"{order.recipient_name} عزیز،\n\n{body}\n\n"
        f"پیگیری سفارش: {settings.FRONTEND_URL}/orders/{order.number}\n\n— صنوبر\n"
    )

    email = _deliver_email(
        user=order.user,
        kind=Notification.Kind.ORDER_STATUS,
        subject=subject,
        body=full_body,
        dedupe_key=key,
    )
    # Through the registered template when one is configured. The template
    # carries the order number, so a customer with several open orders can tell
    # which one moved; the tracking code has no room and stays in the email.
    template_id = settings.SMSIR_ORDER_TEMPLATE_ID or None
    stage = STATUS_STAGE.get(new_status, "")

    sms = None
    if stage:
        sms = _deliver_sms(
            user=order.user,
            kind=Notification.Kind.ORDER_STATUS,
            body=(
                f"سفارش {order.number} در مرحله {stage} است."
                if template_id
                else f"صنوبر: {subject}. {body}"
            ),
            dedupe_key=key,
            recipient=order.recipient_phone or None,
            template_id=template_id,
            parameters=[
                {"name": settings.SMSIR_ORDER_CODE_PARAM, "value": order.number},
                {"name": settings.SMSIR_ORDER_PARAM, "value": stage},
            ],
        )
    # A status with no short stage name has nothing to put in the template.
    # Skipping the SMS entirely is deliberate: clearing template_id instead
    # would quietly drop the message onto the slow bulk line rather than
    # sending nothing. The email still goes out either way.

    return {"order": order.number, "status": new_status, "email": bool(email), "sms": bool(sms)}


@shared_task(name="notifications.payment_received", bind=True, **RETRY_KWARGS)
def payment_received(self, order_id):
    """Confirm a payment landed and the order joined the roast queue."""
    from orders.models import Order

    try:
        order = Order.objects.select_related("user").get(pk=order_id)
    except Order.DoesNotExist:
        return {"skipped": "order_missing"}

    body = (
        f"{order.recipient_name} عزیز،\n\n"
        f"پرداخت سفارش {order.number} تأیید شد و سفارش شما در صف رست قرار گرفت.\n\n"
        f"مبلغ: {order.total_amount:,} تومان\n"
        f"پیگیری: {settings.FRONTEND_URL}/orders/{order.number}\n\n— صنوبر\n"
    )

    key = f"payment:{order.number}"

    email = _deliver_email(
        user=order.user,
        kind=Notification.Kind.PAYMENT_RECEIVED,
        subject=f"پرداخت سفارش {order.number} تأیید شد",
        body=body,
        dedupe_key=key,
    )
    # Payment is the moment a customer most wants confirmation, and many give
    # no email at all — the order-status texts would otherwise be the first
    # thing they ever hear about money that has already left their account.
    template_id = settings.SMSIR_PAYMENT_TEMPLATE_ID or None
    sms = _deliver_sms(
        user=order.user,
        kind=Notification.Kind.PAYMENT_RECEIVED,
        body=(
            f"سفارش {order.number} پرداختش تایید شده و اماده سفر شده."
            if template_id
            else f"صنوبر: پرداخت سفارش {order.number} تأیید شد "
            f"و سفارش شما در صف رست قرار گرفت."
        ),
        dedupe_key=key,
        recipient=order.recipient_phone or None,
        template_id=template_id,
        parameters=[
            {"name": settings.SMSIR_ORDER_CODE_PARAM, "value": order.number}
        ],
    )
    return {"order": order.number, "email": bool(email), "sms": bool(sms)}


@shared_task(name="notifications.ticket_replied", bind=True, **RETRY_KWARGS)
def ticket_replied(self, ticket_id, message_id):
    """Tell a customer that support answered."""
    from support.models import Ticket, TicketMessage

    try:
        ticket = Ticket.objects.select_related("user").get(pk=ticket_id)
        message = TicketMessage.objects.get(pk=message_id)
    except (Ticket.DoesNotExist, TicketMessage.DoesNotExist):
        return {"skipped": "missing"}

    # Internal notes are for us, not the customer.
    if message.is_internal:
        return {"skipped": "internal_note"}

    body = (
        f"{ticket.user.display_name} عزیز،\n\n"
        f"پشتیبانی صنوبر به تیکت «{ticket.subject}» پاسخ داد:\n\n"
        f"{message.body}\n\n"
        f"ادامه گفتگو: {settings.FRONTEND_URL}/support/{ticket.reference}\n\n— صنوبر\n"
    )

    key = f"ticket:{ticket.reference}:msg:{message.pk}"

    email = _deliver_email(
        user=ticket.user,
        kind=Notification.Kind.TICKET_REPLY,
        subject=f"پاسخ پشتیبانی — {ticket.reference}",
        body=body,
        dedupe_key=key,
    )
    # The reply itself is deliberately not in the SMS. A support answer runs to
    # paragraphs, which would cost several message parts, and a ticket may hold
    # order or address details that should stay behind a login rather than sit
    # in a lock-screen preview.
    template_id = settings.SMSIR_TICKET_REPLY_TEMPLATE_ID or None
    sms = _deliver_sms(
        user=ticket.user,
        kind=Notification.Kind.TICKET_REPLY,
        body=(
            f"تیکت شما به کد {ticket.reference} پاسخ گرفت."
            if template_id
            else f"صنوبر: پشتیبانی به تیکت {ticket.reference} پاسخ داد. "
            f"{settings.FRONTEND_URL}/support/{ticket.reference}"
        ),
        dedupe_key=key,
        recipient=_ticket_phone(ticket),
        template_id=template_id,
        parameters=[
            {"name": settings.SMSIR_TICKET_CODE_PARAM, "value": ticket.reference}
        ],
    )
    return {"ticket": ticket.reference, "email": bool(email), "sms": bool(sms)}


def _ticket_phone(ticket):
    """Where to text about a ticket.

    The account's own number, not the related order's recipient: an order can
    be a gift sent to someone else's phone, and that person has no business
    receiving the buyer's support conversation.
    """
    return (ticket.user.phone or None) if ticket.user_id else None


# ==========================================================================
# 4. Ticket status changed
# ==========================================================================

# Only the transitions a customer would want to hear about. A ticket moving to
# PENDING is not among them: that happens because support replied, and
# `ticket_replied` has already said so — two texts for one event.
TICKET_STATUS_MESSAGES = {
    "closed": (
        "تیکت {reference} بسته شد",
        "پشتیبانی این گفتگو را بسته شده اعلام کرد. اگر موضوع هنوز حل نشده، "
        "پاسخ شما در همین تیکت دوباره آن را باز می‌کند.",
    ),
    "open": (
        "تیکت {reference} دوباره باز شد",
        "این گفتگو دوباره باز شد و پشتیبانی آن را بررسی می‌کند.",
    ),
}

# For «تیکت #TICKET_CODE# به وضعیت #TICKET_STATUS# تغییر کرد.» — one word each,
# inside the 25-character parameter limit.
TICKET_STAGE = {"closed": "بسته", "open": "باز"}


@shared_task(name="notifications.ticket_status_changed", bind=True, **RETRY_KWARGS)
def ticket_status_changed(self, ticket_id, new_status, actor_id=None, at=None):
    """Tell a customer their ticket was closed or reopened.

    `actor_id` is the account that made the change. When the customer did it
    themselves — reopening their own ticket by replying — there is nothing to
    tell them, and the status is passed in rather than read off the ticket so
    the message describes the transition that happened.

    `at` stamps the dedupe key. A ticket can legitimately be closed and
    reopened several times, and a key of ticket+status alone would silence
    every round after the first while still letting a retried task through.
    """
    from support.models import Ticket

    try:
        ticket = Ticket.objects.select_related("user").get(pk=ticket_id)
    except Ticket.DoesNotExist:
        logger.warning("ticket_status_changed: ticket %s no longer exists", ticket_id)
        return {"skipped": "ticket_missing"}

    if actor_id is not None and actor_id == ticket.user_id:
        return {"skipped": "customer_own_action"}

    template = TICKET_STATUS_MESSAGES.get(new_status)
    if template is None:
        return {"skipped": "no_message_for_status", "status": new_status}

    subject_template, body_template = template
    subject = subject_template.format(reference=ticket.reference)
    body = body_template.format(reference=ticket.reference)
    key = f"ticket:{ticket.reference}:status:{new_status}:{at or ''}"

    full_body = (
        f"{ticket.user.display_name} عزیز،\n\n"
        f"موضوع: {ticket.subject}\n\n{body}\n\n"
        f"مشاهده تیکت: {settings.FRONTEND_URL}/support/{ticket.reference}\n\n— صنوبر\n"
    )

    email = _deliver_email(
        user=ticket.user,
        kind=Notification.Kind.TICKET_STATUS,
        subject=subject,
        body=full_body,
        dedupe_key=key,
    )
    stage = TICKET_STAGE.get(new_status, "")
    template_id = settings.SMSIR_TICKET_STATUS_TEMPLATE_ID or None

    # As above: no stage word means no SMS at all, rather than a fallback onto
    # the bulk line. Today TICKET_STATUS_MESSAGES gates the same two statuses,
    # so this cannot fire — but the tables are separate and may drift.
    sms = None
    if stage:
        sms = _deliver_sms(
            user=ticket.user,
            kind=Notification.Kind.TICKET_STATUS,
            body=(
                f"تیکت {ticket.reference} به وضعیت {stage} تغییر کرد."
                if template_id
                else f"صنوبر: {subject}."
            ),
            dedupe_key=key,
            recipient=_ticket_phone(ticket),
            template_id=template_id,
            parameters=[
                {"name": settings.SMSIR_TICKET_CODE_PARAM, "value": ticket.reference},
                {"name": settings.SMSIR_TICKET_STATUS_PARAM, "value": stage},
            ],
        )

    return {
        "ticket": ticket.reference,
        "status": new_status,
        "email": bool(email),
        "sms": bool(sms),
    }


@shared_task(name="notifications.cleanup_old", bind=True)
def cleanup_old(self, days=180):
    """Trim the delivery log. Kept long enough to answer "did you tell me?"."""
    from datetime import timedelta

    from django.utils import timezone

    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = Notification.objects.filter(created_at__lt=cutoff).delete()
    return {"deleted": deleted}
