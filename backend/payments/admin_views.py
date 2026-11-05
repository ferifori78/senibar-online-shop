"""Staff-only payment endpoints, backing the panel's GATEWAYS screen."""

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from .gateways import GatewayError, get_gateway
from .models import GatewayToggle, Payment


class IsRoaster(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.is_roaster)


def _describe(name):
    """One gateway's state, as the panel needs to render a row.

    Three separate facts, deliberately not collapsed into one boolean: a
    gateway can be switched on but unusable (no key), and the roaster needs to
    see which of the two is stopping it reaching customers.
    """
    toggle = GatewayToggle.objects.filter(name=name).first()

    label, configured, problem = name, False, ""
    try:
        driver = get_gateway(name)
        label, configured = driver.label, True
    except GatewayError as exc:
        problem = str(exc)

    is_enabled = toggle.is_enabled if toggle else True

    return {
        "name": name,
        "label": label,
        # The switch in the back office.
        "is_enabled": is_enabled,
        # Whether credentials exist in the environment. Read-only here: keys
        # live in .env, never in the database.
        "is_configured": configured,
        # What a customer actually sees at checkout.
        "is_live": is_enabled and configured,
        "problem": problem,
        "note": toggle.note if toggle else "",
        # Volume, so switching one off is an informed decision.
        "paid_count": Payment.objects.filter(
            gateway=name, status=Payment.Status.PAID
        ).count(),
    }


@api_view(["GET"])
@permission_classes((IsRoaster,))
def gateway_admin_list(request):
    """Every gateway this deployment knows about, live or not."""
    return Response(
        {
            "gateways": [_describe(name) for name in settings.PAYMENT_GATEWAYS],
            "default": settings.PAYMENT_GATEWAY,
        }
    )


@api_view(["POST"])
@permission_classes((IsRoaster,))
def gateway_set_enabled(request, name):
    """Switch one gateway on or off for checkout."""
    if name not in settings.PAYMENT_GATEWAYS:
        raise ValidationError(
            {
                "name": (
                    "این درگاه در تنظیمات سرور تعریف نشده است. "
                    "برای افزودن آن، PAYMENT_GATEWAYS را در فایل .env ویرایش کنید."
                )
            }
        )

    value = request.data.get("is_enabled")
    if not isinstance(value, bool):
        raise ValidationError({"is_enabled": "مقدار باید true یا false باشد."})

    # Refusing to switch off the last one is the point: an empty picker leaves
    # customers with a cart they cannot pay for, and nothing on the page says
    # why.
    if not value:
        still_live = [
            g
            for g in settings.PAYMENT_GATEWAYS
            if g != name and _describe(g)["is_live"]
        ]
        if not still_live:
            raise ValidationError(
                {
                    "is_enabled": (
                        "این تنها درگاه فعال است و نمی‌توان خاموشش کرد؛ "
                        "بدون آن هیچ سفارشی قابل پرداخت نخواهد بود."
                    )
                }
            )

    GatewayToggle.objects.update_or_create(
        name=name,
        defaults={
            "is_enabled": value,
            "note": (request.data.get("note") or "")[:200],
        },
    )

    return Response(_describe(name), status=status.HTTP_200_OK)
