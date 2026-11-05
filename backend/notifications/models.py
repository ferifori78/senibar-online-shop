from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Notification(models.Model):
    """A record of one message we tried to deliver.

    Two jobs: an audit trail ("did we tell them the order shipped?"), and
    de-duplication — CELERY_TASK_ACKS_LATE means a task can run twice after a
    worker dies, and a customer should not get the same SMS twice.
    """

    class Channel(models.TextChoices):
        EMAIL = "email", _("Email")
        SMS = "sms", _("SMS")
        # Goes to the shop's own channel, never to a customer.
        TELEGRAM = "telegram", _("Telegram")

    class Kind(models.TextChoices):
        WELCOME = "welcome", _("Welcome")
        ORDER_STATUS = "order_status", _("Order status changed")
        PAYMENT_RECEIVED = "payment_received", _("Payment received")
        TICKET_REPLY = "ticket_reply", _("Support replied")
        TICKET_STATUS = "ticket_status", _("Ticket status changed")
        ROAST_REPORT = "roast_report", _("Daily roast report")
        TELEGRAM_FEED = "telegram_feed", _("Telegram channel post")

    class Status(models.TextChoices):
        SENT = "sent", _("Sent")
        FAILED = "failed", _("Failed")
        SKIPPED = "skipped", _("Skipped")

    user = models.ForeignKey(
        "accounts.CustomUser", on_delete=models.CASCADE, related_name="notifications",
        null=True, blank=True, verbose_name=_("recipient"),
    )
    channel = models.CharField(_("channel"), max_length=16, choices=Channel.choices)
    kind = models.CharField(_("kind"), max_length=32, choices=Kind.choices, db_index=True)
    status = models.CharField(
        _("status"), max_length=16, choices=Status.choices, default=Status.SENT
    )

    recipient = models.CharField(
        _("recipient address"), max_length=254,
        help_text=_("Email address or phone number, as sent."),
    )
    subject = models.CharField(_("subject"), max_length=200, blank=True)
    body = models.TextField(_("body"), blank=True)
    error = models.CharField(_("error"), max_length=255, blank=True)

    # What this notification was about, e.g. "order:SB-260830-4F2A:shipped".
    # Unique per kind, so a retried task recognises work it already did.
    dedupe_key = models.CharField(
        _("dedupe key"), max_length=120, blank=True, db_index=True,
        help_text=_("Identifies the event; a repeat with the same key is skipped."),
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("notification")
        verbose_name_plural = _("notifications")
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["user", "-created_at"])]
        constraints = [
            models.UniqueConstraint(
                fields=["channel", "dedupe_key"],
                condition=models.Q(dedupe_key__gt="", status="sent"),
                name="unique_sent_notification_per_event",
            )
        ]

    def __str__(self):
        return f"{self.get_kind_display()} -> {self.recipient} ({self.status})"

    @classmethod
    def already_sent(cls, *, channel, dedupe_key):
        if not dedupe_key:
            return False
        return cls.objects.filter(
            channel=channel, dedupe_key=dedupe_key, status=cls.Status.SENT
        ).exists()


class SiteVisit(models.Model):
    """One page view, kept only long enough to be counted.

    Rows here are cheap and numerous, so the table carries no foreign keys and
    no indexes beyond the one the digest actually queries. A nightly sweep
    trims it — this is a counter, not an analytics warehouse.
    """

    path = models.CharField(_("path"), max_length=200)
    # A short hash of IP + user agent, not the address itself. Enough to count
    # distinct visitors within an hour; not enough to identify anyone later,
    # and nothing to leak if the table is dumped.
    visitor_hash = models.CharField(_("visitor"), max_length=32, db_index=True)
    referrer = models.CharField(_("referrer"), max_length=200, blank=True)
    is_authenticated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("site visit")
        verbose_name_plural = _("site visits")
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["-created_at", "path"])]

    def __str__(self):
        return f"{self.path} @ {self.created_at:%Y-%m-%d %H:%M}"
