from django.contrib.auth import get_user_model
from rest_framework import generics, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import Address
from .serializers import (
    AddressSerializer,
    PasswordChangeSerializer,
    RegisterSerializer,
    UserSerializer,
)

User = get_user_model()


def issue_tokens(user):
    """A refresh/access pair plus the user payload — what both login and
    register return, so the client has one shape to handle."""
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": UserSerializer(user).data,
    }


class RegisterView(generics.CreateAPIView):
    """Create an account and log straight in — no separate login round-trip."""

    serializer_class = RegisterSerializer
    permission_classes = (AllowAny,)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(issue_tokens(user), status=status.HTTP_201_CREATED)


class SenobarTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Bundles the user record into the login response, and puts role in the
    token so the frontend can pick its register without an extra call."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["name"] = user.display_name
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data


class LoginView(TokenObtainPairView):
    serializer_class = SenobarTokenObtainPairSerializer
    permission_classes = (AllowAny,)


class LogoutView(APIView):
    """Blacklist the refresh token. The access token stays valid until it
    expires — it is short-lived by design."""

    permission_classes = (IsAuthenticated,)

    def post(self, request):
        token = request.data.get("refresh")
        if not token:
            return Response(
                {"detail": "A refresh token is required."}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            RefreshToken(token).blacklist()
        except AttributeError:
            # Blacklist app not installed; nothing to revoke server-side.
            pass
        except Exception:
            return Response(
                {"detail": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(status=status.HTTP_205_RESET_CONTENT)


class ProfileView(generics.RetrieveUpdateAPIView):
    """The signed-in user. GET to hydrate the client, PATCH to edit."""

    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        return self.request.user


class PasswordChangeView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        # The old password is gone; hand back a fresh pair so the session survives.
        return Response(issue_tokens(user))


class AddressViewSet(viewsets.ModelViewSet):
    """A user's saved addresses. Scoped to the owner — never listable across users."""

    serializer_class = AddressSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)
