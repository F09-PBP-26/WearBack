from django.contrib import admin

from listings.models import Listing


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ('name', 'seller', 'price', 'stock', 'created_at')
    list_filter = ('category', 'condition')
    search_fields = ('name', 'seller__username')
    readonly_fields = ('created_at', 'updated_at')
