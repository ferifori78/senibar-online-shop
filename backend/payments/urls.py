from django.urls import path

from .admin_views import gateway_admin_list, gateway_set_enabled
from .views import (
    PaymentRequestView,
    PaymentVerifyView,
    gateway_options,
    mock_pay,
    payment_status,
)

urlpatterns = [
    path("payments/gateways/", gateway_options, name="payment-gateways"),
    # Staff-only: the switchboard behind the customer-facing list above.
    path("admin/gateways/", gateway_admin_list, name="admin-gateways"),
    path(
        "admin/gateways/<slug:name>/enabled/",
        gateway_set_enabled,
        name="admin-gateway-enabled",
    ),
    path("payments/request/", PaymentRequestView.as_view(), name="payment-request"),
    path("payments/verify/", PaymentVerifyView.as_view(), name="payment-verify"),
    path("payments/status/<str:order_number>/", payment_status, name="payment-status"),
    # Mock gateway's hosted pay page. Inert unless PAYMENT_GATEWAY=mock.
    path("payments/mock/<str:authority>/", mock_pay, name="payment-mock-pay"),
]
