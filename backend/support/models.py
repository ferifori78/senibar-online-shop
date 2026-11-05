from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _


class TicketQuerySet(models.QuerySet):
    def open(self):
        return self.exclude(status=Ticket.Status.CLOSED)

    def needing_reply(self):
        """Tickets where the customer spoke last — the support inbox's job list."""
        return self.filter(status=Ticket.Status.OPEN)

    def for_user(self, user):
        return self.filter(user=user)


class Ticket(models.Model):
    """A support conversation.

    Status is derived from who spoke last rather than set by hand:
      OPEN    — the customer is waiting on us
      PENDING — we replied; the ball is with the customer
      CLOSED  — resolved
    Support staff can still close or reopen explicitly.
    """

    class Status(models.TextChoices):
        OPEN = "open", _("Open")
        PENDING = "pending", _("Awaiting customer")
        CLOSED = "closed", _("Closed")

    class Priority(models.TextChoices):
        LOW = "low", _("Low")
        NORMAL = "normal", _("Normal")
        HIGH = "high", _("High")
        URGENT = "urgent", _("Urgent")

    class Topic(models.TextChoices):
        ORDER = "order", _("About an order")
        SHIPPING = "shipping", _("Shipping")
        PAYMENT = "payment", _("Payment")
        PRODUCT = "product", _("Coffee and brewing")
        OTHER = "other", _("Other")

    reference = models.CharField(
        _("reference"), max_length=20, unique=True, editable=False,
        help_text=_("Human-readable ticket id, e.g. TK-260830-4F2A."),
    )
    user = models.ForeignKey(
        "accounts.CustomUser", on_delete=models.CASCADE, related_name="tickets",
        verbose_name=_("customer"),
    )
    subject = models.CharField(_("subject"), max_length=160)
    topic = models.CharField(
        _("topic"), max_length=16, choices=Topic.choices, default=Topic.OTHER
    )
    status = models.CharField(
        _("status"), max_length=16, choices=Status.choices, default=Status.OPEN,
        db_index=True,
    )
    priority = models.CharField(
        _("priority"), max_length=16, choices=Priority.choices, default=Priority.NORMAL
    )

    # Optional link to the order being discussed, so support has context.
    order = models.ForeignKey(
        "orders.Order", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="tickets", verbose_name=_("related order"),
    )

    assigned_to = models.ForeignKey(
        "accounts.CustomUser", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="assigned_tickets", verbose_name=_("assigned to"),
    )

    # Unread counters, kept in step by TicketMessage.save().
    unread_for_staff = models.PositiveSmallIntegerField(default=0)
    unread_for_customer = models.PositiveSmallIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_message_at = models.DateTimeField(_("last message at"), null=True, blank=True)
    closed_at = models.DateTimeField(_("closed at"), null=True, blank=True)

    objects = TicketQuerySet.as_manager()

    class Meta:
        verbose_name = _("ticket")
        verbose_name_plural = _("tickets")
        ordering = ("-last_message_at", "-created_at")
        indexes = [
            models.Index(fields=["status", "-last_message_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.reference} — {self.subject}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self._generate_reference()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_reference():
        stamp = timezone.localdate().strftime("%y%m%d")
        for _attempt in range(10):
            candidate = f"TK-{stamp}-{get_random_string(4, '0123456789ABCDEFGHJKMNPQRSTVWXYZ')}"
            if not Ticket.objects.filter(reference=candidate).exists():
                return candidate
        raise RuntimeError("Could not allocate a unique ticket reference.")

    @property
    def is_closed(self):
        return self.status == self.Status.CLOSED

    @property
    def message_count(self):
        return self.messages.count()

    def close(self, *, actor=None):
        self.status = self.Status.CLOSED
        self.closed_at = timezone.now()
        self.save(update_fields=["status", "closed_at", "updated_at"])
        return self

    def reopen(self, *, actor=None):
        self.status = self.Status.OPEN
        self.closed_at = None
        self.save(update_fields=["status", "closed_at", "updated_at"])
        return self

    def mark_read_by(self, user):
        """Clear the reader's own unread counter, never the other side's."""
        field = "unread_for_staff" if user.is_roaster else "unread_for_customer"
        if getattr(self, field):
            setattr(self, field, 0)
            self.save(update_fields=[field, "updated_at"])
        return self


class TicketMessage(models.Model):
    """One message in a ticket. Append-only — support conversations are a record."""

    class Author(models.TextChoices):
        CUSTOMER = "customer", _("Customer")
        STAFF = "staff", _("Support")
        SYSTEM = "system", _("System")

    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="messages", verbose_name=_("ticket")
    )
    author = models.ForeignKey(
        "accounts.CustomUser", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="ticket_messages", verbose_name=_("author"),
        help_text=_("Null for system notes."),
    )
    author_role = models.CharField(
        _("author role"), max_length=16, choices=Author.choices, default=Author.CUSTOMER
    )
    body = models.TextField(_("message"))

    # Staff-only notes never reach the customer.
    is_internal = models.BooleanField(
        _("internal note"), default=False,
        help_text=_("Visible to support only; excluded from the customer's view."),
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("ticket message")
        verbose_name_plural = _("ticket messages")
        ordering = ("created_at",)
        indexes = [models.Index(fields=["ticket", "created_at"])]

    def __str__(self):
        return f"{self.ticket.reference} · {self.get_author_role_display()}"

    def save(self, *args, **kwargs):
        creating = self._state.adding
        super().save(*args, **kwargs)
        if creating:
            self._touch_ticket()

    def _touch_ticket(self):
        """Advance the ticket's state to match who just spoke.

        Internal notes deliberately do none of this: they must not reopen a
        ticket or show the customer an unread badge.
        """
        if self.is_internal:
            return

        ticket = self.ticket
        fields = ["last_message_at", "updated_at"]
        ticket.last_message_at = self.created_at

        if self.author_role == self.Author.CUSTOMER:
            # A customer reply reopens a closed ticket rather than vanishing.
            ticket.status = Ticket.Status.OPEN
            ticket.closed_at = None
            ticket.unread_for_staff = models.F("unread_for_staff") + 1
            fields += ["status", "closed_at", "unread_for_staff"]
        elif self.author_role == self.Author.STAFF:
            # Replying hands the ball back, unless the ticket is already closed.
            if ticket.status != Ticket.Status.CLOSED:
                ticket.status = Ticket.Status.PENDING
                fields.append("status")
            ticket.unread_for_customer = models.F("unread_for_customer") + 1
            fields.append("unread_for_customer")

        ticket.save(update_fields=fields)
        ticket.refresh_from_db(fields=["unread_for_staff", "unread_for_customer"])
