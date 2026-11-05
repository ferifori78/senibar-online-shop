from decimal import Decimal

from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _


class Payment(models.Model):
    """One attempt to pay for one order.

    An order may accumulate several of these — a customer who abandons the
    gateway and comes back gets a new row, not an overwritten one. The order's
    own payment_status is the summary; this is the ledger.
    """

    class Status(models.TextChoices):
        INITIATED = "initiated", _("Initiated")
        PENDING = "pending", _("Awaiting gateway")
        PAID = "paid", _("Paid")
        FAILED = "failed", _("Failed")
        CANCELLED = "cancelled", _("Cancelled by user")
        REFUNDED = "refunded", _("Refunded")

    class Gateway(models.TextChoices):
        ZARINPAL = "zarinpal", _("ZarinPal")
        BITPAY = "bitpay", _("BitPay")
        MOCK = "mock", _("Mock gateway")

    order = models.ForeignKey(
        "orders.Order", on_delete=models.PROTECT, related_name="payments",
        verbose_name=_("order"),
    )
    gateway = models.CharField(
        _("gateway"), max_length=20, choices=Gateway.choices, default=Gateway.ZARINPAL
    )
    status = models.CharField(
        _("status"), max_length=16, choices=Status.choices, default=Status.INITIATED,
        db_index=True,
    )

    amount = models.DecimalField(
        _("amount"), max_digits=12, decimal_places=0,
        help_text=_("Frozen at request time; the gateway must return this exact figure."),
    )

    gateway_fee = models.DecimalField(
        _("کارمزد درگاه"), max_digits=12, decimal_places=0, default=0,
        help_text=_(
            "مبلغی که فروشگاه به درگاه پرداخت می‌کند؛ به مبلغ سفارش مشتری اضافه نمی‌شود."
        ),
    )

    # The gateway's own identifiers. Both gateways are two-step, but they name
    # their handles differently: `authority` holds ZarinPal's authority or
    # BitPay's id_get, and `ref_id` holds ZarinPal's ref_id or BitPay's
    # trans_id. The unique constraint below is per gateway, so an id_get and an
    # authority can never be confused for each other.
    authority = models.CharField(
        _("authority"), max_length=64, blank=True, db_index=True,
        help_text=_("Gateway-side token identifying this transaction (ZarinPal authority / BitPay id_get)."),
    )
    ref_id = models.CharField(
        _("reference id"), max_length=64, blank=True,
        help_text=_("Bank reference, set once the payment verifies (ZarinPal ref_id / BitPay trans_id)."),
    )
    card_pan = models.CharField(_("masked card"), max_length=32, blank=True)

    description = models.CharField(_("description"), max_length=255, blank=True)
    failure_reason = models.CharField(_("failure reason"), max_length=255, blank=True)
    raw_response = models.JSONField(
        _("raw gateway response"), default=dict, blank=True,
        help_text=_("Kept verbatim for reconciliation and dispute handling."),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(_("paid at"), null=True, blank=True)

    class Meta:
        verbose_name = _("payment")
        verbose_name_plural = _("payments")
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["order", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["gateway", "authority"],
                condition=models.Q(authority__gt=""),
                name="unique_authority_per_gateway",
            ),
        ]

    def __str__(self):
        return f"{self.order.number} · {self.get_status_display()} · {self.amount}"

    @property
    def is_settled(self):
        return self.status in (self.Status.PAID, self.Status.REFUNDED)

    def mark_paid(self, *, ref_id, card_pan="", fee=Decimal("0"), raw=None):
        self.status = self.Status.PAID
        self.ref_id = ref_id
        self.card_pan = card_pan
        # Settlement is the only moment the fee is known, so it is recorded
        # here rather than at request time.
        self.gateway_fee = fee or Decimal("0")
        self.paid_at = timezone.now()
        if raw is not None:
            self.raw_response = raw
        self.save(
            update_fields=[
                "status", "ref_id", "card_pan", "gateway_fee", "paid_at",
                "raw_response", "updated_at",
            ]
        )
        return self

    def mark_failed(self, reason, *, raw=None, status=None):
        self.status = status or self.Status.FAILED
        self.failure_reason = str(reason)[:255]
        if raw is not None:
            self.raw_response = raw
        self.save(update_fields=["status", "failure_reason", "raw_response", "updated_at"])
        return self

    @staticmethod
    def new_authority():
        """ZarinPal authorities are 36 characters, 'A' + 35 digits."""
        return "A" + get_random_string(35, "0123456789")


class GatewayToggle(models.Model):
    """Whether one payment gateway is offered at checkout.

    Only the switch lives here. Credentials stay in the environment: a merchant
    key in the database would be readable by anyone who reaches the admin, and
    recoverable from any backup of it.

    A gateway with no row is treated as enabled, so adding a driver never
    silently turns it off — `PAYMENT_GATEWAYS` in the environment still decides
    which gateways exist at all, and this only decides which of those are live
    right now.
    """

    name = models.SlugField(
        _("gateway"), max_length=20, unique=True,
        help_text=_("Driver name, e.g. zarinpal or bitpay."),
    )
    is_enabled = models.BooleanField(
        _("enabled"), default=True,
        help_text=_("Disabled gateways disappear from checkout immediately."),
    )
    note = models.CharField(
        _("note"), max_length=200, blank=True,
        help_text=_("Why it was switched off, for whoever finds it later."),
    )
    sort_order = models.PositiveSmallIntegerField(_("sort order"), default=0)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("gateway switch")
        verbose_name_plural = _("gateway switches")
        ordering = ("sort_order", "name")

    def __str__(self):
        state = "on" if self.is_enabled else "off"
        return f"{self.name} ({state})"

    @classmethod
    def disabled_names(cls):
        """Names switched off. Read on every checkout, so kept to one query."""
        return set(
            cls.objects.filter(is_enabled=False).values_list("name", flat=True)
        )
