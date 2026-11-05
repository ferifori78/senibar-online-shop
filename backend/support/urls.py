from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import TicketViewSet, inbox_summary

router = DefaultRouter()
router.register("tickets", TicketViewSet, basename="ticket")

urlpatterns = [
    path("support/inbox-summary/", inbox_summary, name="ticket-inbox-summary"),
    path("", include(router.urls)),
]
