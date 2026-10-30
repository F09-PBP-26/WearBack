import csv
import io
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from listings.imports import CSV_FIELDS, MAX_IMPORT_ROWS, MAX_UPLOAD_BYTES, ListingCSVImportForm
from listings.models import Listing, ListingImportBatch


User = get_user_model()


class ListingAdminImportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(username='import-admin', email='admin@example.com', password='TestImport!8491')
        cls.other_admin = User.objects.create_superuser(username='other-admin', email='other@example.com', password='TestImport!8491')
        cls.seller = User.objects.create_user(username='seller-one')
        cls.other_seller = User.objects.create_user(username='seller-two')
        cls.staff = User.objects.create_user(username='staff', is_staff=True)
        cls.upload_url = reverse('admin:listings_listing_import_csv')
        cls.template_url = reverse('admin:listings_listing_csv_template')
        cls.list_url = reverse('admin:listings_listing_changelist')

    def setUp(self):
        self.client.force_login(self.admin)

    def item(self, **changes):
        return {
            'name': 'Cotton shirt', 'price': '75.000,50', 'category': 'tops',
            'size': 'Medium', 'condition': 'good', **changes,
        }

    def csv_upload(self, rows=None, headers=CSV_FIELDS, name='items.csv', bom=False):
        stream = io.StringIO(newline='')
        writer = csv.DictWriter(stream, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows if rows is not None else [self.item()])
        content = ('\ufeff' if bom else '') + stream.getvalue()
        return SimpleUploadedFile(name, content.encode('utf-8'), content_type='text/csv')

    def upload(self, rows=None, client=None, **extra):
        return (client or self.client).post(self.upload_url, {
            'csv_file': self.csv_upload(rows), 'default_seller': self.seller.pk, **extra,
        })

    def preview(self, rows=None):
        response = self.upload(rows)
        self.assertEqual(response.status_code, 302)
        return response.url

    def test_admin_pages_offer_import_and_downloadable_working_template(self):
        self.assertContains(self.client.get(self.list_url), f'href="{self.upload_url}"')
        page = self.client.get(self.upload_url)
        self.assertContains(page, 'Preview items')
        self.assertContains(page, 'multipart/form-data')
        self.assertEqual(page.context['form']['default_seller'].value(), self.admin.pk)
        template = self.client.get(self.template_url)
        self.assertEqual(template['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn('attachment', template['Content-Disposition'])
        upload = SimpleUploadedFile('template.csv', template.content, content_type='text/csv')
        form = ListingCSVImportForm({'default_seller': self.seller.pk}, {'csv_file': upload})
        self.assertTrue(form.is_valid(), form.errors)

    def test_preview_then_confirmation_creates_all_fields_and_admin_history_once(self):
        rows = [
            self.item(name='Shirt, blue', description='First line\nSecond line', image_url='https://example.com/shirt.jpg',
                      brand='WearBack', material='Cotton', style='Casual', location='Depok', contact_email='seller@example.com'),
            self.item(name='Other shirt', seller=self.other_seller.username, price='120000', stock='0'),
        ]
        url = self.preview(rows)
        self.assertEqual(Listing.objects.count(), 0)
        page = self.client.get(url)
        self.assertContains(page, '2 items ready to import.')
        self.assertContains(page, 'Shirt, blue')
        self.assertContains(page, self.other_seller.username)
        self.assertEqual(Listing.objects.count(), 0)
        result = self.client.post(url, {'seller': self.admin.pk, 'name': 'Forged hidden value'}, follow=True)
        self.assertContains(result, 'Successfully imported 2 listings.')
        self.assertEqual(Listing.objects.count(), 2)
        shirt = Listing.objects.get(name='Shirt, blue')
        self.assertEqual(shirt.seller, self.seller)
        self.assertEqual(shirt.price, Decimal('75000.50'))
        self.assertEqual(shirt.stock, 1)
        for field in ('description', 'image_url', 'brand', 'material', 'style', 'location', 'contact_email'):
            self.assertEqual(getattr(shirt, field), rows[0][field])
        other = Listing.objects.get(name='Other shirt')
        self.assertEqual(other.seller, self.other_seller)
        self.assertEqual(other.stock, 0)
        self.assertFalse(other.is_available)
        logs = LogEntry.objects.filter(user=self.admin, action_flag=ADDITION)
        self.assertEqual(set(logs.values_list('object_id', flat=True)), {str(shirt.pk), str(other.pk)})
        batch = ListingImportBatch.objects.get()
        self.assertIsNotNone(batch.completed_at)
        self.assertEqual(batch.rows, [])
        self.assertContains(self.client.post(url, follow=True), 'already imported')
        self.assertEqual(self.client.get(url).status_code, 302)
        self.assertEqual(Listing.objects.count(), 2)
        self.assertEqual(logs.count(), 2)

    def test_each_new_upload_creates_new_listings_instead_of_updating_existing_items(self):
        existing = Listing.objects.create(seller=self.seller, name='Cotton shirt', price=100)
        self.client.post(self.preview())
        self.client.post(self.preview())
        existing.refresh_from_db()
        self.assertEqual(existing.price, Decimal('100'))
        self.assertEqual(Listing.objects.filter(name='Cotton shirt').count(), 3)

    def test_sellers_can_come_entirely_from_csv(self):
        response = self.upload([self.item(seller=self.other_seller.username)], default_seller='')
        self.assertEqual(response.status_code, 302)
        self.client.post(response.url)
        self.assertEqual(Listing.objects.get().seller, self.other_seller)

    def test_minimal_columns_utf8_bom_and_blank_lines_are_supported(self):
        headers = ('name', 'price', 'category', 'size', 'condition')
        upload = self.csv_upload([self.item(name='Kemeja café')], headers=headers, bom=True)
        response = self.client.post(self.upload_url, {'csv_file': upload, 'default_seller': self.seller.pk})
        self.assertEqual(response.status_code, 302)
        self.client.post(response.url)
        item = Listing.objects.get()
        self.assertEqual(item.name, 'Kemeja café')
        self.assertEqual(item.stock, 1)
        self.assertEqual(item.image_url, '')
        content = '\r\nname,price,category,size,condition\r\n\r\nShirt,50000,tops,M,good\r\n,,,,\r\n'
        response = self.client.post(self.upload_url, {
            'csv_file': SimpleUploadedFile('blank-lines.csv', content.encode()), 'default_seller': self.seller.pk,
        })
        self.assertEqual(response.status_code, 302)

    def test_invalid_item_fields_report_csv_line_and_prevent_the_entire_upload(self):
        invalid_values = {
            'name': ['', 'x' * 201], 'price': ['', '0', '-1', 'NaN', 'Infinity', '10000000000', '1.0011'],
            'category': ['', 'unknown'], 'size': ['', 'x' * 33], 'condition': ['', 'bad'],
            'stock': ['-1', '10000', '1.5'], 'image_url': ['http://example.com/a.jpg', 'not-a-url'],
            'contact_email': ['not-an-email'], 'seller': ['missing-user'],
        }
        for field, values in invalid_values.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    response = self.upload([self.item(), self.item(**{field: value})])
                    self.assertEqual(response.status_code, 200)
                    self.assertContains(response, 'CSV errors')
                    self.assertEqual(response.context['row_errors'][0]['line'], 3)
                    self.assertFalse(Listing.objects.exists())
                    self.assertFalse(ListingImportBatch.objects.exists())

    def test_missing_or_inactive_sellers_are_rejected(self):
        self.other_seller.is_active = False
        self.other_seller.save()
        for row, default in ((self.item(), ''), (self.item(seller=self.other_seller.username), self.seller.pk)):
            with self.subTest(row=row):
                response = self.upload([row], default_seller=default)
                self.assertContains(response, 'existing active seller username')
                self.assertFalse(ListingImportBatch.objects.exists())
        response = self.upload(default_seller=self.other_seller.pk)
        self.assertIn('default_seller', response.context['form'].errors)

    def test_invalid_csv_structure_encoding_and_file_type_are_rejected(self):
        files = [
            ('empty.csv', b''),
            ('headers.csv', b'name,price,category,size,condition\n'),
            ('missing.csv', b'name,price\nShirt,75000\n'),
            ('duplicate.csv', b'name,name,price,category,size,condition\n'),
            ('protected.csv', b'name,price,category,size,condition,seller_id\n'),
            ('extra.csv', b'name,price,category,size,condition\nShirt,75000,tops,M,good,extra\n'),
            ('short.csv', b'name,price,category,size,condition\nShirt,75000\n'),
            ('quotes.csv', b'name,price,category,size,condition\n"Unclosed,75000,tops,M,good\n'),
            ('invalid.csv', b'\xff\xfeinvalid'),
            ('null.csv', b'name,price,category,size,condition\nShirt\x00,75000,tops,M,good\n'),
            ('items.xlsx', b'not a CSV'),
            ('huge.csv', b'x' * (MAX_UPLOAD_BYTES + 1)),
        ]
        for name, content in files:
            with self.subTest(name=name):
                response = self.client.post(self.upload_url, {
                    'csv_file': SimpleUploadedFile(name, content), 'default_seller': self.seller.pk,
                })
                self.assertEqual(response.status_code, 200)
                self.assertIn('csv_file', response.context['form'].errors)
                self.assertFalse(ListingImportBatch.objects.exists())
                self.assertFalse(Listing.objects.exists())

    def test_more_than_500_items_are_rejected_before_creating_a_preview(self):
        response = self.upload([self.item()] * (MAX_IMPORT_ROWS + 1))
        self.assertContains(response, 'Import at most 500 items')
        self.assertFalse(ListingImportBatch.objects.exists())

    def test_500_items_can_be_confirmed_together(self):
        url = self.preview([self.item(name=f'Bulk shirt {index}') for index in range(MAX_IMPORT_ROWS)])
        self.assertFalse(Listing.objects.exists())
        response = self.client.post(url, follow=True)
        self.assertContains(response, 'Successfully imported 500 listings.')
        self.assertEqual(Listing.objects.count(), MAX_IMPORT_ROWS)
        self.assertEqual(LogEntry.objects.filter(user=self.admin, action_flag=ADDITION).count(), MAX_IMPORT_ROWS)

    def test_seller_changes_after_preview_prevent_all_items_from_being_added(self):
        for change in ('deactivate', 'delete', 'rename'):
            with self.subTest(change=change):
                seller = User.objects.create_user(username=f'changing-{change}')
                url = self.preview([self.item(), self.item(seller=seller.username)])
                if change == 'delete':
                    seller.delete()
                elif change == 'deactivate':
                    seller.is_active = False
                    seller.save()
                else:
                    seller.username = 'renamed-seller'
                    seller.save()
                response = self.client.post(url)
                self.assertContains(response, 'no longer valid')
                self.assertNotContains(response, 'value="Confirm import"')
                self.assertFalse(Listing.objects.exists())

    def test_preview_is_private_to_its_creator(self):
        url = self.preview()
        self.client.force_login(self.other_admin)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertFalse(Listing.objects.exists())

    def test_expired_preview_cannot_be_imported_and_is_removed_on_next_upload(self):
        url = self.preview()
        batch = ListingImportBatch.objects.get()
        ListingImportBatch.objects.filter(pk=batch.pk).update(created_at=timezone.now() - timedelta(minutes=31))
        response = self.client.post(url, follow=True)
        self.assertContains(response, 'preview expired')
        self.assertFalse(Listing.objects.exists())
        self.preview()
        self.assertFalse(ListingImportBatch.objects.filter(pk=batch.pk).exists())

    def test_failed_database_write_rolls_back_listings_logs_and_completion(self):
        url = self.preview([self.item(), self.item(name='Second item')])
        with patch('listings.admin.ListingAdmin.log_addition', side_effect=IntegrityError('simulated failure')):
            response = self.client.post(url, follow=True)
        self.assertContains(response, 'No items were added.')
        self.assertFalse(Listing.objects.exists())
        self.assertFalse(LogEntry.objects.exists())
        batch = ListingImportBatch.objects.get()
        self.assertIsNone(batch.completed_at)
        self.assertEqual(len(batch.rows), 2)
        self.client.post(url)
        self.assertEqual(Listing.objects.count(), 2)

    def test_preview_and_validation_errors_escape_csv_content(self):
        malicious = '<script>alert("x")</script>'
        url = self.preview([self.item(name=malicious, description=malicious)])
        response = self.client.get(url)
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, malicious)
        upload = SimpleUploadedFile('items.csv', f'{malicious},price\n'.encode())
        response = self.client.post(self.upload_url, {'csv_file': upload, 'default_seller': self.seller.pk})
        self.assertNotContains(response, malicious)

    def test_permissions_protect_all_endpoints_and_are_rechecked_on_confirmation(self):
        url = self.preview()
        for user in (None, self.seller, self.staff):
            self.client.logout()
            if user:
                self.client.force_login(user)
            for endpoint in (self.upload_url, self.template_url, url):
                for method in ('get', 'post'):
                    with self.subTest(user=user, endpoint=endpoint, method=method):
                        response = getattr(self.client, method)(endpoint)
                        self.assertEqual(response.status_code, 403 if user == self.staff else 302)
        self.admin.is_superuser = False
        self.admin.save()
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.assertFalse(Listing.objects.exists())

    def test_staff_with_listing_add_permission_can_import_but_view_only_staff_cannot(self):
        view_permission = Permission.objects.get(content_type__app_label='listings', codename='view_listing')
        add_permission = Permission.objects.get(content_type__app_label='listings', codename='add_listing')
        self.staff.user_permissions.add(view_permission)
        self.client.force_login(self.staff)
        self.assertNotContains(self.client.get(self.list_url), f'href="{self.upload_url}"')
        self.assertEqual(self.client.get(self.upload_url).status_code, 403)
        self.staff.user_permissions.add(add_permission)
        self.assertContains(self.client.get(self.list_url), f'href="{self.upload_url}"')
        self.client.post(self.preview())
        self.assertEqual(Listing.objects.count(), 1)

    def test_upload_and_confirmation_require_csrf_and_accept_valid_tokens(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(self.upload(client=client).status_code, 403)
        client.get(self.upload_url)
        token = client.cookies['csrftoken'].value
        response = self.upload(client=client, csrfmiddlewaretoken=token)
        self.assertEqual(response.status_code, 302)
        url = response.url
        self.assertEqual(client.post(url).status_code, 403)
        self.assertFalse(Listing.objects.exists())
        self.assertEqual(client.post(url, {'csrfmiddlewaretoken': token}).status_code, 302)
        self.assertEqual(Listing.objects.count(), 1)

    def test_unsupported_methods_do_not_create_items(self):
        url = self.preview()
        for endpoint in (self.upload_url, self.template_url, url):
            self.assertEqual(self.client.put(endpoint).status_code, 405)
        self.assertEqual(self.client.post(self.template_url).status_code, 405)
        self.assertFalse(Listing.objects.exists())
