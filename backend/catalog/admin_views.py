"""Staff-only inventory endpoints, backing the panel's INVENTORY screen."""

from django.db.models import F
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from .models import PEAK_DAYS, CoffeeProduct, RoastBatch, StockAdjustment


class IsRoaster(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.is_roaster)


# Below this, a coffee is worth reordering rather than selling down.
LOW_STOCK_GRAMS = 1000


class StockAdjustmentSerializer(serializers.ModelSerializer):
    batch_code = serializers.CharField(source="batch.batch_code", read_only=True)
    product_name = serializers.CharField(source="batch.product.name", read_only=True)
    actor_name = serializers.SerializerMethodField()
    reason_display = serializers.CharField(source="get_reason_display", read_only=True)

    class Meta:
        model = StockAdjustment
        fields = (
            "id",
            "batch_code",
            "product_name",
            "delta_grams",
            "reason",
            "reason_display",
            "note",
            "before_grams",
            "after_grams",
            "actor_name",
            "created_at",
        )

    def get_actor_name(self, obj):
        if not obj.actor:
            return ""
        full = f"{obj.actor.first_name} {obj.actor.last_name}".strip()
        return full or obj.actor.email.split("@")[0]


@api_view(["GET"])
@permission_classes((IsRoaster,))
def inventory(request):
    """Stock per coffee, with the batches behind each number.

    Sellable stock is `remaining - reserved`: grams already promised to an
    unfulfilled order are on the shelf but not for sale, and reporting them as
    available is how a shop oversells.
    """
    sellable = F("remaining_grams") - F("reserved_grams")

    batches = (
        RoastBatch.objects.filter(
            status__in=(RoastBatch.Status.RESTING, RoastBatch.Status.AVAILABLE)
        )
        .select_related("product")
        .annotate(sellable_grams=sellable)
        .order_by("product__name", "roast_date")
    )

    # Grouped in Python rather than a second query: the working set here is one
    # roastery's live batches, not a table scan.
    by_product = {}
    for batch in batches:
        row = by_product.setdefault(
            batch.product_id,
            {
                "product_id": batch.product_id,
                "name": batch.product.name,
                "slug": batch.product.slug,
                "status": batch.product.status,
                "remaining_grams": 0,
                "reserved_grams": 0,
                "sellable_grams": 0,
                "batch_count": 0,
                "batches": [],
            },
        )
        row["remaining_grams"] += batch.remaining_grams
        row["reserved_grams"] += batch.reserved_grams
        row["sellable_grams"] += batch.sellable_grams
        row["batch_count"] += 1
        row["batches"].append(
            {
                "id": batch.id,
                "batch_code": batch.batch_code,
                "roast_date": batch.roast_date,
                "status": batch.status,
                "initial_grams": batch.initial_grams,
                "remaining_grams": batch.remaining_grams,
                "reserved_grams": batch.reserved_grams,
                "sellable_grams": batch.sellable_grams,
                "days_since_roast": batch.days_since_roast,
                "freshness": batch.freshness,
            }
        )

    rows = sorted(by_product.values(), key=lambda r: r["sellable_grams"])

    # Published coffees with no live batch at all: the ones a customer can see
    # but cannot buy. These are the most urgent line on the screen, and a
    # batch-only query would never surface them.
    stocked_ids = set(by_product)
    for product in CoffeeProduct.objects.filter(
        status=CoffeeProduct.Status.PUBLISHED
    ).exclude(id__in=stocked_ids):
        rows.insert(
            0,
            {
                "product_id": product.id,
                "name": product.name,
                "slug": product.slug,
                "status": product.status,
                "remaining_grams": 0,
                "reserved_grams": 0,
                "sellable_grams": 0,
                "batch_count": 0,
                "batches": [],
            },
        )

    totals = {
        "products_tracked": len(rows),
        "out_of_stock": sum(1 for r in rows if r["sellable_grams"] <= 0),
        "low_stock": sum(
            1 for r in rows if 0 < r["sellable_grams"] < LOW_STOCK_GRAMS
        ),
        "total_sellable_grams": sum(r["sellable_grams"] for r in rows),
        "total_reserved_grams": sum(r["reserved_grams"] for r in rows),
        "low_stock_threshold": LOW_STOCK_GRAMS,
    }

    # Batches past their peak that still hold stock — sell or withdraw.
    fading = [
        {
            "id": b.id,
            "batch_code": b.batch_code,
            "product_name": b.product.name,
            "roast_date": b.roast_date,
            "days_since_roast": b.days_since_roast,
            "sellable_grams": b.sellable_grams,
        }
        for b in batches
        if b.days_since_roast > PEAK_DAYS and b.sellable_grams > 0
    ]

    return Response({"totals": totals, "products": rows, "fading": fading})


@api_view(["POST"])
@permission_classes((IsRoaster,))
def adjust_stock(request, pk):
    """Hand-correct one batch's stock, recording who and why."""
    try:
        batch = RoastBatch.objects.select_related("product").get(pk=pk)
    except RoastBatch.DoesNotExist:
        raise NotFound("این بچ یافت نشد.")

    raw_delta = request.data.get("delta_grams")
    try:
        delta = int(raw_delta)
    except (TypeError, ValueError):
        raise ValidationError({"delta_grams": "یک عدد صحیح بفرستید."})

    reason = request.data.get("reason", StockAdjustment.Reason.RECOUNT)
    if reason not in {choice for choice, _ in StockAdjustment.Reason.choices}:
        raise ValidationError({"reason": "دلیل نامعتبر است."})

    note = (request.data.get("note") or "")[:200]

    # A loss without a word of explanation is the record we most regret later.
    if reason == StockAdjustment.Reason.OTHER and not note.strip():
        raise ValidationError({"note": "برای دلیل «سایر» توضیح لازم است."})

    try:
        record = batch.adjust(delta, reason=reason, note=note, actor=request.user)
    except ValueError as exc:
        # The model's guards speak in whole sentences; pass them through.
        raise ValidationError({"delta_grams": str(exc)})

    return Response(
        StockAdjustmentSerializer(record).data, status=status.HTTP_201_CREATED
    )


@api_view(["GET"])
@permission_classes((IsRoaster,))
def adjustment_log(request):
    """Recent hand corrections, newest first."""
    qs = StockAdjustment.objects.select_related("batch__product", "actor")

    batch_id = request.query_params.get("batch")
    if batch_id:
        qs = qs.filter(batch_id=batch_id)

    return Response(StockAdjustmentSerializer(qs[:100], many=True).data)
