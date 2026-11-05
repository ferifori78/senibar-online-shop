from django.contrib import admin

from .models import Ticket, TicketMessage


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 0
    readonly_fields = ("author", "author_role", "created_at")


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("reference", "subject", "user", "status", "priority", "last_message_at")
    list_filter = ("status", "priority", "topic")
    search_fields = ("reference", "subject", "user__email")
    readonly_fields = ("reference", "created_at", "last_message_at")
    inlines = (TicketMessageInline,)
    date_hierarchy = "created_at"
