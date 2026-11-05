from datetime import timedelta
from decimal import Decimal

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models, transaction
from django.db.models import Sum, F, Q
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


# Beans are at their best in this window after roasting. Used for freshness
# reporting and for excluding stale batches from fulfilment.
REST_DAYS = 3          # degassing; too fresh to brew well
PEAK_DAYS = 21         # ideal window closes
STALE_DAYS = 45        # no longer sellable


class CoffeeProductQuerySet(models.QuerySet):
    def published(self):
        return self.filter(status=CoffeeProduct.Status.PUBLISHED)

    def with_available_stock(self):
        """Annotate saleable stock, whichever way this product holds it.

        ``saleable_grams`` is the annotation — NOT ``stock_grams``, which is
        now a real column on pantry items; an annotation sharing a field name
        raises at query time in Django 5, and before that it silently shadowed
        the column.

        A lot sums its fresh batches. A pantry item has none, so the sum is
        NULL and the item would drop out of ``in_stock()`` entirely; its own
        columns are used instead.
        """
        fresh_cutoff = timezone.localdate() - timedelta(days=STALE_DAYS)
        batch_grams = models.Sum(
            F("batches__remaining_grams"),
            filter=Q(
                batches__roast_date__gte=fresh_cutoff,
                batches__status=RoastBatch.Status.AVAILABLE,
            ),
            default=0,
        )
        return self.annotate(
            saleable_grams=models.Case(
                models.When(
                    kind=CoffeeProduct.Kind.PANTRY,
                    sale_mode=CoffeeProduct.SaleMode.PACKAGE,
                    # Packs times pack size. A pack with no recorded weight
                    # would multiply to zero, so COALESCE it to 1 gram: the
                    # figure is only used to answer "is there any?".
                    then=(F("stock_packages") - F("reserved_packages"))
                    * Coalesce(F("package_grams"), models.Value(1)),
                ),
                models.When(
                    kind=CoffeeProduct.Kind.PANTRY,
                    then=F("stock_grams") - F("reserved_grams"),
                ),
                default=batch_grams,
                output_field=models.IntegerField(),
            )
        )

    def in_stock(self):
        return self.with_available_stock().filter(saleable_grams__gt=0)

    def lots(self):
        """Single-origin coffees only — what the taste quiz recommends from."""
        return self.filter(kind=CoffeeProduct.Kind.LOT)

    def featured(self):
        """Hand-picked for the landing page."""
        return self.filter(is_featured=True)


class CoffeeProductManager(models.Manager.from_queryset(CoffeeProductQuerySet)):
    def get_queryset(self):
        return super().get_queryset().select_related()


class CoffeeProduct(models.Model):
    """Something the shop sells. Two kinds live here, not two models.

    A single-origin LOT is the identity of a coffee; its stock lives on
    RoastBatch, because a roast is a physical event with a date and a
    freshness window.

    A PANTRY item — masala tea, gold coffee, hot chocolate — has none of that.
    It is not roasted, has no cupping profile, and is not ground to order. It
    simply sits in the warehouse until it is sold, so its stock lives on the
    product itself.

    They share one model because every consumer already points here:
    OrderItem.product, the cart, the payment lines, the panel. A second model
    would fork all of them, and every `if isinstance(...)` that followed would
    be a place for the two paths to drift apart. `kind` is the discriminator,
    and the handful of methods that differ branch on it in one place each.
    """

    class Kind(models.TextChoices):
        LOT = "lot", _("Single-origin lot")
        PANTRY = "pantry", _("Pantry item")

    class Status(models.TextChoices):
        DRAFT = "draft", _("Draft")
        PUBLISHED = "published", _("Published")
        ARCHIVED = "archived", _("Archived")

    class SaleMode(models.TextChoices):
        """How a pantry item is priced and counted.

        PACKAGE — a sealed pack of a fixed size. The customer buys whole
            packs; stock is a count of packs. This is the normal case for
            masala, instant coffee, a tin of chocolate.
        WEIGHT — sold loose by weight, like coffee. Stock is grams, price
            scales from the 250g base.
        """

        PACKAGE = "package", _("Sold as a package")
        WEIGHT = "weight", _("Sold by weight")

    class Process(models.TextChoices):
        WASHED = "washed", _("Washed")
        NATURAL = "natural", _("Natural")
        HONEY = "honey", _("Honey")
        ANAEROBIC = "anaerobic", _("Anaerobic")
        WET_HULLED = "wet_hulled", _("Wet Hulled")
        OTHER = "other", _("Other")

    class RoastLevel(models.TextChoices):
        LIGHT = "light", _("Light")
        MEDIUM_LIGHT = "medium_light", _("Medium Light")
        MEDIUM = "medium", _("Medium")
        MEDIUM_DARK = "medium_dark", _("Medium Dark")
        DARK = "dark", _("Dark")

    class Species(models.TextChoices):
        ARABICA = "arabica", _("Arabica")
        ROBUSTA = "robusta", _("Robusta")
        BLEND = "blend", _("Blend")

    class OriginType(models.TextChoices):
        """How many origins went into the bag.

        Kept separate from `species` because the two answer different
        questions and a blend of two Ethiopian arabicas is arabica *and*
        multi-origin. Deriving one from the other would make that coffee
        invisible under whichever filter it was not stored as.
        """

        SINGLE = "single", _("Single origin")
        MULTI = "multi", _("Multi origin")

    # --- Identity ---------------------------------------------------------
    # Defaults to LOT so every existing row keeps its meaning through the
    # migration without a data step.
    kind = models.CharField(
        _("kind"), max_length=16, choices=Kind.choices, default=Kind.LOT, db_index=True,
        help_text=_("A roasted lot, or a pantry item with no roast or grind."),
    )
    name = models.CharField(_("name"), max_length=120)
    slug = models.SlugField(_("slug"), max_length=140, unique=True, blank=True)
    subtitle = models.CharField(_("subtitle"), max_length=160, blank=True)
    description = models.TextField(_("description"), blank=True)

    # --- Origin -----------------------------------------------------------
    origin_country = models.CharField(_("country of origin"), max_length=60, db_index=True)
    origin_region = models.CharField(_("region"), max_length=90, blank=True)
    farm = models.CharField(_("farm / cooperative"), max_length=120, blank=True)
    producer = models.CharField(_("producer"), max_length=120, blank=True)
    varietal = models.CharField(_("varietal"), max_length=120, blank=True)
    altitude_masl = models.PositiveIntegerField(
        _("altitude (masl)"), null=True, blank=True,
        help_text=_("Growing altitude in metres above sea level."),
    )
    harvest_year = models.PositiveSmallIntegerField(_("harvest year"), null=True, blank=True)

    # --- Cup profile ------------------------------------------------------
    species = models.CharField(
        _("species"), max_length=16, choices=Species.choices, default=Species.ARABICA
    )
    origin_type = models.CharField(
        _("origin type"), max_length=16, choices=OriginType.choices,
        default=OriginType.SINGLE, db_index=True,
        help_text=_("Whether this is one origin or several blended together."),
    )
    # `process` and `roast_level` stay as the primary value — every storefront
    # card, filter and detail row already reads them, and a blend still has one
    # process it is best described by. The `_extra` lists hold the others.
    process = models.CharField(
        _("process"), max_length=16, choices=Process.choices, default=Process.WASHED
    )
    processes_extra = models.JSONField(
        _("additional processes"), default=list, blank=True,
        help_text=_("Further processes in this lot, beyond the primary one."),
    )
    roast_level = models.CharField(
        _("roast level"), max_length=16, choices=RoastLevel.choices, default=RoastLevel.MEDIUM
    )
    roast_levels_extra = models.JSONField(
        _("additional roast levels"), default=list, blank=True,
        help_text=_("Further roast levels this coffee is offered at."),
    )
    flavor_notes = models.JSONField(
        _("flavor notes"), default=list, blank=True,
        help_text=_('Ordered list of tasting notes, e.g. ["jasmine", "bergamot", "honey"].'),
    )
    cupping_score = models.DecimalField(
        _("cupping score"), max_digits=4, decimal_places=1, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        help_text=_("SCA score, 0-100."),
    )
    # 1-5 sensory axes, for the radar chart on the product page.
    acidity = models.PositiveSmallIntegerField(
        _("acidity"), default=3, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    body = models.PositiveSmallIntegerField(
        _("body"), default=3, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    sweetness = models.PositiveSmallIntegerField(
        _("sweetness"), default=3, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    bitterness = models.PositiveSmallIntegerField(
        _("bitterness"), default=3, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )

    # --- Commerce ---------------------------------------------------------
    price_per_250g = models.DecimalField(
        _("price per 250g"), max_digits=12, decimal_places=0, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text=_("Base price in IRR for a 250g unit; other weights scale from this. "
                    "Ignored for a package item, which is priced per pack."),
    )
    is_espresso_suitable = models.BooleanField(_("suitable for espresso"), default=True)
    is_filter_suitable = models.BooleanField(_("suitable for filter"), default=True)

    # --- Pantry items -----------------------------------------------------
    # Ignored entirely when kind is LOT; a lot's stock is the sum of its
    # batches and its price scales from price_per_250g.
    sale_mode = models.CharField(
        _("sale mode"), max_length=16, choices=SaleMode.choices, default=SaleMode.PACKAGE,
        help_text=_("Pantry items only: sold as a fixed package, or by weight."),
    )
    package_grams = models.PositiveIntegerField(
        _("package size (g)"), null=True, blank=True,
        help_text=_("Net weight printed on the pack. Shown to the customer; "
                    "with sale_mode=package it does not affect the price."),
    )
    package_price = models.DecimalField(
        _("package price"), max_digits=12, decimal_places=0, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0"))],
        help_text=_("Price in IRR for one package. Used when sale_mode=package."),
    )
    # Deliberately two fields rather than one "quantity" that changes unit
    # with sale_mode: a number whose meaning depends on another column is
    # read wrong eventually, and in a stock figure that means overselling.
    stock_packages = models.PositiveIntegerField(
        _("packages in stock"), default=0,
        help_text=_("Whole packs on the shelf. Used when sale_mode=package."),
    )
    stock_grams = models.PositiveIntegerField(
        _("grams in stock"), default=0,
        help_text=_("Loose stock in grams. Used when sale_mode=weight."),
    )
    # Held the way RoastBatch holds reservations: claimed at payment, deducted
    # at shipping, released on cancellation. Without it, two orders placed in
    # the same minute can both be promised the last pack.
    reserved_packages = models.PositiveIntegerField(_("packages reserved"), default=0)
    reserved_grams = models.PositiveIntegerField(_("grams reserved"), default=0)

    brand = models.CharField(
        _("brand"), max_length=120, blank=True,
        help_text=_("Pantry items are usually somebody else's product."),
    )
    production_year = models.PositiveSmallIntegerField(
        _("production year"), null=True, blank=True
    )
    best_before = models.DateField(
        _("best before"), null=True, blank=True,
        help_text=_("Shown on the product page. Does not remove the item from sale."),
    )
    ingredients = models.TextField(
        _("ingredients"), blank=True,
        help_text=_("What is in it, as printed on the pack."),
    )
    preparation = models.TextField(
        _("how to prepare"), blank=True,
        help_text=_("A sentence or two: water temperature, amount, time."),
    )
    # A shop-facing number, never shown to customers: below this the panel
    # flags the item so it can be reordered before it runs out.
    low_stock_threshold = models.PositiveIntegerField(
        _("low stock warning at"), default=0,
        help_text=_("Packages or grams, matching the sale mode. 0 disables the warning."),
    )

    status = models.CharField(
        _("status"), max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    # Where this coffee sits on the shelf. Lowest first; products sharing a
    # number fall back to newest-first, so an untouched catalogue keeps the
    # order it has always had.
    sort_order = models.IntegerField(
        _("sort order"), default=0, db_index=True,
        help_text=_("Lower numbers appear first on the storefront."),
    )
    # Chosen by hand for the landing page. Defaults to False so the existing
    # catalogue is unchanged by the migration, and the home page keeps its
    # newest-first behaviour until a roaster picks a first product.
    is_featured = models.BooleanField(
        _("featured on the home page"), default=False, db_index=True,
        help_text=_("Show this product in «محصولات پیشنهادی صنوبر» on the home page."),
    )
    # The cover image, kept as its own field rather than folded into the
    # gallery: every existing product, serializer and storefront card already
    # reads `product.image`, and the gallery is additive. `cover` on
    # ProductImage keeps the two in step.
    image = models.ImageField(_("image"), upload_to="products/", null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CoffeeProductManager()

    class Meta:
        verbose_name = _("coffee product")
        verbose_name_plural = _("coffee products")
        ordering = ("sort_order", "-created_at")
        indexes = [
            models.Index(fields=["status", "origin_country"]),
            models.Index(fields=["sort_order", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.name} — {self.origin_country}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.name}-{self.origin_country}", allow_unicode=True)[:140]
        super().save(*args, **kwargs)

    @property
    def is_pantry(self):
        return self.kind == self.Kind.PANTRY

    @property
    def sold_by_package(self):
        """True when the customer buys whole packs rather than a weight."""
        return self.is_pantry and self.sale_mode == self.SaleMode.PACKAGE

    def price_for_grams(self, grams):
        """Linear scaling off the 250g base price, rounded to whole IRR.

        A package item ignores `grams` and answers with the pack price: the
        weight on the label is information, not a rate. Charging 200g of a
        250g-base price for a 200g pack of masala would be inventing a
        per-gram price the shop never set.
        """
        if self.sold_by_package:
            return Decimal(self.package_price or 0)
        return (self.price_per_250g * Decimal(grams) / Decimal(250)).quantize(Decimal("1"))

    @staticmethod
    def _combine(primary, extra, labels):
        """The primary value plus its extras, de-duplicated, order preserved.

        Unknown values are dropped rather than shown raw: `extra` is a JSON
        list, so a stale choice left behind by an edit would otherwise reach
        the storefront as a bare slug.
        """
        seen, out = set(), []
        for value in [primary, *(extra or [])]:
            if value and value not in seen and value in labels:
                seen.add(value)
                out.append({"value": value, "label": str(labels[value])})
        return out

    @property
    def all_processes(self):
        """Every process in this lot, primary first."""
        return self._combine(
            self.process, self.processes_extra, dict(self.Process.choices)
        )

    @property
    def all_roast_levels(self):
        """Every roast level this coffee is offered at, primary first."""
        return self._combine(
            self.roast_level, self.roast_levels_extra, dict(self.RoastLevel.choices)
        )

    def deletion_blockers(self):
        """What stops this product being erased, as counts.

        `OrderItem.product` and `RoastBatch.product` are both PROTECT, so a
        plain delete on a referenced product raises ProtectedError and reaches
        the roaster as a 500 with no explanation. Asking first turns that into
        a decision.
        """
        return {
            "orders": self.order_items.count(),
            "batches": self.batches.count(),
        }

    @property
    def can_be_erased(self):
        return not any(self.deletion_blockers().values())

    def archive(self):
        """Retire the product without erasing it.

        Archiving is not a soft status flag on a still-visible row: an
        archived product leaves the storefront entirely (`published()` filters
        on status) while its order lines keep pointing at a real record, so an
        old invoice still resolves.
        """
        if self.status == self.Status.ARCHIVED:
            return False
        self.status = self.Status.ARCHIVED
        self.save(update_fields=["status", "updated_at"])
        return True

    @property
    def available_grams(self):
        """Saleable grams.

        For a lot, that is the sum across fresh, available batches. For a
        pantry item there are no batches: the figure is what is on the shelf,
        minus what other unshipped orders have already claimed.

        Kept as one property rather than two so every existing caller — the
        list serializer, the storefront card, the in-stock filter — keeps
        working without knowing which kind it is holding.
        """
        if self.is_pantry:
            if self.sold_by_package:
                free = max(0, self.stock_packages - self.reserved_packages)
                return free * (self.package_grams or 0)
            return max(0, self.stock_grams - self.reserved_grams)

        cutoff = timezone.localdate() - timedelta(days=STALE_DAYS)
        return (
            self.batches.filter(
                roast_date__gte=cutoff, status=RoastBatch.Status.AVAILABLE
            ).aggregate(total=Sum("remaining_grams"))["total"]
            or 0
        )

    @property
    def available_packages(self):
        """Whole packs a customer could buy right now. Package items only."""
        if not self.sold_by_package:
            return 0
        return max(0, self.stock_packages - self.reserved_packages)

    @property
    def is_in_stock(self):
        # A package item with no package_grams recorded still has stock; going
        # through available_grams would multiply by zero and read as sold out.
        if self.sold_by_package:
            return self.available_packages > 0
        return self.available_grams > 0

    @property
    def is_low_stock(self):
        """For the panel: is this close to running out?

        Never shown to customers — a shop's reorder point is its own business,
        and "only 2 left" on a storefront is a sales tactic this shop does not
        use.
        """
        if not self.is_pantry or not self.low_stock_threshold:
            return False
        on_hand = (
            self.available_packages if self.sold_by_package else self.available_grams
        )
        return on_hand <= self.low_stock_threshold

    # --- Pantry stock movement -------------------------------------------
    # The same three verbs RoastBatch uses, so OrderItem can call one or the
    # other without a third vocabulary. `F()` expressions throughout: two
    # concurrent orders must not read the same figure and each write back
    # their own idea of it.

    def reserve_stock(self, *, packages=0, grams=0):
        """Hold stock for a paid order. Raises ValueError if it is not there."""
        if self.sold_by_package:
            if packages > self.available_packages:
                raise ValueError(
                    f"{self.name}: {self.available_packages} packages available, "
                    f"{packages} requested."
                )
            self.reserved_packages = F("reserved_packages") + packages
            self.save(update_fields=["reserved_packages", "updated_at"])
            self.refresh_from_db(fields=["reserved_packages"])
            return

        if grams > self.available_grams:
            raise ValueError(
                f"{self.name}: {self.available_grams}g available, {grams}g requested."
            )
        self.reserved_grams = F("reserved_grams") + grams
        self.save(update_fields=["reserved_grams", "updated_at"])
        self.refresh_from_db(fields=["reserved_grams"])

    def release_stock(self, *, packages=0, grams=0):
        """Give a reservation back — the order was cancelled.

        Clamped at zero the way RoastBatch.release is: a double release must
        not drive the counter negative, because a negative reservation reads
        as extra stock and oversells the item.
        """
        if self.sold_by_package:
            self.reserved_packages = models.Case(
                models.When(reserved_packages__lte=packages, then=models.Value(0)),
                default=F("reserved_packages") - packages,
            )
            self.save(update_fields=["reserved_packages", "updated_at"])
            self.refresh_from_db(fields=["reserved_packages"])
            return

        self.reserved_grams = models.Case(
            models.When(reserved_grams__lte=grams, then=models.Value(0)),
            default=F("reserved_grams") - grams,
        )
        self.save(update_fields=["reserved_grams", "updated_at"])
        self.refresh_from_db(fields=["reserved_grams"])

    def consume_stock(self, *, packages=0, grams=0):
        """Deduct shipped stock, clearing the matching reservation."""
        if self.sold_by_package:
            if packages > self.stock_packages:
                raise ValueError(
                    f"{self.name}: {self.stock_packages} packages on hand, "
                    f"{packages} requested."
                )
            self.stock_packages = F("stock_packages") - packages
            self.reserved_packages = models.Case(
                models.When(reserved_packages__lte=packages, then=models.Value(0)),
                default=F("reserved_packages") - packages,
            )
            self.save(update_fields=["stock_packages", "reserved_packages", "updated_at"])
            self.refresh_from_db(fields=["stock_packages", "reserved_packages"])
            return

        if grams > self.stock_grams:
            raise ValueError(
                f"{self.name}: {self.stock_grams}g on hand, {grams}g requested."
            )
        self.stock_grams = F("stock_grams") - grams
        self.reserved_grams = models.Case(
            models.When(reserved_grams__lte=grams, then=models.Value(0)),
            default=F("reserved_grams") - grams,
        )
        self.save(update_fields=["stock_grams", "reserved_grams", "updated_at"])
        self.refresh_from_db(fields=["stock_grams", "reserved_grams"])

    def freshest_batch(self):
        """The batch we would ship from today: newest roast with stock left."""
        return (
            self.batches.filter(status=RoastBatch.Status.AVAILABLE, remaining_grams__gt=0)
            .order_by("-roast_date")
            .first()
        )

    def batch_to_ship(self, grams):
        """The batch an order line should draw `grams` from.

        Oldest suitable roast first, not freshest: shipping the newest bag
        every time leaves the older ones on the shelf until they go stale,
        which is the opposite of what a roast-to-order shop wants. Only
        batches with enough unreserved stock qualify, so two orders cannot be
        promised the same grams.

        `select_for_update` is the caller's job — see OrderItem.assign_batch.
        """
        return (
            self.batches.filter(status=RoastBatch.Status.AVAILABLE)
            .annotate(free_grams=F("remaining_grams") - F("reserved_grams"))
            .filter(free_grams__gte=grams)
            .order_by("roast_date")
            .first()
        )


class RoastBatchQuerySet(models.QuerySet):
    def available(self):
        return self.filter(status=RoastBatch.Status.AVAILABLE, remaining_grams__gt=0)

    def fresh(self):
        cutoff = timezone.localdate() - timedelta(days=STALE_DAYS)
        return self.available().filter(roast_date__gte=cutoff)

    def in_peak_window(self):
        today = timezone.localdate()
        return self.available().filter(
            roast_date__lte=today - timedelta(days=REST_DAYS),
            roast_date__gte=today - timedelta(days=PEAK_DAYS),
        )

    def stale(self):
        cutoff = timezone.localdate() - timedelta(days=STALE_DAYS)
        return self.filter(roast_date__lt=cutoff)


class RoastBatchManager(models.Manager.from_queryset(RoastBatchQuerySet)):
    pass


class RoastBatch(models.Model):
    """One physical roast of one product, on one date. Inventory is tracked
    here so freshness and stock are the same fact, not two."""

    class Status(models.TextChoices):
        RESTING = "resting", _("Resting")
        AVAILABLE = "available", _("Available")
        DEPLETED = "depleted", _("Depleted")
        WITHDRAWN = "withdrawn", _("Withdrawn")

    product = models.ForeignKey(
        CoffeeProduct, on_delete=models.PROTECT, related_name="batches", verbose_name=_("product")
    )
    batch_code = models.CharField(
        _("batch code"), max_length=32, unique=True,
        help_text=_("Human-readable lot identifier, e.g. ETH-2408-01."),
    )
    roast_date = models.DateField(_("roast date"), db_index=True)
    roaster = models.ForeignKey(
        "accounts.CustomUser", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="roasted_batches", verbose_name=_("roaster"),
    )

    initial_grams = models.PositiveIntegerField(
        _("initial quantity (g)"), validators=[MinValueValidator(1)]
    )
    remaining_grams = models.PositiveIntegerField(_("remaining quantity (g)"), default=0)
    reserved_grams = models.PositiveIntegerField(
        _("reserved quantity (g)"), default=0,
        help_text=_("Committed to unfulfilled orders but not yet deducted."),
    )

    roast_profile = models.CharField(_("roast profile"), max_length=120, blank=True)
    development_time_ratio = models.DecimalField(
        _("development time ratio"), max_digits=4, decimal_places=2, null=True, blank=True,
        help_text=_("DTR as a percentage, e.g. 21.50."),
    )
    notes = models.TextField(_("notes"), blank=True)

    status = models.CharField(
        _("status"), max_length=16, choices=Status.choices, default=Status.RESTING, db_index=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = RoastBatchManager()

    class Meta:
        verbose_name = _("roast batch")
        verbose_name_plural = _("roast batches")
        ordering = ("-roast_date", "-created_at")
        indexes = [
            models.Index(fields=["product", "-roast_date"]),
            models.Index(fields=["status", "-roast_date"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(remaining_grams__lte=F("initial_grams")),
                name="remaining_not_above_initial",
            ),
            models.CheckConstraint(
                condition=Q(reserved_grams__lte=F("remaining_grams")),
                name="reserved_not_above_remaining",
            ),
        ]

    def __str__(self):
        return f"{self.batch_code} ({self.roast_date})"

    def save(self, *args, **kwargs):
        if self._state.adding and not self.remaining_grams:
            self.remaining_grams = self.initial_grams
        super().save(*args, **kwargs)

    # --- Freshness --------------------------------------------------------
    @property
    def days_since_roast(self):
        return (timezone.localdate() - self.roast_date).days

    @property
    def freshness(self):
        """Where this batch sits in its life: resting / peak / fading / stale."""
        days = self.days_since_roast
        if days < REST_DAYS:
            return "resting"
        if days <= PEAK_DAYS:
            return "peak"
        if days <= STALE_DAYS:
            return "fading"
        return "stale"

    @property
    def is_sellable(self):
        return (
            self.status == self.Status.AVAILABLE
            and self.available_grams > 0
            and self.freshness != "stale"
        )

    @property
    def available_grams(self):
        """Unreserved stock — what a new order may actually claim."""
        return max(self.remaining_grams - self.reserved_grams, 0)

    # --- Inventory transitions -------------------------------------------
    def reserve(self, grams):
        """Commit stock to an order without shipping it yet."""
        if grams > self.available_grams:
            raise ValueError(
                f"Batch {self.batch_code} has {self.available_grams}g available, {grams}g requested."
            )
        self.reserved_grams = F("reserved_grams") + grams
        self.save(update_fields=["reserved_grams", "updated_at"])
        self.refresh_from_db(fields=["reserved_grams"])

    def release(self, grams):
        """Give reserved stock back — an order was cancelled."""
        self.reserved_grams = models.Case(
            models.When(reserved_grams__lte=grams, then=models.Value(0)),
            default=F("reserved_grams") - grams,
        )
        self.save(update_fields=["reserved_grams", "updated_at"])
        self.refresh_from_db(fields=["reserved_grams"])

    def consume(self, grams):
        """Deduct shipped stock. Clears the matching reservation."""
        if grams > self.remaining_grams:
            raise ValueError(
                f"Batch {self.batch_code} has {self.remaining_grams}g left, {grams}g requested."
            )
        self.remaining_grams = F("remaining_grams") - grams
        self.reserved_grams = models.Case(
            models.When(reserved_grams__lte=grams, then=models.Value(0)),
            default=F("reserved_grams") - grams,
        )
        self.save(update_fields=["remaining_grams", "reserved_grams", "updated_at"])
        self.refresh_from_db(fields=["remaining_grams", "reserved_grams"])

        if self.remaining_grams == 0 and self.status == self.Status.AVAILABLE:
            self.status = self.Status.DEPLETED
            self.save(update_fields=["status", "updated_at"])

    def adjust(self, delta_grams, *, reason="recount", note="", actor=None):
        """Hand-correct remaining stock and record why.

        `delta_grams` is signed. The floor is `reserved_grams`, not zero:
        stock already promised to an unfulfilled order cannot be adjusted away
        without cancelling that order first — the database constraint
        `reserved_not_above_remaining` would reject it anyway, but failing
        here gives the packer a sentence instead of an IntegrityError.
        """
        from django.db import transaction

        delta_grams = int(delta_grams)
        if delta_grams == 0:
            raise ValueError("A zero adjustment records nothing.")

        with transaction.atomic():
            # Lock the row: two packers correcting the same batch at once would
            # otherwise both read the same `before` and one would be lost.
            fresh = RoastBatch.objects.select_for_update().get(pk=self.pk)

            before = fresh.remaining_grams
            after = before + delta_grams

            if after < 0:
                raise ValueError(
                    f"Batch {fresh.batch_code} holds {before}g; cannot remove {-delta_grams}g."
                )
            if after < fresh.reserved_grams:
                raise ValueError(
                    f"{fresh.reserved_grams}g of batch {fresh.batch_code} is reserved for "
                    f"unfulfilled orders; stock cannot go below that."
                )
            if after > fresh.initial_grams:
                raise ValueError(
                    f"Batch {fresh.batch_code} was roasted at {fresh.initial_grams}g; "
                    f"adjusting to {after}g would exceed it. Record a new batch instead."
                )

            fresh.remaining_grams = after

            # Keep status honest: emptying a batch depletes it, and refilling a
            # depleted one puts it back on sale.
            fields = ["remaining_grams", "updated_at"]
            if after == 0 and fresh.status == self.Status.AVAILABLE:
                fresh.status = self.Status.DEPLETED
                fields.append("status")
            elif after > 0 and fresh.status == self.Status.DEPLETED:
                fresh.status = self.Status.AVAILABLE
                fields.append("status")
            fresh.save(update_fields=fields)

            record = StockAdjustment.objects.create(
                batch=fresh,
                delta_grams=delta_grams,
                reason=reason,
                note=note,
                before_grams=before,
                after_grams=after,
                actor=actor,
            )

        self.refresh_from_db(fields=["remaining_grams", "status"])
        return record


class StockAdjustment(models.Model):
    """A manual correction to a batch's remaining stock, with its reason.

    Orders move stock through reserve/consume, which is self-explanatory. A
    hand correction is not: spillage, a miscount at packing, a returned bag.
    Recording it here means the difference between the books and the shelf is
    always attributable to someone and something.
    """

    class Reason(models.TextChoices):
        RECOUNT = "recount", _("Recount")
        SPILLAGE = "spillage", _("Spillage / loss")
        SAMPLE = "sample", _("Sample / cupping")
        RETURN = "return", _("Customer return")
        CORRECTION = "correction", _("Data correction")
        OTHER = "other", _("Other")

    batch = models.ForeignKey(
        RoastBatch,
        on_delete=models.CASCADE,
        related_name="adjustments",
        verbose_name=_("batch"),
    )
    # Signed: negative removes stock, positive adds it back.
    delta_grams = models.IntegerField(_("change (g)"))
    reason = models.CharField(
        _("reason"), max_length=16, choices=Reason.choices, default=Reason.RECOUNT
    )
    note = models.CharField(_("note"), max_length=200, blank=True)

    # Both sides of the change, so the record stays readable even if the batch
    # is adjusted again later.
    before_grams = models.PositiveIntegerField(_("before (g)"))
    after_grams = models.PositiveIntegerField(_("after (g)"))

    actor = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_adjustments",
        verbose_name=_("adjusted by"),
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("stock adjustment")
        verbose_name_plural = _("stock adjustments")
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["batch", "-created_at"])]

    def __str__(self):
        sign = "+" if self.delta_grams >= 0 else ""
        return f"{self.batch.batch_code} {sign}{self.delta_grams}g ({self.reason})"


class ProductImage(models.Model):
    """One photograph in a product's gallery.

    A separate table rather than more ImageFields on the product: the number of
    photos varies per coffee, and fixed `image_2`/`image_3` columns would cap
    it arbitrarily and leave holes when the middle one is removed.
    """

    product = models.ForeignKey(
        CoffeeProduct,
        on_delete=models.CASCADE,
        related_name="images",
        verbose_name=_("product"),
    )
    image = models.ImageField(_("image"), upload_to="products/")
    alt_text = models.CharField(
        _("alt text"), max_length=200, blank=True,
        help_text=_("Described for screen readers. Falls back to the product name."),
    )
    # Exactly one cover per product, enforced by the constraint below.
    is_cover = models.BooleanField(_("cover image"), default=False)
    sort_order = models.PositiveIntegerField(_("sort order"), default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("product image")
        verbose_name_plural = _("product images")
        # Explicit order first, then upload order — so a gallery the roaster
        # has not reordered still comes back oldest-first rather than at the
        # database's whim.
        ordering = ("sort_order", "created_at", "pk")
        constraints = [
            models.UniqueConstraint(
                fields=["product"],
                condition=models.Q(is_cover=True),
                name="unique_cover_per_product",
            )
        ]

    def __str__(self):
        return f"{self.product.name} — {self.pk}"

    def make_cover(self):
        """Promote this photo, demoting the previous cover.

        Demote-then-promote in a transaction: the partial unique constraint
        above rejects two covers, so setting the new one first would collide
        with the old.
        """
        with transaction.atomic():
            ProductImage.objects.filter(product=self.product, is_cover=True).exclude(
                pk=self.pk
            ).update(is_cover=False)
            if not self.is_cover:
                self.is_cover = True
                self.save(update_fields=["is_cover"])
            # The product's own `image` field is what the storefront cards and
            # every existing serializer read, so it has to follow the cover.
            self.product.image = self.image
            self.product.save(update_fields=["image", "updated_at"])
