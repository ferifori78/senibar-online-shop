from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import F, Q, Sum
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _


class GrindType(models.TextChoices):
    """How the beans leave the shop. Whole is the default — we grind only on
    request, since ground coffee stales in days rather than weeks."""

    WHOLE = "whole", _("Whole Bean")
    ESPRESSO = "espresso", _("Espresso")
    V60 = "v60", _("V60 / Pour Over")
    CHEMEX = "chemex", _("Chemex")
    AEROPRESS = "aeropress", _("AeroPress")
    FRENCH_PRESS = "french_press", _("French Press")
    MOKA_POT = "moka_pot", _("Moka Pot")
    COLD_BREW = "cold_brew", _("Cold Brew")
    TURKISH = "turkish", _("Turkish")


# Grind fineness, coarsest to finest. Used to sequence the grinder queue so the
# operator adjusts in one direction and purges less.
GRIND_FINENESS = {
    GrindType.WHOLE: 0,
    GrindType.COLD_BREW: 1,
    GrindType.FRENCH_PRESS: 2,
    GrindType.CHEMEX: 3,
    GrindType.V60: 4,
    GrindType.AEROPRESS: 5,
    GrindType.MOKA_POT: 6,
    GrindType.ESPRESSO: 7,
    GrindType.TURKISH: 8,
}


class ShippingMethod(models.Model):
    """A shipping option the roastery offers, editable from the back office.

    `key` is the stable identifier: an Order stores it as a plain string and
    keeps its own `shipping_cost`, so retiring or repricing a method here can
    never rewrite an order that has already been placed.
    """

    key = models.SlugField(
        _("key"), max_length=20, unique=True,
        help_text=_("Stable identifier stored on orders. Do not change it once in use."),
    )
    label = models.CharField(_("label"), max_length=120)
    description = models.TextField(_("description"), blank=True)
    days = models.CharField(
        _("delivery time"), max_length=60, blank=True,
        help_text=_("Shown to the customer, e.g. 3 to 5 working days."),
    )

    cost = models.DecimalField(
        _("cost"), max_digits=12, decimal_places=0, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    free_over = models.DecimalField(
        _("free over"), max_digits=12, decimal_places=0, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0"))],
        help_text=_("Subtotal above which this method is free. Empty means never free."),
    )

    is_active = models.BooleanField(
        _("active"), default=True,
        help_text=_("Inactive methods disappear from checkout but still price old orders."),
    )
    sort_order = models.PositiveSmallIntegerField(_("sort order"), default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("shipping method")
        verbose_name_plural = _("shipping methods")
        ordering = ("sort_order", "key")

    def __str__(self):
        return f"{self.label} ({self.key})"

    def cost_for(self, subtotal):
        """This method's price for a given subtotal, honouring the threshold."""
        if self.free_over is not None and subtotal >= self.free_over:
            return Decimal("0")
        return self.cost


class OrderQuerySet(models.QuerySet):
    def open(self):
        return self.exclude(status__in=Order.TERMINAL_STATUSES)

    def in_production(self):
        return self.filter(
            status__in=[Order.Status.ROASTING, Order.Status.GROUND, Order.Status.PACKED]
        )

    def awaiting_roast(self):
        return self.filter(status=Order.Status.PENDING, paid_at__isnull=False)

    def for_user(self, user):
        return self.filter(user=user)

    def with_totals(self):
        return self.annotate(computed_total=Sum(F("items__unit_price") * F("items__quantity")))


class OrderManager(models.Manager.from_queryset(OrderQuerySet)):
    def get_queryset(self):
        return super().get_queryset().select_related("user")


class Order(models.Model):
    """A customer order. The shipping address is stored as a flat snapshot so
    that editing the saved address later never rewrites a shipped order."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        ROASTING = "roasting", _("Roasting")
        GROUND = "ground", _("Ground")
        PACKED = "packed", _("Packed")
        SHIPPED = "shipped", _("Shipped")
        DELIVERED = "delivered", _("Delivered")
        CANCELLED = "cancelled", _("Cancelled")
        REFUNDED = "refunded", _("Refunded")

    # The happy path, in order. Drives the Timeline register on the frontend.
    PIPELINE = [
        Status.PENDING,
        Status.ROASTING,
        Status.GROUND,
        Status.PACKED,
        Status.SHIPPED,
        Status.DELIVERED,
    ]
    TERMINAL_STATUSES = [Status.DELIVERED, Status.CANCELLED, Status.REFUNDED]

    # Which transitions are legal. Anything else raises.
    ALLOWED_TRANSITIONS = {
        Status.PENDING: [Status.ROASTING, Status.CANCELLED],
        Status.ROASTING: [Status.GROUND, Status.PACKED, Status.CANCELLED],
        Status.GROUND: [Status.PACKED, Status.CANCELLED],
        Status.PACKED: [Status.SHIPPED, Status.CANCELLED],
        Status.SHIPPED: [Status.DELIVERED, Status.REFUNDED],
        Status.DELIVERED: [Status.REFUNDED],
        Status.CANCELLED: [],
        Status.REFUNDED: [],
    }

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", _("Unpaid")
        PAID = "paid", _("Paid")
        FAILED = "failed", _("Failed")
        REFUNDED = "refunded", _("Refunded")

    number = models.CharField(_("order number"), max_length=20, unique=True, editable=False)
    user = models.ForeignKey(
        "accounts.CustomUser", on_delete=models.PROTECT, related_name="orders",
        verbose_name=_("customer"),
    )

    status = models.CharField(
        _("status"), max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    payment_status = models.CharField(
        _("payment status"), max_length=16, choices=PaymentStatus.choices,
        default=PaymentStatus.UNPAID,
    )

    # --- Shipping address snapshot ---------------------------------------
    address = models.ForeignKey(
        "accounts.Address", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="orders", verbose_name=_("saved address"),
        help_text=_("Reference only. The fields below are the authoritative record."),
    )
    recipient_name = models.CharField(_("recipient name"), max_length=120)
    recipient_phone = models.CharField(_("recipient phone"), max_length=20)
    province = models.CharField(_("province"), max_length=60)
    city = models.CharField(_("city"), max_length=60)
    street_address = models.TextField(_("street address"))
    postal_code = models.CharField(_("postal code"), max_length=20)

    # --- Money ------------------------------------------------------------
    shipping_method = models.CharField(
        _("shipping method"), max_length=20, default="standard",
        help_text=_("ShippingMethod.key. Stored as a string so a deleted method cannot orphan the order."),
    )
    shipping_cost = models.DecimalField(
        _("shipping cost"), max_digits=12, decimal_places=0, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    discount_amount = models.DecimalField(
        _("discount"), max_digits=12, decimal_places=0, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    total_amount = models.DecimalField(
        _("total"), max_digits=12, decimal_places=0, default=Decimal("0"),
        help_text=_("Denormalised for reporting; recomputed by recalculate_total()."),
    )

    customer_note = models.TextField(_("customer note"), blank=True)
    internal_note = models.TextField(_("internal note"), blank=True)
    tracking_code = models.CharField(_("tracking code"), max_length=64, blank=True)

    # --- Timestamps for each pipeline stage -------------------------------
    placed_at = models.DateTimeField(_("placed at"), auto_now_add=True)
    paid_at = models.DateTimeField(_("paid at"), null=True, blank=True)
    roasted_at = models.DateTimeField(_("roasted at"), null=True, blank=True)
    shipped_at = models.DateTimeField(_("shipped at"), null=True, blank=True)
    delivered_at = models.DateTimeField(_("delivered at"), null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = OrderManager()

    class Meta:
        verbose_name = _("order")
        verbose_name_plural = _("orders")
        ordering = ("-placed_at",)
        indexes = [
            models.Index(fields=["status", "-placed_at"]),
            models.Index(fields=["user", "-placed_at"]),
        ]

    def __str__(self):
        return f"{self.number} — {self.get_status_display()}"

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = self._generate_number()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_number():
        """SB-YYMMDD-XXXX. Readable on a packing slip, unguessable enough."""
        stamp = timezone.localdate().strftime("%y%m%d")
        for _attempt in range(10):
            candidate = f"SB-{stamp}-{get_random_string(4, '0123456789ABCDEFGHJKMNPQRSTVWXYZ')}"
            if not Order.objects.filter(number=candidate).exists():
                return candidate
        raise RuntimeError("Could not allocate a unique order number.")

    # --- Derived values ---------------------------------------------------
    @property
    def subtotal(self):
        return sum((item.line_total for item in self.items.all()), Decimal("0"))

    def recalculate_total(self, save=True):
        """Re-derive shipping and the grand total from the current line items.

        Shipping is recomputed rather than trusted, so a free-shipping
        threshold can never be met by a client that simply says so.
        """
        from .shipping import shipping_cost_for

        subtotal = self.subtotal
        try:
            self.shipping_cost = shipping_cost_for(self.shipping_method, subtotal)
        except KeyError:
            # Unknown method on an existing order: keep what was stored.
            pass

        total = subtotal + self.shipping_cost - self.discount_amount
        self.total_amount = max(total, Decimal("0"))
        if save:
            self.save(update_fields=["shipping_cost", "total_amount", "updated_at"])
        return self.total_amount

    @property
    def total_grams(self):
        return self.items.aggregate(g=Sum(F("weight_grams") * F("quantity")))["g"] or 0

    @property
    def requires_grinding(self):
        return self.items.exclude(grind_type=GrindType.WHOLE).exists()

    @property
    def is_open(self):
        return self.status not in self.TERMINAL_STATUSES

    @property
    def can_be_cancelled(self):
        return Order.Status.CANCELLED in self.ALLOWED_TRANSITIONS[self.Status(self.status)]

    @property
    def pipeline_position(self):
        """Index into PIPELINE, or None for cancelled/refunded orders."""
        try:
            return self.PIPELINE.index(self.Status(self.status))
        except ValueError:
            return None

    def timeline(self):
        """The Timeline register's data: every pipeline stage with its state."""
        position = self.pipeline_position
        stages = []
        for index, stage in enumerate(self.PIPELINE):
            if position is None:
                state = "cancelled"
            elif index < position:
                state = "done"
            elif index == position:
                state = "current"
            else:
                state = "upcoming"
            stages.append(
                {"status": stage.value, "label": stage.label, "state": state}
            )
        return stages

    # --- Transitions ------------------------------------------------------
    @transaction.atomic
    def transition_to(
        self, new_status, *, actor=None, note="", commit_stock=True, notify=True
    ):
        """Move the order forward, recording history and touching stock.

        Raises ValueError on an illegal transition rather than silently
        allowing an order to skip roasting or un-ship itself.
        """
        current = self.Status(self.status)
        target = self.Status(new_status)

        if target == current:
            return self

        if target not in self.ALLOWED_TRANSITIONS[current]:
            raise ValueError(
                f"Cannot move order {self.number} from {current.label} to {target.label}."
            )

        now = timezone.now()
        stamp_fields = {
            self.Status.ROASTING: "roasted_at",
            self.Status.SHIPPED: "shipped_at",
            self.Status.DELIVERED: "delivered_at",
        }

        self.status = target
        updated = ["status", "updated_at"]
        if field := stamp_fields.get(target):
            setattr(self, field, now)
            updated.append(field)
        self.save(update_fields=updated)

        if commit_stock:
            if target == self.Status.SHIPPED:
                for item in self.items.select_related("batch"):
                    item.commit_stock()
            elif target in (self.Status.CANCELLED, self.Status.REFUNDED):
                for item in self.items.select_related("batch"):
                    item.release_stock()

        OrderStatusHistory.objects.create(
            order=self, from_status=current, to_status=target, actor=actor, note=note
        )

        # Queued after commit: a worker that picks this up mid-transaction
        # would read the order at its old status.
        if notify:
            self._queue_notification("order_status_changed", self.pk, target.value)
            self._queue_notification(
                "order_status_changed",
                self.pk,
                target.value,
                getattr(actor, "display_name", "") if actor else "",
                module="feed",
            )

        return self

    @staticmethod
    def _queue_notification(task_name, *args, module="tasks"):
        """Dispatch a notification task without making the model depend on it.

        `module` picks between `notifications.tasks` (what the customer is
        told) and `notifications.feed` (what the shop's own channel is told).

        Import is local and failures are swallowed: a broker that is down must
        never roll back an order that has already shipped.
        """
        from django.db import transaction as db_transaction

        def dispatch():
            try:
                import importlib

                mod = importlib.import_module(f"notifications.{module}")
                getattr(mod, task_name).delay(*args)
            except Exception:
                import logging

                logging.getLogger("senobar.orders").exception(
                    "Could not queue %s.%s%s", module, task_name, args
                )

        db_transaction.on_commit(dispatch)

    @transaction.atomic
    def mark_paid(self, *, actor=None, reference="", notify=True):
        self.payment_status = self.PaymentStatus.PAID
        self.paid_at = timezone.now()
        self.save(update_fields=["payment_status", "paid_at", "updated_at"])

        # Claim the stock now. Payment is the first moment the shop owes this
        # customer coffee, so it is the right moment to stop offering the same
        # grams to somebody else.
        unfulfillable = []
        for item in self.items.select_related("product", "batch"):
            if item.assign_batch() is None:
                unfulfillable.append(item.product_name)

        OrderStatusHistory.objects.create(
            order=self, from_status=self.status, to_status=self.status,
            actor=actor, note=f"Payment received. {reference}".strip(),
        )

        if unfulfillable:
            # Not an error: the money is taken and the order stands. The
            # roastery sees it on the board and roasts a fresh batch — which is
            # the normal path for a roast-to-order shop. Recorded after the
            # payment row so the trail reads in the order things happened.
            OrderStatusHistory.objects.create(
                order=self, from_status=self.status, to_status=self.status,
                actor=actor,
                note="Awaiting a roast for: " + "، ".join(unfulfillable),
            )

        if notify:
            self._queue_notification("payment_received", self.pk)
            self._queue_notification("payment_confirmed", self.pk, module="feed")

        return self

    def grind_queue(self):
        """Items needing grinding, coarsest first, to minimise grinder resets."""
        items = list(self.items.exclude(grind_type=GrindType.WHOLE).select_related("product"))
        return sorted(items, key=lambda i: GRIND_FINENESS.get(i.grind_type, 0))


class OrderItem(models.Model):
    """One coffee, at one weight, at one grind. Price and product name are
    copied at checkout so a later price change cannot rewrite an old order."""

    class Weight(models.IntegerChoices):
        G100 = 100, _("100 g")
        G250 = 250, _("250 g")
        G500 = 500, _("500 g")
        G1000 = 1000, _("1 kg")

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="items", verbose_name=_("order")
    )
    product = models.ForeignKey(
        "catalog.CoffeeProduct", on_delete=models.PROTECT, related_name="order_items",
        verbose_name=_("product"),
    )
    batch = models.ForeignKey(
        "catalog.RoastBatch", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="order_items", verbose_name=_("roast batch"),
        help_text=_("Assigned when the order is roasted or allocated."),
    )

    # Snapshot of the product at the moment of ordering.
    product_name = models.CharField(_("product name"), max_length=120, blank=True)
    product_origin = models.CharField(_("origin"), max_length=60, blank=True)

    weight_grams = models.PositiveIntegerField(
        _("weight (g)"), default=Weight.G250,
        validators=[MinValueValidator(1)],
        help_text=_(
            "Grams on this line. Deliberately NOT restricted to Weight.choices: "
            "those are the four sizes coffee is sold in, but a pantry pack is "
            "whatever the manufacturer printed on it — 200g of masala is a "
            "legitimate line and would fail a choices validation."
        ),
    )
    grind_type = models.CharField(
        _("grind"), max_length=16, choices=GrindType.choices, default=GrindType.WHOLE
    )
    quantity = models.PositiveSmallIntegerField(
        _("quantity"), default=1, validators=[MinValueValidator(1)]
    )
    unit_price = models.DecimalField(
        _("unit price"), max_digits=12, decimal_places=0,
        validators=[MinValueValidator(Decimal("0"))],
        help_text=_("Price for one unit at this weight, frozen at checkout."),
    )

    stock_committed = models.BooleanField(
        _("stock committed"), default=False,
        help_text=_("True once stock has been deducted."),
    )
    # A lot line records its reservation by having a batch. A pantry line has
    # no batch, so it needs its own flag — without it a second call to
    # assign_batch (a retried callback, a re-run of mark_paid) would reserve
    # the same packs twice and quietly oversell the item.
    stock_reserved = models.BooleanField(
        _("stock reserved"), default=False,
        help_text=_("Pantry lines only: stock is held but not yet deducted."),
    )
    note = models.CharField(_("note"), max_length=200, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("order item")
        verbose_name_plural = _("order items")
        ordering = ("created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["order", "product", "weight_grams", "grind_type"],
                name="unique_line_per_order",
            ),
            models.CheckConstraint(condition=Q(quantity__gte=1), name="item_quantity_positive"),
        ]

    def __str__(self):
        return f"{self.product_name or self.product} · {self.weight_grams}g · {self.get_grind_type_display()}"

    def save(self, *args, **kwargs):
        if self.product_id:
            if not self.product_name:
                self.product_name = self.product.name
            if not self.product_origin:
                self.product_origin = self.product.origin_country

            if self.product.is_pantry:
                # Nothing to grind. Forced rather than merely defaulted: the
                # API takes a grind from the client, and a crafted request
                # asking for espresso grind on hot chocolate would otherwise
                # print it on the packing slip and confuse the person packing.
                self.grind_type = GrindType.WHOLE
                if self.product.sold_by_package:
                    # The pack's own weight, so the invoice and the packing
                    # slip state what actually ships. A client-supplied weight
                    # is meaningless for a sealed pack.
                    self.weight_grams = self.product.package_grams or self.weight_grams

            if self.unit_price is None:
                self.unit_price = self.product.price_for_grams(self.weight_grams)
        super().save(*args, **kwargs)

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    @property
    def total_grams(self):
        return self.weight_grams * self.quantity

    @property
    def needs_grinding(self):
        return self.grind_type != GrindType.WHOLE

    # --- Stock ------------------------------------------------------------
    @property
    def is_pantry_line(self):
        """A line for a pantry item: no roast, no batch, stock on the product."""
        return bool(self.product and self.product.is_pantry)

    def assign_batch(self):
        """Pick the batch this line will ship from, and hold its grams.

        Until this runs the line has no batch, and every method below is a
        no-op — the order would move all the way to shipped without a single
        gram leaving the shelf. Called when the order is paid, because that is
        the first moment the shop owes anyone coffee.

        Returns the batch, or None when nothing has enough free stock; the
        caller decides whether that is an error or a line to flag for the
        roastery.

        A pantry line has no batch to assign, but it still has to claim its
        stock here — this is the only hook the payment path calls. It returns
        a truthy sentinel so `mark_paid` does not read "no stock" and flag a
        perfectly fulfillable line as awaiting a roast.
        """
        if self.is_pantry_line:
            return self._claim_pantry_stock()

        if self.batch or self.stock_committed:
            return self.batch

        # Lock the candidate rows: two orders paid at the same instant must not
        # both be promised the last kilo.
        with transaction.atomic():
            batch = self.product.batch_to_ship(self.total_grams)
            if batch is None:
                return None

            # Imported here, not at module scope: catalog imports accounts, and a
            # top-level import would tie the two apps' load order together.
            from catalog.models import RoastBatch

            locked = RoastBatch.objects.select_for_update().get(pk=batch.pk)
            # Re-check under the lock: another order may have taken it between
            # the query above and the lock here.
            if locked.remaining_grams - locked.reserved_grams < self.total_grams:
                return None

            self.batch = locked
            self.save(update_fields=["batch"])
            locked.reserve(self.total_grams)

        return self.batch

    def _pantry_amounts(self):
        """What this line takes from a pantry item, in that item's own unit."""
        if self.product.sold_by_package:
            return {"packages": self.quantity}
        return {"grams": self.total_grams}

    def _claim_pantry_stock(self):
        """Reserve a pantry item's stock for this line.

        Returns True when the stock was held, None when there is not enough —
        matching `assign_batch`'s contract so `mark_paid` can treat both kinds
        the same way.
        """
        if self.stock_reserved or self.stock_committed:
            return True

        from catalog.models import CoffeeProduct

        with transaction.atomic():
            # Lock the product row: two orders paid at the same instant must
            # not both be promised the last pack. This is the pantry analogue
            # of locking the batch.
            locked = CoffeeProduct.objects.select_for_update().get(pk=self.product_id)
            try:
                locked.reserve_stock(**self._pantry_amounts())
            except ValueError:
                return None

            self.stock_reserved = True
            self.save(update_fields=["stock_reserved"])
        return True

    def reserve_stock(self):
        """Hold stock without deducting it yet."""
        if self.is_pantry_line:
            self._claim_pantry_stock()
            return
        if self.batch and not self.stock_committed:
            self.batch.reserve(self.total_grams)

    def commit_stock(self):
        """Deduct stock — called when the order ships."""
        if self.is_pantry_line:
            if self.stock_committed:
                return
            from catalog.models import CoffeeProduct

            with transaction.atomic():
                locked = CoffeeProduct.objects.select_for_update().get(pk=self.product_id)
                locked.consume_stock(**self._pantry_amounts())
                self.stock_committed = True
                # The reservation is cleared by consume_stock; the flag has to
                # follow or a later cancellation would release it twice.
                self.stock_reserved = False
                self.save(update_fields=["stock_committed", "stock_reserved"])
            return

        if self.batch and not self.stock_committed:
            self.batch.consume(self.total_grams)
            self.stock_committed = True
            self.save(update_fields=["stock_committed"])

    def release_stock(self):
        """Return reserved stock — called when the order is cancelled."""
        if self.is_pantry_line:
            if not self.stock_reserved or self.stock_committed:
                return
            from catalog.models import CoffeeProduct

            with transaction.atomic():
                locked = CoffeeProduct.objects.select_for_update().get(pk=self.product_id)
                locked.release_stock(**self._pantry_amounts())
                self.stock_reserved = False
                self.save(update_fields=["stock_reserved"])
            return

        if self.batch and not self.stock_committed:
            self.batch.release(self.total_grams)


class OrderStatusHistory(models.Model):
    """Append-only audit trail. One row per transition; never edited."""

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="history", verbose_name=_("order")
    )
    from_status = models.CharField(_("from"), max_length=16, choices=Order.Status.choices)
    to_status = models.CharField(_("to"), max_length=16, choices=Order.Status.choices)
    actor = models.ForeignKey(
        "accounts.CustomUser", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="order_actions", verbose_name=_("actor"),
        help_text=_("Null for automated transitions."),
    )
    note = models.TextField(_("note"), blank=True)
    created_at = models.DateTimeField(_("at"), auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("order status change")
        verbose_name_plural = _("order status history")
        ordering = ("created_at",)
        indexes = [models.Index(fields=["order", "created_at"])]

    def __str__(self):
        return f"{self.order.number}: {self.from_status} -> {self.to_status}"
