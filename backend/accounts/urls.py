from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from .admin_views import AdminUserViewSet
from . import otp_views
from .views import (
    AddressViewSet,
    LoginView,
    LogoutView,
    PasswordChangeView,
    ProfileView,
    RegisterView,
)

router = DefaultRouter()
router.register("addresses", AddressViewSet, basename="address")
router.register("admin/users", AdminUserViewSet, basename="admin-user")

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),
    # Login or registration by one-time code, alongside the password flow.
    path("auth/otp/request/", otp_views.request_code, name="otp-request"),
    path("auth/otp/verify/", otp_views.verify_code, name="otp-verify"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/verify/", TokenVerifyView.as_view(), name="token-verify"),
    path("auth/password/", PasswordChangeView.as_view(), name="password-change"),
    path("me/", ProfileView.as_view(), name="profile"),
    path("", include(router.urls)),
]
