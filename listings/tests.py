from decimal import Decimal
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse

from listings.models import Listing
from listings.forms import ListingForm
from main.models import SSOIdentity

User = get_user_model()


class SellerScreenTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user(username='screen-seller', first_name='Screen', last_name='Seller')
        cls.other = User.objects.create_user(username='screen-other')
        cls.listing = Listing.objects.create(seller=cls.seller, name='Vintage coat', price=Decimal('1234.50'),
                                             size='Custom fit', stock=2, image_url='https://example.com/coat.jpg')
        Listing.objects.create(seller=cls.other, name='Private dashboard item')

    def setUp(self):
        self.client.force_login(self.seller)

    def test_dashboard_displays_own_inventory_with_real_availability(self):
        Listing.objects.create(seller=self.seller, name='Unpriced scarf')
        Listing.objects.create(seller=self.seller, name='Sold coat', price=100, stock=0)
        response = self.client.get(reverse('listings:mine'))
        self.assertTemplateUsed(response, 'listings/dashboard.html')
        for text in ('Vintage coat', '3 items', 'Listed', 'Needs details', 'Sold out',
                     '0 orders', 'Orders will appear here when checkout is available.'):
            self.assertContains(response, text)
        self.assertNotContains(response, 'Private dashboard item')
        self.assertNotContains(response, 'Awaiting shipment')
        self.assertNotContains(response, '>Draft<')

    def test_empty_dashboard_offers_first_listing(self):
        self.client.force_login(self.other)
        Listing.objects.filter(seller=self.other).delete()
        response = self.client.get(reverse('listings:mine'))
        self.assertContains(response, '0 items')
        self.assertContains(response, 'Create your first item')
        self.assertNotContains(response, 'seller-list-row')

    def test_edit_preserves_custom_size_and_localized_price_on_unchanged_save(self):
        response = self.client.get(reverse('listings:update', args=[self.listing.pk]))
        self.assertContains(response, '<option value="Custom fit" selected>Custom fit</option>', html=True)
        self.assertEqual(response.context['form']['price'].value(), '1.234,50')
        form = ListingForm(instance=self.listing)
        payload = {name: form[name].value() or '' for name in form.fields}
        response = self.client.post(reverse('listings:update', args=[self.listing.pk]), payload)
        self.assertEqual(response.status_code, 302)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.price, Decimal('1234.50'))
        self.assertEqual(self.listing.size, 'Custom fit')
        self.assertEqual(self.listing.stock, 2)

    def test_validation_retains_entered_values_and_exposes_additional_field_errors(self):
        response = self.client.post(reverse('listings:update', args=[self.listing.pk]), {
            'name': 'Changed coat', 'price': '-50', 'stock': '-1', 'size': 'Custom fit',
            'image_url': 'javascript:alert(1)', 'contact_email': 'not-an-email',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Check your item details')
        self.assertEqual(response.context['form']['name'].value(), 'Changed coat')
        self.assertEqual(response.context['form']['price'].value(), '-50')
        self.assertTrue(response.context['form'].extra_details_have_errors)
        self.assertContains(response, '<details class="seller-panel seller-extra" open>')
        self.assertEqual(response.context['form'].preview_image_url, '')
        self.assertNotContains(response, 'src="javascript:')
        self.assertNotContains(response, 'src="https://example.com/coat.jpg"')
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.name, 'Vintage coat')


class ListingPermissionsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username='owner', email='private-owner@example.com',
                                             first_name='Listing', last_name='Owner')
        cls.other = User.objects.create_user(username='other', first_name='Another', last_name='Member')
        cls.staff = User.objects.create_user(username='staff', is_staff=True)
        cls.superuser = User.objects.create_user(username='superuser', is_staff=True, is_superuser=True)
        cls.listing = Listing.objects.create(seller=cls.owner, name='Owner coat', description='A wool coat.',
                                             contact_email='published-contact@example.com')
        cls.other_listing = Listing.objects.create(seller=cls.other, name='Another member’s shirt')

    def listing_url(self, action, pk=None):
        return reverse('listings:' + action, args=[self.listing.pk if pk is None else pk])

    def test_guests_can_browse_without_contact_or_management_links(self):
        for url in [reverse('listings:index'), self.listing_url('detail')]:
            with self.subTest(url=url):
                response = self.client.get(url, follow=True)
                self.assertContains(response, self.listing.name)
                self.assertNotContains(response, self.listing.contact_email)
                self.assertNotContains(response, self.owner.email)
                self.assertNotContains(response, self.listing_url('update'))
                self.assertNotContains(response, self.listing_url('delete'))
        response = self.client.get(self.listing_url('detail'))
        self.assertEqual(response.context['contact_email'], '')
        self.assertIn('private', response.headers['Cache-Control'])
        self.assertIn('no-store', response.headers['Cache-Control'])

    def test_authenticated_non_owner_can_see_published_contact_only(self):
        self.client.force_login(self.other)
        response = self.client.get(self.listing_url('detail'))
        self.assertContains(response, self.listing.contact_email)
        self.assertNotContains(response, self.owner.email)
        self.assertNotContains(response, self.listing_url('update'))
        self.assertNotContains(response, self.listing_url('delete'))
        self.assertIn('no-store', response.headers['Cache-Control'])

    def test_account_email_is_not_used_as_contact(self):
        self.listing.contact_email = ''
        self.listing.save()
        self.client.force_login(self.other)
        response = self.client.get(self.listing_url('detail'))
        self.assertNotContains(response, self.owner.email)
        self.assertContains(response, 'hasn’t shared a contact email')

    def test_owner_sees_management_links(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.listing_url('detail'))
        self.assertContains(response, self.listing_url('update'))
        self.assertContains(response, self.listing_url('delete'))

    def test_guests_are_redirected_before_reading_or_changing_private_pages(self):
        urls = [reverse('listings:create'), reverse('listings:mine'),
                self.listing_url('update'), self.listing_url('delete')]
        for url in urls:
            for method in ('get', 'post'):
                with self.subTest(url=url, method=method):
                    response = getattr(self.client, method)(url)
                    self.assertEqual(response.status_code, 302)
                    parsed = urlparse(response.url)
                    self.assertEqual(parsed.path, reverse('main:login'))
                    self.assertEqual(parse_qs(parsed.query)['next'], [url])
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.name, 'Owner coat')
        self.assertEqual(Listing.objects.count(), 2)

    def test_any_member_can_create_but_cannot_choose_another_seller(self):
        for user in (self.owner, self.other):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.post(reverse('listings:create'), {
                    'name': 'New listing by ' + user.username, 'description': 'Preloved clothing',
                    'contact_email': 'optional-contact@example.com',
                    'seller': self.staff.pk, 'seller_id': self.staff.pk,
                })
                listing = Listing.objects.get(name='New listing by ' + user.username)
                self.assertEqual(listing.seller, user)
                self.assertRedirects(response, reverse('listings:detail', args=[listing.pk]))

    def test_owner_can_update_without_transferring_ownership(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.listing_url('update')).status_code, 200)
        response = self.client.post(self.listing_url('update'), {
            'name': 'Updated coat', 'description': 'Updated description',
            'contact_email': '', 'seller': self.other.pk, 'seller_id': self.other.pk,
        })
        self.assertRedirects(response, self.listing_url('detail'))
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.name, 'Updated coat')
        self.assertEqual(self.listing.seller, self.owner)

    def test_other_members_staff_and_superusers_cannot_manage_another_listing(self):
        for user in (self.other, self.staff, self.superuser):
            self.client.force_login(user)
            for action in ('update', 'delete'):
                for method in ('get', 'post'):
                    with self.subTest(user=user.username, action=action, method=method):
                        response = getattr(self.client, method)(self.listing_url(action), {
                            'name': 'Unauthorized change', 'contact_email': 'changed@example.com',
                        })
                        self.assertEqual(response.status_code, 404)
                        self.listing.refresh_from_db()
                        self.assertEqual(self.listing.name, 'Owner coat')
                        self.assertEqual(self.listing.seller, self.owner)
                        self.assertEqual(self.listing.contact_email, 'published-contact@example.com')
        self.assertEqual(Listing.objects.count(), 2)

    def test_my_listings_only_contains_the_current_members_items(self):
        for user, own, other in ((self.owner, self.listing, self.other_listing),
                                 (self.other, self.other_listing, self.listing)):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(reverse('listings:mine'))
                self.assertContains(response, own.name)
                self.assertNotContains(response, other.name)
                self.assertQuerySetEqual(response.context['listings'], [own])

    def test_delete_requires_confirmation_post_and_preserves_other_listings(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.listing_url('delete'))
        self.assertContains(response, 'csrfmiddlewaretoken')
        self.assertTrue(Listing.objects.filter(pk=self.listing.pk).exists())
        response = self.client.post(self.listing_url('delete'))
        self.assertRedirects(response, reverse('listings:mine'))
        self.assertFalse(Listing.objects.filter(pk=self.listing.pk).exists())
        self.assertTrue(Listing.objects.filter(pk=self.other_listing.pk).exists())

    def test_invalid_forms_do_not_create_or_modify_listings(self):
        self.client.force_login(self.owner)
        for url in (reverse('listings:create'), self.listing_url('update')):
            with self.subTest(url=url):
                response = self.client.post(url, {'name': '', 'contact_email': 'invalid-email'})
                self.assertEqual(response.status_code, 200)
                self.assertIn('name', response.context['form'].errors)
                self.assertIn('contact_email', response.context['form'].errors)
                self.assertEqual(Listing.objects.count(), 2)
                self.listing.refresh_from_db()
                self.assertEqual(self.listing.name, 'Owner coat')

    def test_mutations_require_csrf_even_for_the_owner(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        for url in (reverse('listings:create'), self.listing_url('update'), self.listing_url('delete')):
            with self.subTest(url=url):
                self.assertEqual(client.post(url, {'name': 'Changed coat'}).status_code, 403)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.name, 'Owner coat')
        self.assertEqual(Listing.objects.count(), 2)

    def test_valid_csrf_posts_can_create_update_and_delete(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        client.get(reverse('listings:create'))
        token = client.cookies['csrftoken'].value
        response = client.post(reverse('listings:create'), {'name': 'CSRF checked listing'}, HTTP_X_CSRFTOKEN=token)
        listing = Listing.objects.get(name='CSRF checked listing')
        self.assertEqual(response.status_code, 302)
        response = client.post(self.listing_url('update', listing.pk), {'name': 'Updated with token'},
                               HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 302)
        listing.refresh_from_db()
        self.assertEqual(listing.name, 'Updated with token')
        response = client.post(self.listing_url('delete', listing.pk), HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Listing.objects.filter(pk=listing.pk).exists())

    def test_unsupported_methods_cannot_change_listings(self):
        self.client.force_login(self.owner)
        for url in (reverse('listings:create'), self.listing_url('update'), self.listing_url('delete')):
            for method in ('put', 'patch', 'delete'):
                with self.subTest(url=url, method=method):
                    self.assertEqual(getattr(self.client, method)(url).status_code, 405)
        self.assertEqual(Listing.objects.count(), 2)

    def test_missing_listings_return_404(self):
        missing_pk = self.other_listing.pk + 1000
        self.assertEqual(self.client.get(self.listing_url('detail', missing_pk)).status_code, 404)
        self.client.force_login(self.owner)
        for action in ('update', 'delete'):
            for method in ('get', 'post'):
                with self.subTest(action=action, method=method):
                    self.assertEqual(getattr(self.client, method)(self.listing_url(action, missing_pk)).status_code, 404)

    def test_sso_only_members_have_the_same_listing_permissions(self):
        user = User.objects.create_user(username='sso-member', first_name='SSO', last_name='Member')
        self.assertFalse(user.has_usable_password())
        SSOIdentity.objects.create(user=user, subject='listing-sso-member')
        self.client.force_login(user, backend='django.contrib.auth.backends.ModelBackend')
        response = self.client.post(reverse('listings:create'), {'name': 'SSO member listing'})
        listing = Listing.objects.get(name='SSO member listing')
        self.assertRedirects(response, reverse('listings:detail', args=[listing.pk]))
        self.assertEqual(listing.seller, user)
        self.assertContains(self.client.get(self.listing_url('detail')), self.listing.contact_email)
        self.assertEqual(self.client.post(self.listing_url('delete')).status_code, 404)


class ItemDetailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user(username='detail-seller', first_name='Vintage', last_name='Seller',
                                              email='private-login@example.com')
        cls.buyer = User.objects.create_user(username='detail-buyer', first_name='Buyer', last_name='Member')
        cls.listing = Listing.objects.create(
            seller=cls.seller, name='Vintage wool scarf', description='A soft wool scarf.',
            price=Decimal('300000.00'), image_url='https://example.com/scarf.jpg',
            category=Listing.Category.ACCESSORIES, size='M', condition=Listing.Condition.GREAT,
            brand='Wear Again', material='Wool', style='Casual, vintage', location='Depok, Indonesia',
            stock=3, contact_email='published-seller@example.com',
        )
        Listing.objects.create(seller=cls.seller, name='Another item')
        cls.url = reverse('listings:detail', args=[cls.listing.pk])

    def test_detail_uses_saved_product_fields_and_actual_seller_count(self):
        response = self.client.get(self.url)
        for value in ('Vintage wool scarf', 'Rp300.000', 'Accessories', 'Great', 'Wool', 'Wear Again',
                      'Casual, vintage', 'Depok, Indonesia', '3 available', '2 listings', 'No ratings yet'):
            with self.subTest(value=value):
                self.assertContains(response, value)
        self.assertContains(response, self.listing.image_url)
        self.assertNotContains(response, '4.8 / 5')
        self.assertNotContains(response, '67 products')
        self.assertNotContains(response, self.seller.email)
        self.assertNotContains(response, self.listing.contact_email)

    def test_guest_has_sign_in_action_and_no_cart_or_owner_dialog(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'Sign in to shop')
        self.assertContains(response, '/login/?next=' + self.url)
        self.assertNotContains(response, 'Add to cart')
        self.assertNotContains(response, 'delete-listing-dialog')

    def test_buyer_has_quantity_control_cart_notice_and_published_contact(self):
        self.client.force_login(self.buyer)
        response = self.client.get(self.url)
        self.assertContains(response, 'id="item-quantity"')
        self.assertContains(response, 'max="3"')
        self.assertContains(response, 'Add to cart')
        self.assertContains(response, 'Shopping cart is coming soon.')
        self.assertContains(response, self.listing.contact_email)
        self.assertNotContains(response, self.seller.email)
        self.assertNotContains(response, 'delete-listing-dialog')

    def test_owner_gets_management_dialog_and_cannot_buy_own_item(self):
        self.client.force_login(self.seller)
        response = self.client.get(self.url)
        self.assertContains(response, 'Your listing')
        self.assertContains(response, 'id="delete-listing-dialog"')
        self.assertContains(response, 'Keep listing')
        self.assertContains(response, 'csrfmiddlewaretoken')
        self.assertNotContains(response, 'Add to cart')
        self.assertNotContains(response, 'id="item-quantity"')

    def test_sold_out_items_have_no_purchase_or_quantity_controls(self):
        self.listing.stock = 0
        self.listing.save()
        self.client.force_login(self.buyer)
        response = self.client.get(self.url)
        self.assertContains(response, 'This item is sold out.')
        self.assertContains(response, 'disabled>Sold out</button>')
        self.assertNotContains(response, 'Add to cart')
        self.assertNotContains(response, 'id="item-quantity"')

    def test_legacy_listing_without_new_fields_has_honest_fallbacks(self):
        listing = Listing.objects.get(name='Another item')
        response = self.client.get(reverse('listings:detail', args=[listing.pk]))
        self.assertContains(response, 'Price not set')
        self.assertContains(response, 'Currently unavailable')
        self.assertContains(response, 'Not specified')
        self.assertContains(response, 'item-photo-placeholder.png')
        self.assertNotContains(response, 'Rp300.000')
        self.assertNotContains(response, 'id="item-quantity"')

    def test_price_display_formats_rupiah_without_using_floating_point(self):
        for price, expected in ((Decimal('100000.50'), 'Rp100.000,50'),
                                (Decimal('1.00'), 'Rp1'), (None, 'Price not set')):
            with self.subTest(price=price):
                self.assertEqual(Listing(price=price).price_display, expected)

    def test_create_saves_detail_fields_and_formats_indonesian_price(self):
        self.client.force_login(self.seller)
        response = self.client.post(reverse('listings:create'), {
            'name': 'New scarf', 'price': '1.234.567,50', 'stock': '2',
            'image_url': 'https://example.com/new-scarf.jpg', 'category': 'accessories',
            'condition': 'good', 'size': 'One size', 'brand': 'Another brand',
            'material': 'Cotton', 'style': 'Vintage', 'location': 'Jakarta',
            'contact_email': 'public-contact@example.com', 'seller': self.buyer.pk,
        })
        listing = Listing.objects.get(name='New scarf')
        self.assertEqual(listing.price, Decimal('1234567.50'))
        self.assertEqual(listing.stock, 2)
        self.assertEqual(listing.material, 'Cotton')
        self.assertEqual(listing.seller, self.seller)
        self.assertRedirects(response, reverse('listings:detail', args=[listing.pk]), fetch_redirect_response=False)
        self.assertContains(self.client.get(response.url), 'Your item is now listed.')

    def test_edit_retains_stock_when_older_form_omits_it(self):
        self.client.force_login(self.seller)
        response = self.client.post(reverse('listings:update', args=[self.listing.pk]), {'name': 'Updated scarf'})
        self.assertEqual(response.status_code, 302)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.stock, 3)

    def test_invalid_price_stock_category_and_image_values_do_not_save(self):
        self.client.force_login(self.seller)
        cases = [('price', '0'), ('price', '-10'), ('price', 'NaN'), ('price', '1.2345'),
                 ('stock', '-1'), ('stock', '10000'), ('stock', '1.5'),
                 ('category', 'not-a-category'), ('condition', 'not-a-condition'),
                 ('image_url', 'javascript:alert(1)'), ('image_url', 'http://example.com/image.jpg')]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                response = self.client.post(reverse('listings:create'), {'name': 'Invalid item', field: value})
                self.assertEqual(response.status_code, 200)
                self.assertIn(field, response.context['form'].errors)
                self.assertFalse(Listing.objects.filter(name='Invalid item').exists())

    def test_database_rejects_non_positive_prices(self):
        for value in (Decimal('0'), Decimal('-1')):
            with self.subTest(value=value), self.assertRaises(IntegrityError), transaction.atomic():
                Listing.objects.create(seller=self.seller, name='Invalid price', price=value)
