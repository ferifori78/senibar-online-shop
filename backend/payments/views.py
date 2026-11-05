from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Order

from .gateways import GatewayError, available_gateways, get_gateway
from .models import Payment
from .serializers import PaymentRequestSerializer, PaymentSerializer, PaymentVerifySerializer


class PaymentRequestView(APIView):
    """Open a transaction with the gateway and hand back a redirect URL."""

    permission_classes = (IsAuthenticated,)

    def post(self, request):
        serializer = PaymentRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = get_object_or_404(
            Order, number=serializer.validated_data["order_number"], user=request.user
        )

        if order.payment_status == Order.PaymentStatus.PAID:
            return Response(
                {"detail": "This order is already paid."}, status=status.HTTP_409_CONFLICT
            )
        if order.status in Order.TERMINAL_STATUSES:
            return Response(
                {"detail": "This order can no longer be paid."},
                status=status.HTTP_409_CONFLICT,
            )

        # Recompute rather than trust the stored figure — line items or shipping
        # may have shifted since the order was created.
        amount = order.recalculate_total()
        if amount <= 0:
            return Response(
                {"detail": "Order total is zero; nothing to pay."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # The customer picks the gateway, but only from the configured list —
        # otherwise a crafted request could name a driver the shop has not
        # enabled, or "mock" in production and settle an order for free.
        requested = (serializer.validated_data.get("gateway") or "").strip()
        offered = available_gateways()

        if requested and requested not in {g["name"] for g in offered}:
            # Name the gateways by their Persian labels: this message is shown
            # to a customer, who has no idea what "bitpay" is.
            names = "، ".join(g["label"] for g in offered) or "هیچ درگاهی"
            return Response(
                {"gateway": f"این درگاه در دسترس نیست. درگاه‌های فعال: {names}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            gateway = get_gateway(requested or None)
        except GatewayError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        callback_url = serializer.validated_data.get("callback_url") or settings.PAYMENT_CALLBACK_URL

        payment = Payment.objects.create(
            order=order,
            gateway=gateway.name,
            amount=amount,
            description=f"Senobar order {order.number}",
            status=Payment.Status.INITIATED,
        )

        try:
            result = gateway.request(
                amount=amount,
                description=payment.description,
                callback_url=callback_url,
                mobile=order.recipient_phone,
                email=request.user.email,
            )
        except GatewayError as exc:
            payment.mark_failed(exc)
            return Response(
                {"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY
            )

        payment.authority = result.authority
        payment.status = Payment.Status.PENDING
        payment.raw_response = result.raw
        payment.save(update_fields=["authority", "status", "raw_response", "updated_at"])

        return Response(
            {
                "authority": result.authority,
                "redirect_url": result.redirect_url,
                "amount": amount,
                "payment": PaymentSerializer(payment).data,
            },
            status=status.HTTP_201_CREATED,
        )


class PaymentVerifyView(APIView):
    """Settle a transaction after the gateway sends the customer back.

    Deliberately open to unauthenticated calls: the gateway redirects the
    browser here and the session cookie may not survive the round trip. The
    authority is the credential — it is unguessable and single-use.
    """

    permission_classes = (AllowAny,)

    def post(self, request):
        return self._handle(request.data)

    def get(self, request):
        # ZarinPal returns the customer by GET with query parameters.
        return self._handle(request.query_params)

    def _handle(self, data):
        serializer = PaymentVerifySerializer(data=data)
        serializer.is_valid(raise_exception=True)

        authority = serializer.validated_data["authority"]
        gateway_status = serializer.validated_data["status"].upper()
        extra = serializer.validated_data.get("extra") or {}

        payment = get_object_or_404(Payment, authority=authority)

        # Already settled: report the same result rather than charging again.
        if payment.status == Payment.Status.PAID:
            return Response(
                {
                    "status": "paid",
                    "already_verified": True,
                    "order": payment.order.number,
                    "ref_id": payment.ref_id,
                    "payment": PaymentSerializer(payment).data,
                }
            )

        # The customer cancelled at the gateway.
        if gateway_status != "OK":
            payment.mark_failed(
                "Cancelled at the gateway.", status=Payment.Status.CANCELLED
            )
            return Response(
                {
                    "status": "cancelled",
                    "order": payment.order.number,
                    "detail": "پرداخت لغو شد.",
                },
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        gateway = get_gateway(payment.gateway)
        try:
            result = gateway.verify(
                authority=authority, amount=payment.amount, extra=extra
            )
        except GatewayError as exc:
            payment.mark_failed(exc)
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        if not result.success:
            payment.mark_failed(result.message, raw=result.raw)
            return Response(
                {
                    "status": "failed",
                    "order": payment.order.number,
                    "detail": result.message or "تأیید پرداخت ناموفق بود.",
                },
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        with transaction.atomic():
            # Lock the row so two concurrent callbacks can't both settle it.
            locked = Payment.objects.select_for_update().get(pk=payment.pk)
            if locked.status == Payment.Status.PAID:
                payment = locked
            else:
                payment = locked.mark_paid(
                    ref_id=result.ref_id,
                    card_pan=result.card_pan,
                    fee=result.fee,
                    raw=result.raw,
                )
                order = payment.order
                # mark_paid assigns a batch to each line and reserves its
                # grams. Reserving again here would double-count every order.
                order.mark_paid(reference=f"{payment.gateway}:{result.ref_id}")

        return Response(
            {
                "status": "paid",
                "already_verified": result.already_verified,
                "order": payment.order.number,
                "ref_id": payment.ref_id,
                "payment": PaymentSerializer(payment).data,
            }
        )


@api_view(["GET"])
@permission_classes((AllowAny,))
def gateway_options(request):
    """The gateways checkout may offer.

    Public: the checkout page needs this before the customer signs in, and it
    exposes nothing but names and labels.
    """
    return Response({"gateways": available_gateways(), "default": settings.PAYMENT_GATEWAY})


@api_view(["GET"])
@permission_classes((IsAuthenticated,))
def payment_status(request, order_number):
    """Latest payment attempt for one of the caller's orders."""
    order = get_object_or_404(Order, number=order_number, user=request.user)
    payment = order.payments.first()
    if payment is None:
        return Response({"detail": "No payment has been started for this order."}, status=404)
    return Response(PaymentSerializer(payment).data)


@api_view(["POST"])
@permission_classes((AllowAny,))
def mock_pay(request, authority):
    """Stands in for the gateway's hosted pay page.

    Only reachable while the mock gateway is active, so it can never settle a
    real transaction. Post `{"outcome": "fail"}` to simulate a decline.
    """
    if settings.PAYMENT_GATEWAY != "mock":
        return Response(
            {"detail": "The mock pay page is disabled."}, status=status.HTTP_404_NOT_FOUND
        )

    gateway = get_gateway("mock")
    outcome = str(request.data.get("outcome", "success")).lower()

    if outcome in ("fail", "failed", "decline"):
        gateway.fail(authority)
        return Response({"authority": authority, "status": "NOK"})

    if not gateway.settle(authority):
        return Response({"detail": "Unknown authority."}, status=status.HTTP_404_NOT_FOUND)

    return Response({"authority": authority, "status": "OK"})
