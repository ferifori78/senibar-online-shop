"""Scheduled reports for the roastery.

These run under Celery Beat. Each is written to be safely re-runnable: a
missed 08:00 that fires at 08:40 produces the same report, and running it
twice sends the same figures rather than double-counting anything.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Count, F, Sum
from django.utils import timezone

from notifications.models import Notification

from .models import PEAK_DAYS, REST_DAYS, STALE_DAYS, RoastBatch

logger = logging.getLogger("senobar.reports")


def _line(label, value):
    return f"{label}: {value}"


@shared_task(name="reports.daily_roast_report", bind=True)
def daily_roast_report(self, for_date=None):
    """The 08:00 briefing: which batches were roasted today, and what is queued.

    `for_date` (an ISO date string) lets the report be re-run for a past day
    without pretending it is that day — useful when Beat was down.
    """
    from orders.models import GrindType, Order, OrderItem

    today = (
        timezone.datetime.fromisoformat(for_date).date()
        if for_date
        else timezone.localdate()
    )

    # --- Roasted today ---------------------------------------------------
    roasted_today = (
        RoastBatch.objects.filter(roast_date=today)
        .select_related("product", "roaster")
        .order_by("batch_code")
    )
    roasted_grams = roasted_today.aggregate(g=Sum("initial_grams"))["g"] or 0

    # --- What still needs roasting ---------------------------------------
    awaiting = Order.objects.awaiting_roast()
    roast_plan = list(
        OrderItem.objects.filter(order__in=awaiting)
        .values(name=F("product_name"))
        .annotate(grams=Sum(F("weight_grams") * F("quantity")), lines=Count("id"))
        .order_by("-grams")
    )
    plan_grams = sum(row["grams"] for row in roast_plan)

    # --- Grinding queue --------------------------------------------------
    grind_queue = list(
        OrderItem.objects.filter(order__status=Order.Status.ROASTING)
        .exclude(grind_type=GrindType.WHOLE)
        .values("grind_type")
        .annotate(grams=Sum(F("weight_grams") * F("quantity")))
        .order_by("-grams")
    )

    # --- Batches leaving their peak window -------------------------------
    leaving_peak = (
        RoastBatch.objects.filter(
            status=RoastBatch.Status.AVAILABLE,
            remaining_grams__gt=0,
            roast_date=today - timedelta(days=PEAK_DAYS),
        )
        .select_related("product")
    )

    # --- Compose ---------------------------------------------------------
    lines = [
        f"گزارش روزانه رست — {today}",
        "=" * 42,
        "",
        f"بچ‌های رست‌شده امروز: {roasted_today.count()} لات، {roasted_grams:,} گرم",
    ]

    if roasted_today:
        for batch in roasted_today:
            roaster = batch.roaster.display_name if batch.roaster else "—"
            lines.append(
                f"  · {batch.batch_code} — {batch.product.name} — "
                f"{batch.initial_grams:,}g — {batch.get_status_display()} — {roaster}"
            )
    else:
        lines.append("  (امروز هنوز بچی ثبت نشده است)")

    lines += ["", f"در انتظار رست: {awaiting.count()} سفارش، {plan_grams:,} گرم"]
    for row in roast_plan:
        lines.append(f"  · {row['name']}: {row['grams']:,}g ({row['lines']} خط)")
    if not roast_plan:
        lines.append("  (صف رست خالی است)")

    if grind_queue:
        lines += ["", "صف آسیاب:"]
        for row in grind_queue:
            lines.append(f"  · {row['grind_type']}: {row['grams']:,}g")

    if leaving_peak:
        lines += ["", f"امروز از اوج تازگی خارج می‌شوند ({PEAK_DAYS} روز):"]
        for batch in leaving_peak:
            lines.append(
                f"  · {batch.batch_code} — {batch.product.name} — "
                f"{batch.remaining_grams:,}g باقی مانده"
            )

    body = "\n".join(lines) + "\n"
    subject = f"صنوبر — گزارش رست {today}"

    recipients = settings.ROASTERY_REPORT_EMAILS
    key = f"roast_report:{today}"

    if Notification.already_sent(channel=Notification.Channel.EMAIL, dedupe_key=key):
        logger.info("Roast report for %s already sent", today)
        return {"date": str(today), "skipped": "already_sent"}

    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipients,
        fail_silently=False,
    )

    Notification.objects.create(
        channel=Notification.Channel.EMAIL,
        kind=Notification.Kind.ROAST_REPORT,
        status=Notification.Status.SENT,
        recipient=", ".join(recipients)[:254],
        subject=subject,
        body=body,
        dedupe_key=key,
    )

    logger.info("Roast report for %s sent to %s", today, recipients)

    return {
        "date": str(today),
        "roasted_batches": roasted_today.count(),
        "roasted_grams": roasted_grams,
        "awaiting_orders": awaiting.count(),
        "plan_grams": plan_grams,
        "leaving_peak": leaving_peak.count(),
        "recipients": recipients,
    }


@shared_task(name="reports.flag_stale_batches", bind=True)
def flag_stale_batches(self):
    """Withdraw batches past their sell-by window.

    Coffee does not become dangerous, it becomes disappointing — and a stale
    batch left `available` quietly keeps getting sold.
    """
    cutoff = timezone.localdate() - timedelta(days=STALE_DAYS)

    stale = RoastBatch.objects.filter(
        status=RoastBatch.Status.AVAILABLE, roast_date__lt=cutoff
    ).select_related("product")

    withdrawn = []
    for batch in stale:
        batch.status = RoastBatch.Status.WITHDRAWN
        batch.save(update_fields=["status", "updated_at"])
        withdrawn.append(
            {
                "batch_code": batch.batch_code,
                "product": batch.product.name,
                "remaining_grams": batch.remaining_grams,
                "days": batch.days_since_roast,
            }
        )

    if withdrawn:
        lines = [f"بچ‌های کهنه که از فروش خارج شدند (بیش از {STALE_DAYS} روز):", ""]
        lines += [
            f"  · {b['batch_code']} — {b['product']} — {b['remaining_grams']:,}g — "
            f"{b['days']} روز"
            for b in withdrawn
        ]
        send_mail(
            subject=f"صنوبر — {len(withdrawn)} بچ از فروش خارج شد",
            message="\n".join(lines) + "\n",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=settings.ROASTERY_REPORT_EMAILS,
            fail_silently=True,
        )
        logger.info("Withdrew %s stale batches", len(withdrawn))

    return {"withdrawn": len(withdrawn), "batches": withdrawn}


@shared_task(name="reports.rest_window_ready", bind=True)
def rest_window_ready(self):
    """Batches that finished resting today and may now be sold."""
    target = timezone.localdate() - timedelta(days=REST_DAYS)

    ready = RoastBatch.objects.filter(
        status=RoastBatch.Status.RESTING, roast_date__lte=target
    ).select_related("product")

    released = [b.batch_code for b in ready]
    ready.update(status=RoastBatch.Status.AVAILABLE)

    if released:
        logger.info("Released %s rested batches: %s", len(released), released)

    return {"released": len(released), "batches": released}
