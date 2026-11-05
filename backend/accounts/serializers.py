from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from config.digits import digits_only, to_english_digits

from .models import Address

User = get_user_model()


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = (
            "id", "label", "recipient_name", "phone", "province", "city",
            "street_address", "postal_code", "is_default", "created_at",
        )
        read_only_fields = ("id", "created_at")

    # A phone number and a postal code are numbers, so Persian digits become
    # ASCII and separators are dropped. A street address is prose that happens
    # to contain a plate number, so only the digits inside it are converted.
    def validate_phone(self, value):
        return digits_only(value)

    def validate_postal_code(self, value):
        return digits_only(value)

    def validate_street_address(self, value):
        return to_english_digits(value)

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)

    def validate(self, attrs):
        """Only one default per user — demote the old one instead of tripping
        the DB constraint."""
        user = self.context["request"].user
        if attrs.get("is_default"):
            qs = Address.objects.filter(user=user, is_default=True)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            qs.update(is_default=False)
        return attrs


class UserSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    addresses = AddressSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = (
            "id", "email", "first_name", "last_name", "display_name", "phone",
            "role", "preferred_grind", "accepts_marketing", "addresses",
            "date_joined", "created_at",
        )
        read_only_fields = ("id", "email", "role", "date_joined", "created_at")

    def validate_phone(self, value):
        return digits_only(value)


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("email", "password", "password_confirm", "first_name", "last_name", "phone")

    def validate_phone(self, value):
        return digits_only(value)

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])

    def validate_current_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user
