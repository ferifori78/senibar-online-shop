"""Housekeeping for orders."""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("senobar.orders")

# How long an unpaid order may hold its place before we let it go.
ABANDONED_AFTER_HOURS = 24


@shared_task(name="orders.release_abandoned_payments", bind=True)
def release_abandoned_payments(self, hours=ABANDONED_AFTER_HOURS):
    """Cancel orders that were never paid for.

    A customer who opens the gateway and walks away leaves an order sitting in
    `pending`. It holds no stock (reservation happens on payment), but it
    clutters the roast queue and the dashboard's counts.
    """
    from .models import Order

    cutoff = timezone.now() - timedelta(hours=hours)

    abandoned = Order.objects.filter(
        status=Order.Status.PENDING,
        payment_status=Order.PaymentStatus.UNPAID,
        placed_at__lt=cutoff,
    )

    cancelled = []
    for order in abandoned:
        try:
            order.transition_to(
                Order.Status.CANCELLED,
                note=f"Automatically cancelled: unpaid for more than {hours} hours.",
            )
            cancelled.append(order.number)
        except ValueError:
            # Someone moved it in the meantime; leave it alone.
            logger.info("Skipped %s — no longer cancellable", order.number)

    if cancelled:
        logger.info("Cancelled %s abandoned orders: %s", len(cancelled), cancelled)

    return {"cancelled": len(cancelled), "orders": cancelled}
