from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("order", "gateway", "status", "amount", "ref_id", "created_at")
    list_filter = ("gateway", "status", "created_at")
    search_fields = ("order__number", "authority", "ref_id")
    readonly_fields = (
        "order", "gateway", "amount", "authority", "ref_id", "card_pan",
        "raw_response", "created_at", "paid_at",
    )
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False  # payments are created by the checkout flow only
