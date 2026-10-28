from django.contrib import admin

from listings.models import Listing


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ('name', 'seller', 'created_at')
    readonly_fields = ('created_at', 'updated_at')
