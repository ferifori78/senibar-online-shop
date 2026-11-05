from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from accounts.models import Address
from catalog.models import CoffeeProduct
from config.digits import digits_only, to_english_digits

from .models import GrindType, Order, OrderItem, OrderStatusHistory, ShippingMethod
from .shipping import DEFAULT_SHIPPING_METHOD


class ShippingMethodKeyField(serializers.CharField):
    """A shipping method key, checked against the table on every request.

    Not a ChoiceField: the choices now live in the database, and a list built
    once at import time would go stale the moment the roastery adds a method.
    """

    def to_internal_value(self, data):
        key = super().to_internal_value(data)
        if not ShippingMethod.objects.filter(key=key, is_active=True).exists():
            raise serializers.ValidationError("روش ارسال انتخاب‌شده معتبر نیست.")
        return key


class ShippingMethodSerializer(serializers.ModelSerializer):
    """Full record — the back-office editor. `key` is writable on create only;
    orders store it verbatim, so renaming it would strand them."""

    order_count = serializers.SerializerMethodField()

    class Meta:
        model = ShippingMethod
        fields = (
            "id", "key", "label", "description", "days",
            "cost", "free_over", "is_active", "sort_order",
            "order_count", "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def get_order_count(self, obj):
        """Lets the editor explain why a method cannot be deleted."""
        return Order.objects.filter(shipping_method=obj.key).count()

    def get_fields(self):
        fields = super().get_fields()
        if self.instance is not None:
            fields["key"].read_only = True
        return fields


class OrderItemSerializer(serializers.ModelSerializer):
    grind_display = serializers.CharField(source="get_grind_type_display", read_only=True)
    line_total = serializers.DecimalField(max_digits=12, decimal_places=0, read_only=True)
    total_grams = serializers.IntegerField(read_only=True)
    needs_grinding = serializers.BooleanField(read_only=True)
    batch_code = serializers.CharField(source="batch.batch_code", read_only=True, default=None)

    class Meta:
        model = OrderItem
        fields = (
            "id", "product", "product_name", "product_origin", "batch", "batch_code",
            "weight_grams", "grind_type", "grind_display", "quantity",
            "unit_price", "line_total", "total_grams", "needs_grinding", "note",
        )
        read_only_fields = (
            "id", "product_name", "product_origin", "batch", "unit_price",
        )


class OrderItemWriteSerializer(serializers.Serializer):
    """Checkout input. Price is never accepted from the client — it is read off
    the product server-side."""

    # Checkout resolves against published coffees only. The quote endpoint
    # widens this in __init__: a coffee archived while it sat in someone's cart
    # must come back as a line-level issue the cart page can explain, not a 400
    # reading "invalid pk" that takes the whole cart down with it.
    product = serializers.PrimaryKeyRelatedField(
        queryset=CoffeeProduct.objects.published()
    )

    def get_fields(self):
        """Widen the product lookup for the quote endpoint.

        Not `__init__`: with `many=True` the child is built before the parent's
        context is attached, so `self.context` is still empty there. `get_fields`
        runs on first access, by which time the context has arrived.
        """
        fields = super().get_fields()
        if self.context.get("report_only"):
            fields["product"].queryset = CoffeeProduct.objects.all()
        return fields
    # Not a ChoiceField: those four sizes are how coffee is sold, but a pantry
    # pack is whatever the manufacturer printed on it. Required only for a lot
    # — a package item's weight comes from the product, not the client.
    weight_grams = serializers.IntegerField(min_value=1, required=False)
    grind_type = serializers.ChoiceField(choices=GrindType.choices, default=GrindType.WHOLE)
    quantity = serializers.IntegerField(min_value=1, max_value=99, default=1)
    note = serializers.CharField(max_length=200, required=False, allow_blank=True)

    def validate(self, attrs):
        product = attrs["product"]

        # Fill in what the client is not allowed to choose, BEFORE the quote
        # short-circuit below: the cart prices these lines too, and a package
        # line with no weight would price at zero.
        if product.is_pantry:
            attrs["grind_type"] = GrindType.WHOLE
            if product.sold_by_package:
                attrs["weight_grams"] = product.package_grams or 1
            elif not attrs.get("weight_grams"):
                raise serializers.ValidationError(
                    {"weight_grams": f"{product.name} is sold by weight; choose an amount."}
                )
        else:
            if not attrs.get("weight_grams"):
                raise serializers.ValidationError({"weight_grams": "This field is required."})
            if attrs["weight_grams"] not in OrderItem.Weight.values:
                raise serializers.ValidationError(
                    {"weight_grams": "Not a weight this coffee is sold in."}
                )

        # The quote endpoint reports problems as a list the cart page can act
        # on, rather than rejecting the whole request; checkout still enforces.
        if self.context.get("report_only"):
            return attrs

        grind = attrs["grind_type"]
        if grind in (GrindType.ESPRESSO, GrindType.TURKISH) and not product.is_espresso_suitable:
            raise serializers.ValidationError(
                {"grind_type": f"{product.name} is not offered at this grind."}
            )

        # Stock is counted in the unit the product is actually sold in, and the
        # message says so: telling someone "only 400g available" when they are
        # buying sealed packs is not something they can act on.
        if product.sold_by_package:
            if attrs["quantity"] > product.available_packages:
                raise serializers.ValidationError(
                    {"quantity": f"Only {product.available_packages} of {product.name} is available."}
                )
        else:
            requested = attrs["weight_grams"] * attrs["quantity"]
            if requested > product.available_grams:
                raise serializers.ValidationError(
                    {"quantity": f"Only {product.available_grams}g of {product.name} is available."}
                )
        return attrs


class CartQuoteSerializer(serializers.Serializer):
    """Input for pricing a browser-side cart. Anonymous callers welcome —
    the checkout page needs a trustworthy total before anyone signs in."""

    items = OrderItemWriteSerializer(many=True, allow_empty=False)
    shipping_method = ShippingMethodKeyField(required=False)

    def validate_items(self, value):
        if len(value) > 50:
            raise serializers.ValidationError("Too many lines in one cart.")
        return value


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.display_name", read_only=True, default=None)
    from_display = serializers.CharField(source="get_from_status_display", read_only=True)
    to_display = serializers.CharField(source="get_to_status_display", read_only=True)

    class Meta:
        model = OrderStatusHistory
        fields = (
            "id", "from_status", "from_display", "to_status", "to_display",
            "actor", "actor_name", "note", "created_at",
        )
        read_only_fields = fields


class OrderListSerializer(serializers.ModelSerializer):
    """Row payload for "my orders". Carries enough to render a card without a
    second request per order: what's inside, and where it is in the pipeline."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    payment_status_display = serializers.CharField(
        source="get_payment_status_display", read_only=True
    )
    # Counted off the prefetched list, not `items.count` — that would fire a
    # COUNT query per row and turn the list into an N+1.
    item_count = serializers.SerializerMethodField()
    total_grams = serializers.SerializerMethodField()
    pipeline_position = serializers.IntegerField(read_only=True)
    pipeline_length = serializers.SerializerMethodField()
    is_open = serializers.BooleanField(read_only=True)
    can_be_cancelled = serializers.BooleanField(read_only=True)
    summary = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            "id", "number", "status", "status_display",
            "payment_status", "payment_status_display",
            "total_amount", "item_count", "total_grams", "summary",
            "pipeline_position", "pipeline_length", "is_open", "can_be_cancelled",
            "placed_at", "shipped_at", "delivered_at",
        )

    def get_pipeline_length(self, obj):
        return len(obj.PIPELINE)

    def get_item_count(self, obj):
        return len(obj.items.all())

    def get_total_grams(self, obj):
        return sum(item.weight_grams * item.quantity for item in obj.items.all())

    def get_summary(self, obj):
        """The coffees in this order, named. Two, then a count for the rest."""
        names = [item.product_name for item in obj.items.all()]
        if len(names) <= 2:
            return "، ".join(names)
        return "، ".join(names[:2]) + f" و {len(names) - 2} مورد دیگر"


class OrderSerializer(serializers.ModelSerializer):
    """Full order payload, including the Timeline register's stage data."""

    items = OrderItemSerializer(many=True, read_only=True)
    history = OrderStatusHistorySerializer(many=True, read_only=True)
    timeline = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    payment_status_display = serializers.CharField(
        source="get_payment_status_display", read_only=True
    )
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=0, read_only=True)
    total_grams = serializers.IntegerField(read_only=True)
    can_be_cancelled = serializers.BooleanField(read_only=True)
    requires_grinding = serializers.BooleanField(read_only=True)
    gateway_fee = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            "id", "number", "user", "status", "status_display",
            "payment_status", "payment_status_display",
            "recipient_name", "recipient_phone", "province", "city",
            "street_address", "postal_code",
            "items", "subtotal", "shipping_cost", "discount_amount", "total_amount",
            "gateway_fee",
            "total_grams", "requires_grinding", "can_be_cancelled",
            "customer_note", "tracking_code", "timeline", "history",
            "placed_at", "paid_at", "roasted_at", "shipped_at", "delivered_at",
        )
        read_only_fields = (
            "id", "number", "user", "status", "payment_status", "total_amount",
            "placed_at", "paid_at", "roasted_at", "shipped_at", "delivered_at",
        )

    def get_timeline(self, obj):
        return obj.timeline()

    def get_gateway_fee(self, obj):
        """What the shop paid the gateway to collect this order.

        Shown on the invoice as a cost the shop absorbed — it is not part of
        the customer's total. Read off the prefetched `payments` list rather
        than queried, so a list of orders stays one query.
        """
        for payment in obj.payments.all():
            if payment.status == "paid":
                return payment.gateway_fee
        return Decimal("0")


class OrderCreateSerializer(serializers.Serializer):
    """Checkout. Takes a saved address (or literal fields) plus line items, and
    builds the order in one transaction."""

    address_id = serializers.IntegerField(required=False)
    recipient_name = serializers.CharField(max_length=120, required=False)
    recipient_phone = serializers.CharField(max_length=20, required=False)
    province = serializers.CharField(max_length=60, required=False)
    city = serializers.CharField(max_length=60, required=False)
    street_address = serializers.CharField(required=False)
    postal_code = serializers.CharField(max_length=20, required=False)

    items = OrderItemWriteSerializer(many=True)
    customer_note = serializers.CharField(required=False, allow_blank=True)
    # The client picks a method, never a price: the cost is looked up server-side.
    shipping_method = ShippingMethodKeyField(default=DEFAULT_SHIPPING_METHOD)

    ADDRESS_FIELDS = (
        "recipient_name", "recipient_phone", "province", "city", "street_address", "postal_code",
    )

    # An address typed on a Persian keyboard arrives with Persian digits. The
    # courier's label and the postal code both need ASCII.
    def validate_recipient_phone(self, value):
        return digits_only(value)

    def validate_postal_code(self, value):
        return digits_only(value)

    def validate_street_address(self, value):
        return to_english_digits(value)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("An order needs at least one item.")

        seen = set()
        for item in value:
            key = (item["product"].pk, item["weight_grams"], item["grind_type"])
            if key in seen:
                raise serializers.ValidationError(
                    "Duplicate line: merge the same product, weight and grind into one quantity."
                )
            seen.add(key)
        return value

    def validate(self, attrs):
        user = self.context["request"].user

        if address_id := attrs.get("address_id"):
            try:
                address = Address.objects.get(pk=address_id, user=user)
            except Address.DoesNotExist:
                raise serializers.ValidationError({"address_id": "Address not found."})
            attrs["_address"] = address
            snapshot = address.as_snapshot()
            attrs["recipient_name"] = snapshot["recipient_name"]
            attrs["recipient_phone"] = snapshot["phone"]
            for field in ("province", "city", "street_address", "postal_code"):
                attrs[field] = snapshot[field]
        else:
            missing = [f for f in self.ADDRESS_FIELDS if not attrs.get(f)]
            if missing:
                raise serializers.ValidationError(
                    {f: "Required when no saved address is given." for f in missing}
                )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user = self.context["request"].user
        items_data = validated_data.pop("items")
        address = validated_data.pop("_address", None)
        validated_data.pop("address_id", None)

        order = Order.objects.create(user=user, address=address, **validated_data)

        for item in items_data:
            product = item["product"]
            OrderItem.objects.create(
                order=order,
                product=product,
                weight_grams=item["weight_grams"],
                grind_type=item["grind_type"],
                quantity=item["quantity"],
                note=item.get("note", ""),
                unit_price=product.price_for_grams(item["weight_grams"]),
            )

        order.recalculate_total()

        # Announced on the shop's own channel after the total is final, so the
        # message never shows a half-built order. Queued on commit and its
        # failures swallowed — see Order._queue_notification.
        order._queue_notification("order_placed", order.pk, module="feed")

        return order

    def to_representation(self, instance):
        return OrderSerializer(instance, context=self.context).data


class OrderStatusUpdateSerializer(serializers.Serializer):
    """Admin transition endpoint. The model enforces which moves are legal."""

    status = serializers.ChoiceField(choices=Order.Status.choices)
    note = serializers.CharField(required=False, allow_blank=True)

    def validate_status(self, value):
        order = self.context["order"]
        if value not in order.ALLOWED_TRANSITIONS[Order.Status(order.status)]:
            raise serializers.ValidationError(
                f"Cannot move from {order.get_status_display()} to {Order.Status(value).label}."
            )
        return value

    def save(self, **kwargs):
        order = self.context["order"]
        return order.transition_to(
            self.validated_data["status"],
            actor=self.context["request"].user,
            note=self.validated_data.get("note", ""),
        )
