from django.db.models import Count, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from orders.admin_views import IsRoaster

from .models import Ticket, TicketMessage
from .serializers import (
    TicketCreateSerializer,
    TicketListSerializer,
    TicketMessageCreateSerializer,
    TicketMessageSerializer,
    TicketSerializer,
)


class TicketViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Support tickets. Customers see their own; staff see every ticket.

    Never deletable — a support conversation is a record, and closing is the
    way a ticket ends.
    """

    permission_classes = (IsAuthenticated,)
    lookup_field = "reference"
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filterset_fields = ("status", "topic", "priority")
    search_fields = ("reference", "subject", "messages__body", "user__email")
    ordering_fields = ("created_at", "last_message_at", "priority")
    ordering = ("-last_message_at", "-created_at")

    def get_queryset(self):
        user = self.request.user
        qs = Ticket.objects.select_related("user", "order", "assigned_to").prefetch_related(
            "messages__author"
        )
        if not user.is_roaster:
            qs = qs.filter(user=user)

        state = self.request.query_params.get("state")
        if state == "open":
            qs = qs.open()
        elif state == "closed":
            qs = qs.filter(status=Ticket.Status.CLOSED)
        elif state == "needs_reply":
            qs = qs.needing_reply()

        return qs.distinct()

    def get_serializer_class(self):
        if self.action == "create":
            return TicketCreateSerializer
        if self.action == "list":
            return TicketListSerializer
        return TicketSerializer

    def retrieve(self, request, *args, **kwargs):
        """Opening a thread clears the reader's own unread badge."""
        ticket = self.get_object()
        ticket.mark_read_by(request.user)
        return Response(self.get_serializer(ticket).data)

    @staticmethod
    def _queue(task_name, *args, module="tasks"):
        """Dispatch after commit, and never let a dead broker fail the request.

        `module` picks between `notifications.tasks` (what the customer is
        told) and `notifications.feed` (the shop's own Telegram channel).

        `delay()` raises when the broker is unreachable, and inside on_commit
        that exception leaves the request — which would turn a saved reply or a
        closed ticket into a 500 even though the work is already done. Telling
        the customer is secondary to the change itself.
        """
        from django.db import transaction

        def dispatch():
            try:
                import importlib

                mod = importlib.import_module(f"notifications.{module}")
                getattr(mod, task_name).delay(*args)
            except Exception:
                import logging

                logging.getLogger("senobar.support").exception(
                    "Could not queue %s.%s%s", module, task_name, args
                )

        transaction.on_commit(dispatch)

    def perform_create(self, serializer):
        """Announce a new ticket on the shop's channel."""
        ticket = serializer.save()
        self._queue("ticket_opened", ticket.pk, module="feed")
        return ticket

    def _fresh(self, ticket):
        """Re-read before serialising: posting a message changes status and
        adds a row that the prefetched cache would otherwise hide."""
        ticket = self.get_queryset().get(pk=ticket.pk)
        return TicketSerializer(ticket, context=self.get_serializer_context()).data

    @action(detail=True, methods=["post"])
    def reply(self, request, reference=None):
        """Post a message. Role is taken from the caller, never from the body."""
        ticket = self.get_object()
        serializer = TicketMessageCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        # A customer replying to a closed ticket reopens it; a staff reply to a
        # closed one leaves it closed. Both are handled in _touch_ticket().
        is_staff = request.user.is_roaster

        message = TicketMessage.objects.create(
            ticket=ticket,
            author=request.user,
            author_role=(
                TicketMessage.Author.STAFF if is_staff else TicketMessage.Author.CUSTOMER
            ),
            body=serializer.validated_data["body"],
            is_internal=serializer.validated_data.get("is_internal", False),
        )

        # Only a staff reply is worth an email; the customer's own message is
        # not news to them, and internal notes never leave the building.
        if is_staff and not message.is_internal:
            self._queue("ticket_replied", ticket.pk, message.pk)
        elif not is_staff:
            # The other direction: a customer answering is what support needs
            # to see, and the shop's channel is where they are watching.
            self._queue("customer_replied", ticket.pk, message.pk, module="feed")

        return Response(
            {
                "message": TicketMessageSerializer(message).data,
                "ticket": self._fresh(ticket),
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def close(self, request, reference=None):
        ticket = self.get_object()
        if ticket.is_closed:
            return Response(
                {"detail": "این تیکت از قبل بسته است."}, status=status.HTTP_409_CONFLICT
            )

        ticket.close(actor=request.user)
        self._queue(
            "ticket_status_changed",
            ticket.pk,
            Ticket.Status.CLOSED.value,
            request.user.pk,
            ticket.closed_at.isoformat() if ticket.closed_at else None,
        )
        self._queue(
            "ticket_status_changed",
            ticket.pk,
            Ticket.Status.CLOSED.value,
            request.user.display_name,
            ticket.closed_at.isoformat() if ticket.closed_at else "",
            module="feed",
        )
        if note := request.data.get("note"):
            TicketMessage.objects.create(
                ticket=ticket,
                author=request.user,
                author_role=(
                    TicketMessage.Author.STAFF
                    if request.user.is_roaster
                    else TicketMessage.Author.CUSTOMER
                ),
                body=note,
                is_internal=True,
            )
        return Response(self._fresh(ticket))

    @action(detail=True, methods=["post"])
    def reopen(self, request, reference=None):
        ticket = self.get_object()
        if not ticket.is_closed:
            return Response(
                {"detail": "این تیکت باز است."}, status=status.HTTP_409_CONFLICT
            )
        ticket.reopen(actor=request.user)
        # `reopen` clears closed_at, so the moment has to come from the clock.
        # Reopening is stamped, not keyed on status alone, because a ticket may
        # go round the close/reopen loop more than once.
        self._queue(
            "ticket_status_changed",
            ticket.pk,
            Ticket.Status.OPEN.value,
            request.user.pk,
            timezone.now().isoformat(),
        )
        self._queue(
            "ticket_status_changed",
            ticket.pk,
            Ticket.Status.OPEN.value,
            request.user.display_name,
            timezone.now().isoformat(),
            module="feed",
        )
        return Response(self._fresh(ticket))

    @action(detail=True, methods=["post"], permission_classes=(IsRoaster,))
    def assign(self, request, reference=None):
        """Take a ticket, or hand it to someone else."""
        ticket = self.get_object()
        ticket.assigned_to = request.user
        ticket.priority = request.data.get("priority", ticket.priority)
        ticket.save(update_fields=["assigned_to", "priority", "updated_at"])
        # Stamped with the moment, so a ticket handed back and forth between
        # staff announces each move rather than only the first.
        self._queue(
            "ticket_status_changed",
            ticket.pk,
            ticket.status,
            request.user.display_name,
            timezone.now().isoformat(),
            module="feed",
        )
        return Response(self._fresh(ticket))


@api_view(["GET"])
@permission_classes((IsRoaster,))
def inbox_summary(request):
    """Counts for the Terminal inbox's filter tabs."""
    counts = Ticket.objects.aggregate(
        open=Count("id", filter=Q(status=Ticket.Status.OPEN)),
        pending=Count("id", filter=Q(status=Ticket.Status.PENDING)),
        closed=Count("id", filter=Q(status=Ticket.Status.CLOSED)),
        urgent=Count(
            "id",
            filter=Q(priority=Ticket.Priority.URGENT).__and__(
                ~Q(status=Ticket.Status.CLOSED)
            ),
        ),
    )
    counts["total"] = sum(counts[k] for k in ("open", "pending", "closed"))
    counts["unread"] = (
        Ticket.objects.filter(unread_for_staff__gt=0).exclude(
            status=Ticket.Status.CLOSED
        ).count()
    )
    return Response(counts)
