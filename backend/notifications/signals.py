"""Where notifications get triggered.

Queued with `transaction.on_commit` throughout: a task dispatched inside an
open transaction can reach a worker before the row it describes is visible,
and the worker then reads a user or order that "does not exist".
"""

import logging

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger("senobar.notifications")


@receiver(post_save, sender=settings.AUTH_USER_MODEL, dispatch_uid="senobar_welcome")
def queue_welcome(sender, instance, created, **kwargs):
    """Greet a new customer. Staff accounts get nothing."""
    if not created or instance.is_staff:
        return

    from .feed import customer_joined
    from .tasks import send_welcome

    def queue():
        # `delay()` reaches the broker, and an unreachable Redis raises rather
        # than returning. Inside on_commit that exception propagates out of
        # the request that created the account — which would turn a correct
        # OTP code, or a valid registration, into a 500. The greeting is a
        # nicety; signing up is not.
        try:
            send_welcome.delay(instance.pk)
        except Exception as exc:
            logger.error("Welcome message not queued for %s: %s", instance.pk, exc)

        # Caught separately: a failure here must not stop the greeting above,
        # and neither may stop the registration.
        try:
            customer_joined.delay(instance.pk)
        except Exception as exc:
            logger.error("Feed post not queued for user %s: %s", instance.pk, exc)

    transaction.on_commit(queue)
