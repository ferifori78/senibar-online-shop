from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("kind", "channel", "recipient", "status", "created_at")
    list_filter = ("kind", "channel", "status", "created_at")
    search_fields = ("recipient", "subject", "dedupe_key")
    readonly_fields = tuple(f.name for f in Notification._meta.fields)
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False  # written by tasks only
