from rest_framework import serializers

from orders.models import Order

from .models import Ticket, TicketMessage


class TicketMessageSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    role_display = serializers.CharField(source="get_author_role_display", read_only=True)

    class Meta:
        model = TicketMessage
        fields = (
            "id", "body", "author", "author_name", "author_role", "role_display",
            "is_internal", "created_at",
        )
        read_only_fields = ("id", "author", "author_role", "created_at")

    def get_author_name(self, obj):
        """Staff appear as "پشتیبانی صنوبر", never by personal name — the
        customer is talking to the roastery, not to an individual."""
        if obj.author_role == TicketMessage.Author.STAFF:
            return "پشتیبانی صنوبر"
        if obj.author_role == TicketMessage.Author.SYSTEM:
            return "سیستم"
        return obj.author.display_name if obj.author else "—"


class TicketMessageCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=5000, trim_whitespace=True)
    is_internal = serializers.BooleanField(default=False)

    def validate_body(self, value):
        if not value.strip():
            raise serializers.ValidationError("متن پیام نمی‌تواند خالی باشد.")
        return value

    def validate_is_internal(self, value):
        # Only staff may write notes the customer cannot see.
        if value and not self.context["request"].user.is_roaster:
            raise serializers.ValidationError("یادداشت داخلی فقط برای پشتیبانی است.")
        return value


class TicketListSerializer(serializers.ModelSerializer):
    """Row payload for both inboxes."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    topic_display = serializers.CharField(source="get_topic_display", read_only=True)
    priority_display = serializers.CharField(source="get_priority_display", read_only=True)
    customer = serializers.CharField(source="user.display_name", read_only=True)
    customer_email = serializers.CharField(source="user.email", read_only=True)
    order_number = serializers.CharField(source="order.number", read_only=True, default=None)
    message_count = serializers.SerializerMethodField()
    preview = serializers.SerializerMethodField()
    unread = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = (
            "id", "reference", "subject", "topic", "topic_display",
            "status", "status_display", "priority", "priority_display",
            "customer", "customer_email", "order_number",
            "message_count", "preview", "unread",
            "created_at", "last_message_at",
        )

    def get_message_count(self, obj):
        # Counted off the prefetch; `messages.count()` would be one query per row.
        return len([m for m in obj.messages.all() if not m.is_internal])

    def get_preview(self, obj):
        """First line of the newest visible message, for the inbox row."""
        visible = [m for m in obj.messages.all() if not m.is_internal]
        if not visible:
            return ""
        body = visible[-1].body.strip().replace("\n", " ")
        return body[:110] + ("…" if len(body) > 110 else "")

    def get_unread(self, obj):
        user = self.context["request"].user
        return obj.unread_for_staff if user.is_roaster else obj.unread_for_customer


class TicketSerializer(serializers.ModelSerializer):
    """Full thread. Internal notes are filtered out for customers."""

    messages = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    topic_display = serializers.CharField(source="get_topic_display", read_only=True)
    priority_display = serializers.CharField(source="get_priority_display", read_only=True)
    customer = serializers.CharField(source="user.display_name", read_only=True)
    customer_email = serializers.CharField(source="user.email", read_only=True)
    order_number = serializers.CharField(source="order.number", read_only=True, default=None)
    is_closed = serializers.BooleanField(read_only=True)

    class Meta:
        model = Ticket
        fields = (
            "id", "reference", "subject", "topic", "topic_display",
            "status", "status_display", "priority", "priority_display",
            "customer", "customer_email", "order", "order_number",
            "assigned_to", "is_closed", "messages",
            "created_at", "last_message_at", "closed_at",
        )
        read_only_fields = (
            "id", "reference", "status", "created_at", "last_message_at", "closed_at",
        )

    def get_messages(self, obj):
        messages = obj.messages.all()
        if not self.context["request"].user.is_roaster:
            messages = [m for m in messages if not m.is_internal]
        return TicketMessageSerializer(messages, many=True).data


class TicketCreateSerializer(serializers.Serializer):
    """Open a ticket and post its first message in one call."""

    subject = serializers.CharField(max_length=160)
    topic = serializers.ChoiceField(choices=Ticket.Topic.choices, default=Ticket.Topic.OTHER)
    body = serializers.CharField(max_length=5000)
    order_number = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate_subject(self, value):
        if not value.strip():
            raise serializers.ValidationError("موضوع نمی‌تواند خالی باشد.")
        return value.strip()

    def validate_body(self, value):
        if not value.strip():
            raise serializers.ValidationError("متن پیام نمی‌تواند خالی باشد.")
        return value

    def validate_order_number(self, value):
        """An order may be attached only if the caller owns it."""
        if not value:
            return None
        user = self.context["request"].user
        try:
            return Order.objects.get(number=value, user=user)
        except Order.DoesNotExist:
            raise serializers.ValidationError("سفارشی با این شماره برای شما یافت نشد.")

    def create(self, validated_data):
        user = self.context["request"].user
        ticket = Ticket.objects.create(
            user=user,
            subject=validated_data["subject"],
            topic=validated_data["topic"],
            order=validated_data.get("order_number"),
        )
        TicketMessage.objects.create(
            ticket=ticket,
            author=user,
            author_role=TicketMessage.Author.CUSTOMER,
            body=validated_data["body"],
        )
        ticket.refresh_from_db()
        return ticket

    def to_representation(self, instance):
        return TicketSerializer(instance, context=self.context).data
