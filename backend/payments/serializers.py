from rest_framework import serializers

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    order_number = serializers.CharField(source="order.number", read_only=True)

    class Meta:
        model = Payment
        fields = (
            "id", "order", "order_number", "gateway", "status", "status_display",
            "amount", "gateway_fee", "authority", "ref_id", "card_pan", "failure_reason",
            "created_at", "paid_at",
        )
        read_only_fields = fields


class PaymentRequestSerializer(serializers.Serializer):
    """Start a payment for an order the caller owns."""

    order_number = serializers.CharField(max_length=20)
    callback_url = serializers.URLField(required=False)
    # Which gateway to use. Validated against the configured list in the view,
    # not here, so the error names the gateways actually on offer.
    gateway = serializers.CharField(max_length=20, required=False, allow_blank=True)


class PaymentVerifySerializer(serializers.Serializer):
    """The gateway callback, normalised across gateways.

    ZarinPal returns `?Authority=A000…&Status=OK`.
    BitPay returns `?trans_id=123&id_get=321` and has no status parameter — a
    customer who abandons the bank page simply never arrives here, so a BitPay
    callback that reaches us is always an attempt to settle.
    """

    authority = serializers.CharField(max_length=64)
    status = serializers.CharField(max_length=8, required=False, default="OK")
    # Everything else the gateway sent, passed to the driver untouched. BitPay
    # needs `trans_id` at verification time; ZarinPal needs nothing extra.
    extra = serializers.DictField(required=False, default=dict)

    def to_internal_value(self, data):
        authority = (
            data.get("authority")
            or data.get("Authority")
            # BitPay's payment handle, created by the request step.
            or data.get("id_get")
            or data.get("idGet")
        )

        trans_id = data.get("trans_id") or data.get("transId") or ""

        normalised = {
            "authority": authority,
            "status": data.get("status") or data.get("Status") or "OK",
            "extra": {"trans_id": str(trans_id)} if trans_id else {},
        }
        return super().to_internal_value(normalised)
