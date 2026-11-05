from decimal import Decimal

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from catalog.models import CoffeeProduct

from .models import Order
from .serializers import (
    CartQuoteSerializer,
    OrderCreateSerializer,
    OrderListSerializer,
    OrderSerializer,
    OrderStatusUpdateSerializer,
)
from .shipping import DEFAULT_SHIPPING_METHOD, shipping_cost_for, shipping_options


class OrderViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """A customer's orders. Never deletable — cancel instead, so the trail stays."""

    permission_classes = (IsAuthenticated,)
    lookup_field = "number"
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filterset_fields = ("status", "payment_status")
    search_fields = ("number", "items__product_name", "tracking_code")
    ordering_fields = ("placed_at", "total_amount")
    ordering = ("-placed_at",)

    def get_queryset(self):
        # The list rows never render history, so don't pay for it there.
        qs = Order.objects.prefetch_related("items")
        if self.action != "list":
            # `payments` feeds the detail serializer's gateway_fee; prefetched
            # so serialising a page of orders stays a fixed number of queries.
            qs = qs.prefetch_related("items__product", "history__actor", "payments")

        user = self.request.user
        # Staff see the whole board; customers see only their own.
        if not (user.is_authenticated and user.is_roaster):
            qs = qs.filter(user=user)

        # `state=open` is what the orders page asks for by default: anything
        # still moving. `past` is the archive.
        state = self.request.query_params.get("state")
        if state == "open":
            qs = qs.open()
        elif state == "past":
            qs = qs.filter(status__in=Order.TERMINAL_STATUSES)

        # Searching across items can multiply rows; collapse them.
        return qs.distinct()

    def get_serializer_class(self):
        if self.action == "create":
            return OrderCreateSerializer
        if self.action == "list":
            return OrderListSerializer
        return OrderSerializer

    def _fresh(self, order):
        """Re-read the order before serialising it.

        `get_object()` arrives with `history` and `items` already prefetched;
        a transition adds a history row that the stale cache would hide, so
        the response would show the new status with the old history.
        """
        order = self.get_queryset().get(pk=order.pk)
        return OrderSerializer(order, context=self.get_serializer_context()).data

    @action(detail=True, methods=["post"])
    def cancel(self, request, number=None):
        """Customer-initiated cancellation, allowed only before dispatch."""
        order = self.get_object()

        if not order.can_be_cancelled:
            return Response(
                {"detail": f"سفارش در وضعیت «{order.get_status_display()}» قابل لغو نیست."},
                status=status.HTTP_409_CONFLICT,
            )

        order.transition_to(
            Order.Status.CANCELLED,
            actor=request.user,
            note=request.data.get("reason", "Cancelled by the customer."),
        )
        return Response(self._fresh(order))

    @action(detail=True, methods=["post"], url_path="status")
    def set_status(self, request, number=None):
        """Staff transition endpoint. The model decides which moves are legal."""
        order = self.get_object()

        if not request.user.is_roaster:
            return Response(
                {"detail": "Only roasters may change an order's status."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = OrderStatusUpdateSerializer(
            data=request.data, context={"request": request, "order": order}
        )
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response(self._fresh(order))


@api_view(["POST"])
@permission_classes((AllowAny,))
def quote_cart(request):
    """Price a cart without creating an order.

    The cart lives in the browser, so the totals shown there are the client's
    arithmetic. This endpoint is what the checkout page trusts: it re-reads
    every price from the database and reports what the order would actually
    cost, plus anything that has since gone out of stock.
    """
    # report_only: stock and grind problems come back as an `issues` list the
    # cart page can render, rather than a 400 that says only "invalid".
    serializer = CartQuoteSerializer(data=request.data, context={"report_only": True})
    serializer.is_valid(raise_exception=True)

    items = serializer.validated_data["items"]
    method = serializer.validated_data.get("shipping_method") or DEFAULT_SHIPPING_METHOD

    lines = []
    subtotal = Decimal("0")
    issues = []

    for entry in items:
        product = entry["product"]
        grams = entry["weight_grams"]
        quantity = entry["quantity"]

        unit_price = product.price_for_grams(grams)
        line_total = unit_price * quantity
        subtotal += line_total

        # Withdrawn from sale while it sat in the cart. Treated as a stock
        # problem rather than a missing object: the coffee is real, the
        # customer saw it, and the cart page needs to say so in words.
        is_sellable = product.status == CoffeeProduct.Status.PUBLISHED
        if not is_sellable:
            issues.append(
                {
                    "product": product.slug,
                    "code": "unavailable",
                    "detail": f"{product.name} دیگر برای فروش عرضه نمی‌شود.",
                    "available_grams": 0,
                }
            )

        available = product.available_grams if is_sellable else 0
        requested = grams * quantity
        if is_sellable and requested > available:
            issues.append(
                {
                    "product": product.slug,
                    "code": "insufficient_stock",
                    "detail": f"از {product.name} تنها {available} گرم موجود است.",
                    "available_grams": available,
                }
            )

        if entry["grind_type"] in ("espresso", "turkish") and not product.is_espresso_suitable:
            issues.append(
                {
                    "product": product.slug,
                    "code": "grind_unavailable",
                    "detail": f"{product.name} با این درجه آسیاب عرضه نمی‌شود.",
                }
            )

        lines.append(
            {
                "product": product.slug,
                "product_name": product.name,
                "product_origin": product.origin_country,
                "image": product.image.url if product.image else None,
                "weight_grams": grams,
                "grind_type": entry["grind_type"],
                "quantity": quantity,
                "unit_price": unit_price,
                "line_total": line_total,
                "available_grams": available,
                "is_available": is_sellable and requested <= available,
            }
        )

    shipping = shipping_cost_for(method, subtotal)

    return Response(
        {
            "items": lines,
            "subtotal": subtotal,
            "shipping_method": method,
            "shipping_cost": shipping,
            "discount_amount": Decimal("0"),
            "total": subtotal + shipping,
            "total_grams": sum(l["weight_grams"] * l["quantity"] for l in lines),
            "issues": issues,
            "is_orderable": not issues and bool(lines),
            "shipping_options": shipping_options(subtotal),
        }
    )


@api_view(["GET"])
@permission_classes((AllowAny,))
def shipping_methods(request):
    """Shipping methods, priced against an optional `subtotal` query param."""
    try:
        subtotal = Decimal(request.query_params.get("subtotal", "0"))
    except Exception:
        subtotal = Decimal("0")
    return Response(shipping_options(subtotal))
