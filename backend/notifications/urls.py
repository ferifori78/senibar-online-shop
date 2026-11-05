from django.urls import path

from .views import record_visit

urlpatterns = [
    path("visits/", record_visit, name="record-visit"),
]
