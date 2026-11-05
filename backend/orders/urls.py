from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .admin_views import ShippingMethodViewSet, dashboard, order_board
from .views import OrderViewSet, quote_cart, shipping_methods

router = DefaultRouter()
router.register("orders", OrderViewSet, basename="order")
router.register(
    "admin/shipping-methods", ShippingMethodViewSet, basename="admin-shipping-method"
)

urlpatterns = [
    path("cart/quote/", quote_cart, name="cart-quote"),
    path("shipping/methods/", shipping_methods, name="shipping-methods"),
    # Terminal register. Staff only.
    path("admin/dashboard/", dashboard, name="admin-dashboard"),
    path("admin/board/", order_board, name="admin-order-board"),
    path("", include(router.urls)),
]
