from django.contrib import admin

from .models import Order, OrderItem, OrderStatusHistory, ShippingMethod


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("unit_price", "product_name", "stock_committed")


class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ("from_status", "to_status", "actor", "note", "created_at")
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("number", "user", "status", "payment_status", "total_amount", "placed_at")
    list_filter = ("status", "payment_status", "placed_at")
    search_fields = ("number", "user__email", "recipient_name", "tracking_code")
    readonly_fields = ("number", "placed_at", "total_amount")
    inlines = (OrderItemInline, OrderStatusHistoryInline)
    date_hierarchy = "placed_at"


@admin.register(ShippingMethod)
class ShippingMethodAdmin(admin.ModelAdmin):
    list_display = ("key", "label", "cost", "free_over", "is_active", "sort_order")
    list_filter = ("is_active",)
    list_editable = ("cost", "free_over", "is_active", "sort_order")
    search_fields = ("key", "label")
