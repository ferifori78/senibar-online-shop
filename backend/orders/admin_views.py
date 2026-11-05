"""Staff-only endpoints backing the Terminal register."""

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, F, Q, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from catalog.models import STALE_DAYS, CoffeeProduct, RoastBatch

from .models import GrindType, Order, OrderItem, ShippingMethod
from .serializers import ShippingMethodSerializer


class IsRoaster(BasePermission):
    """Staff-only. Never a read-only fallback — this is the back office."""

    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.is_roaster)


ZERO = Decimal("0")


def _money(expression):
    """Sum that returns 0 rather than None when nothing matches."""
    return Coalesce(expression, ZERO, output_field=DecimalField(max_digits=14, decimal_places=0))


@api_view(["GET"])
@permission_classes((IsRoaster,))
def dashboard(request):
    """The numbers the roastery reads first thing in the morning."""
    now = timezone.now()
    today = timezone.localdate()
    week_ago = today - timedelta(days=6)

    paid = Order.objects.filter(payment_status=Order.PaymentStatus.PAID)

    # --- Revenue ----------------------------------------------------------
    today_sales = paid.filter(paid_at__date=today).aggregate(
        total=_money(Sum("total_amount")), count=Count("id")
    )
    week_sales = paid.filter(paid_at__date__gte=week_ago).aggregate(
        total=_money(Sum("total_amount")), count=Count("id")
    )

    # --- The production queue --------------------------------------------
    awaiting_roast = Order.objects.awaiting_roast()
    in_production = Order.objects.in_production()

    # Grams to roast, per coffee. This is the roast plan.
    roast_plan = list(
        OrderItem.objects.filter(order__in=awaiting_roast)
        .values(name=F("product_name"), slug=F("product__slug"))
        .annotate(grams=Sum(F("weight_grams") * F("quantity")), lines=Count("id"))
        .order_by("-grams")
    )

    # --- Grinding ---------------------------------------------------------
    grind_queue = (
        OrderItem.objects.filter(order__status=Order.Status.ROASTING)
        .exclude(grind_type=GrindType.WHOLE)
        .values("grind_type")
        .annotate(grams=Sum(F("weight_grams") * F("quantity")), lines=Count("id"))
    )

    # --- Stock ------------------------------------------------------------
    stale_cutoff = today - timedelta(days=STALE_DAYS)
    batches = RoastBatch.objects.filter(status=RoastBatch.Status.AVAILABLE)

    low_stock = [
        {
            "batch_code": b.batch_code,
            "product": b.product.name,
            "remaining_grams": b.remaining_grams,
            "available_grams": b.available_grams,
            "roast_date": b.roast_date,
            "freshness": b.freshness,
        }
        for b in batches.select_related("product").order_by("remaining_grams")[:8]
        if b.available_grams < 1000
    ]

    going_stale = [
        {
            "batch_code": b.batch_code,
            "product": b.product.name,
            "remaining_grams": b.remaining_grams,
            "days_since_roast": b.days_since_roast,
            "freshness": b.freshness,
        }
        for b in batches.select_related("product")
        .filter(roast_date__lt=today - timedelta(days=21), remaining_grams__gt=0)
        .order_by("roast_date")[:8]
    ]

    # --- Seven-day sales, for the dashboard's bar chart -------------------
    daily = (
        paid.filter(paid_at__date__gte=week_ago)
        .annotate(day=TruncDate("paid_at"))
        .values("day")
        .annotate(total=_money(Sum("total_amount")), count=Count("id"))
        .order_by("day")
    )
    by_day = {row["day"]: row for row in daily}
    sales_series = []
    for offset in range(7):
        day = week_ago + timedelta(days=offset)
        row = by_day.get(day)
        sales_series.append(
            {
                "date": day,
                "total": row["total"] if row else ZERO,
                "count": row["count"] if row else 0,
            }
        )

    return Response(
        {
            "generated_at": now,
            "sales": {
                "today": today_sales["total"],
                "today_orders": today_sales["count"],
                "week": week_sales["total"],
                "week_orders": week_sales["count"],
                "series": sales_series,
            },
            "queue": {
                "awaiting_roast": awaiting_roast.count(),
                "roasting": Order.objects.filter(status=Order.Status.ROASTING).count(),
                "ground": Order.objects.filter(status=Order.Status.GROUND).count(),
                "packed": Order.objects.filter(status=Order.Status.PACKED).count(),
                "shipped": Order.objects.filter(status=Order.Status.SHIPPED).count(),
                "in_production": in_production.count(),
                "unpaid": Order.objects.filter(
                    status=Order.Status.PENDING, payment_status=Order.PaymentStatus.UNPAID
                ).count(),
            },
            "roast_plan": roast_plan,
            "grind_queue": list(grind_queue),
            "stock": {
                "low": low_stock,
                "going_stale": going_stale,
                "available_batches": batches.filter(
                    roast_date__gte=stale_cutoff, remaining_grams__gt=0
                ).count(),
                "total_grams": batches.aggregate(g=Coalesce(Sum("remaining_grams"), 0))["g"],
            },
            "catalog": {
                "published": CoffeeProduct.objects.published().count(),
                "draft": CoffeeProduct.objects.filter(
                    status=CoffeeProduct.Status.DRAFT
                ).count(),
                "out_of_stock": sum(
                    1 for p in CoffeeProduct.objects.published() if not p.is_in_stock
                ),
            },
        }
    )


@api_view(["GET"])
@permission_classes((IsRoaster,))
def order_board(request):
    """One flat row per order line — the dense table the Terminal renders.

    Deliberately not the nested order payload: an operator reads across
    columns, not down a tree, and a 3-line order should be 3 rows.
    """
    orders = (
        Order.objects.select_related("user")
        # `items__batch` too: each row prints its batch code, and without this
        # the board fires one query per line.
        .prefetch_related("items__batch")
        .exclude(status__in=[Order.Status.CANCELLED, Order.Status.REFUNDED])
    )

    state = request.query_params.get("state")
    if state == "queue":
        orders = orders.filter(
            status__in=[Order.Status.PENDING, Order.Status.ROASTING, Order.Status.GROUND]
        )
    elif state:
        orders = orders.filter(status=state)

    search = request.query_params.get("search")
    if search:
        orders = orders.filter(
            Q(number__icontains=search)
            | Q(user__email__icontains=search)
            | Q(recipient_name__icontains=search)
            | Q(items__product_name__icontains=search)
        ).distinct()

    def line_matches(order, item):
        """When searching by coffee name, emit only the matching lines — not
        every line of an order that happens to contain it."""
        if not search:
            return True
        term = search.lower()
        if term in item.product_name.lower():
            return True
        # The order itself matched (by number, customer, email): keep all lines.
        return (
            term in order.number.lower()
            or term in order.recipient_name.lower()
            or term in order.user.email.lower()
        )

    rows = []
    for order in orders.order_by("placed_at")[:200]:
        for item in order.items.all():
            if not line_matches(order, item):
                continue
            rows.append(
                {
                    "order_number": order.number,
                    "order_status": order.status,
                    "payment_status": order.payment_status,
                    "customer": order.recipient_name,
                    "customer_email": order.user.email,
                    "city": order.city,
                    "product_name": item.product_name,
                    "grind_type": item.grind_type,
                    "weight_grams": item.weight_grams,
                    "quantity": item.quantity,
                    "total_grams": item.weight_grams * item.quantity,
                    "batch_code": item.batch.batch_code if item.batch_id else None,
                    "placed_at": order.placed_at,
                    "total_amount": order.total_amount,
                }
            )

    return Response({"count": len(rows), "results": rows})


class ShippingMethodViewSet(viewsets.ModelViewSet):
    """Shipping rates, editable from the Terminal register. Staff only.

    Lists inactive methods too — withdrawing one is the normal way to retire
    it, and the operator has to be able to see and undo that.
    """

    queryset = ShippingMethod.objects.all()
    serializer_class = ShippingMethodSerializer
    permission_classes = (IsRoaster,)

    def destroy(self, request, *args, **kwargs):
        method = self.get_object()

        # An order stores the key, not a foreign key, so nothing stops the
        # delete at the database level — but it would leave those orders unable
        # to reprice, and the packing slip unable to name how it shipped.
        if Order.objects.filter(shipping_method=method.key).exists():
            return Response(
                {
                    "detail": (
                        f"روش ارسال «{method.label}» در سفارش‌ها استفاده شده و قابل حذف نیست. "
                        "به‌جای آن غیرفعالش کنید."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        return super().destroy(request, *args, **kwargs)
