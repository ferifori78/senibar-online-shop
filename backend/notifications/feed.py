"""The shop's Telegram feed: what gets posted, and when.

Four things reach the channel immediately — an order, a payment, a ticket, a
new customer — because each is a thing the roaster may want to act on within
minutes. Site traffic is summarised on a schedule instead, with one exception:
a product page that suddenly spikes is worth interrupting for.

Every task swallows its own failures. The feed is a convenience; a channel
that is misconfigured, rate-limited or simply down must never stop an order
being placed.
"""

import logging

from celery import shared_task
from django.conf import settings
from django.db.models import Count
from django.utils import timezone

from .models import Notification, SiteVisit
from .telegram import TelegramError, escape, is_configured, send

logger = logging.getLogger("senobar.telegram")


def _post(text, *, kind_key, silent=False):
    """Send one feed message and record it, at most once per event.

    The Notification row is what makes this idempotent: CELERY_TASK_ACKS_LATE
    re-runs a task whose worker died, and the roaster should not see the same
    order twice.
    """
    if not is_configured():
        return False

    if Notification.already_sent(
        channel=Notification.Channel.TELEGRAM, dedupe_key=kind_key
    ):
        logger.info("Skipping duplicate feed post %s", kind_key)
        return False

    try:
        send(text, silent=silent)
    except TelegramError as exc:
        logger.error("Feed post %s failed: %s", kind_key, exc)
        Notification.objects.create(
            channel=Notification.Channel.TELEGRAM,
            kind=Notification.Kind.TELEGRAM_FEED,
            status=Notification.Status.FAILED,
            recipient=str(settings.TELEGRAM_CHAT_ID)[:254],
            body=text[:2000],
            error=str(exc)[:255],
            dedupe_key=kind_key,
        )
        return False

    Notification.objects.create(
        channel=Notification.Channel.TELEGRAM,
        kind=Notification.Kind.TELEGRAM_FEED,
        status=Notification.Status.SENT,
        recipient=str(settings.TELEGRAM_CHAT_ID)[:254],
        body=text[:2000],
        dedupe_key=kind_key,
    )
    return True


# The models' own choice labels are English, because the site never renders
# them — it has its own Persian strings per view. The feed is read by a
# Persian speaker, so it carries its own.
ORDER_STATE = {
    "pending": "در انتظار پرداخت",
    "paid": "پرداخت شد",
    "roasting": "در حال رست",
    "ground": "آسیاب شد",
    "packed": "بسته‌بندی شد",
    "shipped": "ارسال شد",
    "delivered": "تحویل شد",
    "cancelled": "لغو شد",
    "refunded": "مسترد شد",
}

TICKET_STATE = {
    "open": "باز",
    "pending": "در انتظار پاسخ مشتری",
    "closed": "بسته",
}


def _money(amount):
    """Rial stored, toman spoken — the way prices are quoted in the shop."""
    try:
        return f"{int(amount) // 10:,} تومان"
    except (TypeError, ValueError):
        return "—"


# ==========================================================================
# Orders
# ==========================================================================

@shared_task(name="feed.order_placed", bind=True, max_retries=0)
def order_placed(self, order_id):
    """A new order landed."""
    from orders.models import Order

    try:
        order = Order.objects.prefetch_related("items").get(pk=order_id)
    except Order.DoesNotExist:
        return {"skipped": "order_missing"}

    lines = [
        f"*سفارش تازه* — `{escape(order.number)}`",
        "",
        f"👤 {escape(order.recipient_name)}",
        f"📞 `{escape(order.recipient_phone)}`",
        f"📍 {escape(order.province)}، {escape(order.city)}",
        f"     {escape(order.street_address)}",
        f"     کد پستی: `{escape(order.postal_code)}`",
        "",
    ]

    for item in order.items.all():
        grind = item.get_grind_type_display()
        lines.append(
            f"• {escape(item.product_name)} — "
            f"{escape(item.weight_grams)}g × {escape(item.quantity)} "
            f"\\({escape(grind)}\\)"
        )

    lines += [
        "",
        f"جمع: *{escape(_money(order.total_amount))}*",
        f"پرداخت: {escape(order.get_payment_status_display())}",
    ]
    if order.customer_note:
        lines += ["", f"📝 {escape(order.customer_note)}"]

    return {
        "posted": _post("\n".join(lines), kind_key=f"feed:order:{order.number}")
    }


@shared_task(name="feed.payment_confirmed", bind=True, max_retries=0)
def payment_confirmed(self, order_id):
    """Money actually arrived — the moment the shop owes coffee."""
    from orders.models import Order

    try:
        order = Order.objects.get(pk=order_id)
    except Order.DoesNotExist:
        return {"skipped": "order_missing"}

    text = "\n".join([
        f"*پرداخت تأیید شد* — `{escape(order.number)}`",
        "",
        f"👤 {escape(order.recipient_name)}",
        f"مبلغ: *{escape(_money(order.total_amount))}*",
    ])
    return {"posted": _post(text, kind_key=f"feed:payment:{order.number}")}


@shared_task(name="feed.order_status_changed", bind=True, max_retries=0)
def order_status_changed(self, order_id, new_status, actor_name=""):
    """An order moved along the board.

    The status is passed in rather than read off the order, so the message
    describes the transition that happened even if the order has since moved
    on again.
    """
    from orders.models import Order

    try:
        order = Order.objects.get(pk=order_id)
    except Order.DoesNotExist:
        return {"skipped": "order_missing"}

    label = ORDER_STATE.get(new_status, new_status)

    lines = [
        f"*وضعیت سفارش* — `{escape(order.number)}`",
        "",
        f"👤 {escape(order.recipient_name)}",
        f"مرحله: *{escape(label)}*",
    ]
    if new_status == "shipped" and order.tracking_code:
        lines.append(f"کد رهگیری: `{escape(order.tracking_code)}`")
    if actor_name:
        lines.append(f"توسط: {escape(actor_name)}")

    # Keyed by order and status, so a retried task cannot repeat itself.
    key = f"feed:order:{order.number}:{new_status}"
    return {"posted": _post("\n".join(lines), kind_key=key)}


# ==========================================================================
# Support
# ==========================================================================

@shared_task(name="feed.ticket_opened", bind=True, max_retries=0)
def ticket_opened(self, ticket_id):
    from support.models import Ticket

    try:
        ticket = Ticket.objects.select_related("user").get(pk=ticket_id)
    except Ticket.DoesNotExist:
        return {"skipped": "ticket_missing"}

    first = ticket.messages.filter(is_internal=False).order_by("created_at").first()
    body = (first.body if first else "")[:400]

    lines = [
        f"*تیکت تازه* — `{escape(ticket.reference)}`",
        "",
        f"👤 {escape(ticket.user.display_name)}",
        f"موضوع: {escape(ticket.subject)}",
        f"دسته: {escape(ticket.get_topic_display())} — "
        f"اولویت: {escape(ticket.get_priority_display())}",
    ]
    if body:
        lines += ["", f"_{escape(body)}_"]

    return {
        "posted": _post("\n".join(lines), kind_key=f"feed:ticket:{ticket.reference}")
    }


@shared_task(name="feed.customer_replied", bind=True, max_retries=0)
def customer_replied(self, ticket_id, message_id):
    """A customer answered an open ticket — the ball is back with support."""
    from support.models import Ticket, TicketMessage

    try:
        ticket = Ticket.objects.select_related("user").get(pk=ticket_id)
        message = TicketMessage.objects.get(pk=message_id)
    except (Ticket.DoesNotExist, TicketMessage.DoesNotExist):
        return {"skipped": "missing"}

    if message.is_internal:
        return {"skipped": "internal_note"}

    text = "\n".join([
        f"*پاسخ مشتری* — `{escape(ticket.reference)}`",
        "",
        f"👤 {escape(ticket.user.display_name)}",
        f"_{escape(message.body[:400])}_",
    ])
    return {
        "posted": _post(
            text, kind_key=f"feed:ticket:{ticket.reference}:msg:{message.pk}"
        )
    }


@shared_task(name="feed.ticket_status_changed", bind=True, max_retries=0)
def ticket_status_changed(self, ticket_id, new_status, actor_name="", at=""):
    """A ticket was closed, reopened, or handed to someone.

    `at` stamps the dedupe key: a ticket can legitimately go round the
    close/reopen loop more than once, and a key of ticket+status alone would
    silence every round after the first.
    """
    from support.models import Ticket

    try:
        ticket = Ticket.objects.select_related("user", "assigned_to").get(pk=ticket_id)
    except Ticket.DoesNotExist:
        return {"skipped": "ticket_missing"}

    # The model's own choice labels are English (`Closed`, `Open`) — the site
    # never renders them, so translating them was never needed. The feed is
    # read by a Persian speaker, so it uses Persian words.
    label = TICKET_STATE.get(new_status, new_status)

    lines = [
        f"*وضعیت تیکت* — `{escape(ticket.reference)}`",
        "",
        f"👤 {escape(ticket.user.display_name)}",
        f"موضوع: {escape(ticket.subject)}",
        f"وضعیت: *{escape(label)}*",
    ]
    if ticket.assigned_to:
        lines.append(f"مسئول: {escape(ticket.assigned_to.display_name)}")
    if actor_name:
        lines.append(f"توسط: {escape(actor_name)}")

    key = f"feed:ticket:{ticket.reference}:status:{new_status}:{at}"
    return {"posted": _post("\n".join(lines), kind_key=key)}


# ==========================================================================
# Accounts
# ==========================================================================

@shared_task(name="feed.customer_joined", bind=True, max_retries=0)
def customer_joined(self, user_id):
    from django.contrib.auth import get_user_model

    try:
        user = get_user_model().objects.get(pk=user_id)
    except get_user_model().DoesNotExist:
        return {"skipped": "user_missing"}

    if user.is_staff:
        return {"skipped": "staff"}

    lines = [
        "*مشتری تازه*",
        "",
        f"👤 {escape(user.display_name)}",
    ]
    if user.phone:
        lines.append(f"📞 `{escape(user.phone)}`")
    # The placeholder address a phone-only signup gets is noise, not information.
    if user.email and not user.email.endswith(".invalid"):
        lines.append(f"✉️ `{escape(user.email)}`")

    return {"posted": _post("\n".join(lines), kind_key=f"feed:user:{user.pk}")}


# ==========================================================================
# Traffic
# ==========================================================================

@shared_task(name="feed.traffic_digest", bind=True, max_retries=0)
def traffic_digest(self):
    """One summary per window, instead of a message per page view.

    Silent by default: this arrives on the hour and should not buzz a phone.
    """
    if not is_configured():
        return {"skipped": "not_configured"}

    minutes = settings.TELEGRAM_DIGEST_MINUTES
    now = timezone.now()
    since = now - timezone.timedelta(minutes=minutes)

    visits = SiteVisit.objects.filter(created_at__gte=since, created_at__lt=now)
    total = visits.count()
    if not total:
        # Nothing happened. Saying so every hour would train the roaster to
        # ignore the channel.
        return {"skipped": "no_traffic"}

    unique = visits.values("visitor_hash").distinct().count()
    signed_in = visits.filter(is_authenticated=True).count()

    top = (
        visits.values("path")
        .annotate(n=Count("id"))
        .order_by("-n")[:5]
    )
    sources = (
        visits.exclude(referrer="")
        .values("referrer")
        .annotate(n=Count("id"))
        .order_by("-n")[:3]
    )

    lines = [
        f"*خلاصه‌ی {escape(minutes)} دقیقه‌ی گذشته*",
        "",
        f"بازدید: *{escape(total)}*  —  بازدیدکننده: *{escape(unique)}*",
    ]
    if signed_in:
        lines.append(f"وارد شده: {escape(signed_in)}")

    lines += ["", "*پربازدیدترین:*"]
    for row in top:
        lines.append(f"  `{escape(row['path'])}` — {escape(row['n'])}")

    if sources:
        lines += ["", "*از کجا آمدند:*"]
        for row in sources:
            lines.append(f"  {escape(row['referrer'][:60])} — {escape(row['n'])}")

    # Keyed by the window, so a retried task cannot post the same hour twice.
    key = f"feed:digest:{since:%Y%m%d%H%M}"
    return {"posted": _post("\n".join(lines), kind_key=key, silent=True)}


@shared_task(name="feed.trending_product", bind=True, max_retries=0)
def trending_product(self):
    """Interrupt the digest when one product page suddenly spikes.

    The threshold is per window and per product, so this fires when something
    is genuinely being looked at — a mention somewhere, or a link that landed.
    """
    if not is_configured():
        return {"skipped": "not_configured"}

    minutes = settings.TELEGRAM_DIGEST_MINUTES
    since = timezone.now() - timezone.timedelta(minutes=minutes)

    hot = (
        SiteVisit.objects.filter(created_at__gte=since, path__startswith="/products/")
        .exclude(path="/products/")
        .values("path")
        .annotate(n=Count("id"))
        .filter(n__gte=settings.TELEGRAM_TRENDING_VIEWS)
        .order_by("-n")
        .first()
    )
    if not hot:
        return {"skipped": "nothing_trending"}

    text = "\n".join([
        "*یک صفحه دارد داغ می‌شود*",
        "",
        f"`{escape(hot['path'])}`",
        f"{escape(hot['n'])} بازدید در {escape(minutes)} دقیقه",
    ])
    # Once per product per window, not once per check.
    key = f"feed:trending:{hot['path']}:{since:%Y%m%d%H}"
    return {"posted": _post(text, kind_key=key)}


@shared_task(name="feed.sweep_visits", bind=True, max_retries=0)
def sweep_visits(self):
    """Trim the visit table. These rows exist to be counted, not kept."""
    cutoff = timezone.now() - timezone.timedelta(
        days=settings.SITE_VISIT_RETENTION_DAYS
    )
    deleted, _ = SiteVisit.objects.filter(created_at__lt=cutoff).delete()
    return {"deleted": deleted}
