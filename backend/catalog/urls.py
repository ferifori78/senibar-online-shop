from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .admin_views import adjust_stock, adjustment_log, inventory
from .views import CoffeeProductViewSet, RoastBatchViewSet

router = DefaultRouter()
router.register("products", CoffeeProductViewSet, basename="product")
router.register("batches", RoastBatchViewSet, basename="batch")

urlpatterns = [
    # Staff-only inventory, before the router so the router's catch-alls
    # cannot shadow them.
    path("admin/inventory/", inventory, name="admin-inventory"),
    path("admin/inventory/log/", adjustment_log, name="admin-adjustment-log"),
    path("admin/batches/<int:pk>/adjust/", adjust_stock, name="admin-adjust-stock"),
    path("", include(router.urls)),
]
