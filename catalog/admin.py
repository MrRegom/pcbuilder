from django.contrib import admin

from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "component_type", "brand", "price_low", "in_stock", "extraction_method"]
    list_filter = ["component_type", "brand", "in_stock", "extraction_method"]
    search_fields = ["name", "description"]
