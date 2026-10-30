import csv
from datetime import timedelta

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone

from listings.imports import CSV_FIELDS, REQUIRED_COLUMNS, ListingCSVImportForm, validate_listing_rows
from listings.models import Listing, ListingImportBatch


PREVIEW_LIFETIME = timedelta(minutes=30)


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    change_list_template = 'admin/listings/listing/change_list.html'
    list_display = ('name', 'seller', 'price', 'stock', 'created_at')
    list_filter = ('category', 'condition')
    search_fields = ('name', 'seller__username')
    readonly_fields = ('created_at', 'updated_at')

    def get_urls(self):
        return [
            path('import-csv/', self.admin_site.admin_view(self.import_csv), name='listings_listing_import_csv'),
            path('import-csv/template/', self.admin_site.admin_view(self.csv_template),
                 name='listings_listing_csv_template'),
            path('import-csv/<uuid:batch_id>/', self.admin_site.admin_view(self.import_preview),
                 name='listings_listing_import_preview'),
        ] + super().get_urls()

    def import_context(self, request, **extra):
        return {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'media': self.media,
            'required_columns': REQUIRED_COLUMNS,
            'categories': Listing.Category.choices,
            'conditions': Listing.Condition.choices,
            **extra,
        }

    def import_csv(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied
        if request.method not in ('GET', 'POST'):
            return HttpResponseNotAllowed(['GET', 'POST'])
        form = ListingCSVImportForm(
            request.POST if request.method == 'POST' else None,
            request.FILES if request.method == 'POST' else None,
            initial={'default_seller': request.user.pk},
        )
        if request.method == 'POST' and form.is_valid():
            ListingImportBatch.objects.filter(
                created_by=request.user, completed_at__isnull=True,
                created_at__lt=timezone.now() - PREVIEW_LIFETIME,
            ).delete()
            batch = ListingImportBatch.objects.create(created_by=request.user, rows=form.rows)
            return redirect('admin:listings_listing_import_preview', batch_id=batch.pk)
        return TemplateResponse(request, 'admin/listings/listing/import_form.html', self.import_context(
            request, title='Import listings from CSV', form=form, row_errors=form.row_errors,
        ))

    def csv_template(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied
        if request.method != 'GET':
            return HttpResponseNotAllowed(['GET'])
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="wearback-listings-template.csv"'
        response.write('\ufeff')
        writer = csv.DictWriter(response, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerow({
            'name': 'Example cotton shirt', 'price': '75000', 'category': Listing.Category.TOPS,
            'size': 'Medium', 'condition': Listing.Condition.GOOD, 'stock': 1,
            'description': 'Replace this example with your item details.',
        })
        return response

    def import_preview(self, request, batch_id):
        if not self.has_add_permission(request):
            raise PermissionDenied
        if request.method not in ('GET', 'POST'):
            return HttpResponseNotAllowed(['GET', 'POST'])
        imported_count = None
        try:
            with transaction.atomic():
                # Lock the preview on confirmation so simultaneous submits cannot create duplicates on PWS/PostgreSQL.
                batches = ListingImportBatch.objects.all()
                if request.method == 'POST':
                    batches = batches.select_for_update()
                batch = get_object_or_404(batches, pk=batch_id, created_by=request.user)
                if batch.completed_at:
                    self.message_user(request, 'This preview was already imported. No new items were added.', messages.WARNING)
                    return redirect('admin:listings_listing_changelist')
                if batch.created_at < timezone.now() - PREVIEW_LIFETIME:
                    self.message_user(request, 'This preview expired. Upload the CSV again.', messages.ERROR)
                    return redirect('admin:listings_listing_import_csv')
                listings, row_errors = validate_listing_rows(batch.rows)
                if request.method == 'POST' and not row_errors:
                    Listing.objects.bulk_create(listings)
                    for listing in listings:
                        self.log_addition(request, listing, 'Added through CSV import.')
                    batch.completed_at = timezone.now()
                    batch.rows = []
                    batch.save(update_fields=['completed_at', 'rows'])
                    imported_count = len(listings)
        except IntegrityError:
            self.message_user(request, 'The import could not be saved. No items were added. Upload the CSV again.', messages.ERROR)
            return redirect('admin:listings_listing_import_csv')
        if imported_count is not None:
            self.message_user(request, f'Successfully imported {imported_count} listings.', messages.SUCCESS)
            return redirect('admin:listings_listing_changelist')
        return TemplateResponse(request, 'admin/listings/listing/import_preview.html', self.import_context(
            request, title='Review CSV import', listings=listings, batch=batch, row_errors=row_errors,
        ))
