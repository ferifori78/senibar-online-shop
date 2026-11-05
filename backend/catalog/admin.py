from django.contrib import admin

from .models import CoffeeProduct, RoastBatch


@admin.register(CoffeeProduct)
class CoffeeProductAdmin(admin.ModelAdmin):
    list_display = ("name", "origin_country", "process", "roast_level", "price_per_250g", "status")
    list_filter = ("status", "origin_country", "process", "roast_level")
    search_fields = ("name", "origin_country", "farm", "producer")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(RoastBatch)
class RoastBatchAdmin(admin.ModelAdmin):
    list_display = ("batch_code", "product", "roast_date", "remaining_grams", "reserved_grams", "status")
    list_filter = ("status", "roast_date")
    search_fields = ("batch_code", "product__name")
    date_hierarchy = "roast_date"
    autocomplete_fields = ("product",)
