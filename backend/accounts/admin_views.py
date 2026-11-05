"""Staff-only customer management, backing the panel's USERS screen."""

from django.db.models import Count, DecimalField, Max, Q, Sum
from django.db.models.functions import Coalesce
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from orders.models import Order

from .models import CustomUser

ZERO_MONEY = Coalesce(
    Sum("orders__total_amount", filter=Q(orders__payment_status=Order.PaymentStatus.PAID)),
    0,
    output_field=DecimalField(max_digits=14, decimal_places=0),
)


class IsRoaster(BasePermission):
    """Staff-only. The back office has no read-only visitor tier."""

    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.is_roaster)


class AdminUserSerializer(serializers.ModelSerializer):
    """A customer as the roastery sees them: who they are, and what they bought.

    Spend and counts come from annotations on the queryset, so listing N users
    stays one query rather than N.
    """

    display_name = serializers.SerializerMethodField()
    order_count = serializers.IntegerField(read_only=True)
    paid_order_count = serializers.IntegerField(read_only=True)
    total_spent = serializers.DecimalField(
        max_digits=14, decimal_places=0, read_only=True
    )
    last_order_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = CustomUser
        fields = (
            "id",
            "email",
            "phone",
            "first_name",
            "last_name",
            "display_name",
            "role",
            "is_active",
            "accepts_marketing",
            "preferred_grind",
            "date_joined",
            "last_login",
            "order_count",
            "paid_order_count",
            "total_spent",
            "last_order_at",
        )
        # Everything identifying is read-only here: this screen exists to see
        # customers and adjust standing, not to edit their details behind their
        # back. Only `role` and `is_active` are writable, via their own actions.
        read_only_fields = fields

    def get_display_name(self, obj):
        full = f"{obj.first_name} {obj.last_name}".strip()
        return full or obj.email.split("@")[0]


class AdminUserViewSet(viewsets.ReadOnlyModelViewSet):
    """List and inspect customers. Mutations are explicit, named actions."""

    permission_classes = (IsRoaster,)
    serializer_class = AdminUserSerializer
    search_fields = ("email", "first_name", "last_name", "phone")
    ordering_fields = ("date_joined", "last_login", "total_spent", "order_count")
    ordering = ("-date_joined",)

    def get_queryset(self):
        qs = CustomUser.objects.annotate(
            order_count=Count("orders", distinct=True),
            paid_order_count=Count(
                "orders",
                filter=Q(orders__payment_status=Order.PaymentStatus.PAID),
                distinct=True,
            ),
            total_spent=ZERO_MONEY,
            last_order_at=Max("orders__placed_at"),
        )

        role = self.request.query_params.get("role")
        if role:
            qs = qs.filter(role=role)

        active = self.request.query_params.get("is_active")
        if active in ("true", "false"):
            qs = qs.filter(is_active=(active == "true"))

        # "Has ever paid for something" — the useful split for a roastery.
        buyers = self.request.query_params.get("buyers")
        if buyers == "true":
            qs = qs.filter(paid_order_count__gt=0)
        elif buyers == "false":
            qs = qs.filter(paid_order_count=0)

        return qs

    @action(detail=True, methods=["get"])
    def orders(self, request, pk=None):
        """This customer's order history — the panel's drill-down."""
        user = self.get_object()
        rows = (
            Order.objects.filter(user=user)
            .order_by("-placed_at")
            .values(
                "number",
                "status",
                "payment_status",
                "total_amount",
                "placed_at",
                "paid_at",
            )[:50]
        )
        return Response(list(rows))

    @action(detail=True, methods=["post"], url_path="role")
    def set_role(self, request, pk=None):
        """Promote or demote. Guarded so the panel cannot lock itself out."""
        user = self.get_object()
        new_role = request.data.get("role")

        valid = {choice for choice, _ in CustomUser.Role.choices}
        if new_role not in valid:
            raise ValidationError({"role": f"Must be one of: {', '.join(sorted(valid))}."})

        # Removing your own staff access would end the session that is doing it,
        # leaving no way back except the command line.
        if user.pk == request.user.pk and new_role == CustomUser.Role.CUSTOMER:
            raise PermissionDenied("نمی‌توانید نقش خودتان را به مشتری تغییر دهید.")

        # The last remaining admin must not be demoted by anyone.
        if user.role == CustomUser.Role.ADMIN and new_role != CustomUser.Role.ADMIN:
            others = CustomUser.objects.filter(
                role=CustomUser.Role.ADMIN, is_active=True
            ).exclude(pk=user.pk)
            if not others.exists():
                raise PermissionDenied("آخرین ادمین فعال را نمی‌توان تنزل داد.")

        user.role = new_role
        # Staff roles need the Django admin flag too, or /admin/ refuses them.
        user.is_staff = new_role in (CustomUser.Role.ROASTER, CustomUser.Role.ADMIN)
        user.save(update_fields=["role", "is_staff", "updated_at"])

        return Response(self.get_serializer(self.get_queryset().get(pk=user.pk)).data)

    @action(detail=True, methods=["post"], url_path="active")
    def set_active(self, request, pk=None):
        """Suspend or restore an account. Never deletes: orders reference it."""
        user = self.get_object()
        value = request.data.get("is_active")
        if not isinstance(value, bool):
            raise ValidationError({"is_active": "Must be true or false."})

        if user.pk == request.user.pk and not value:
            raise PermissionDenied("نمی‌توانید حساب خودتان را غیرفعال کنید.")

        user.is_active = value
        user.save(update_fields=["is_active", "updated_at"])
        return Response(self.get_serializer(self.get_queryset().get(pk=user.pk)).data)

