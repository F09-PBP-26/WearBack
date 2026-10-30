from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse

from listings.models import Listing
from main.models import DropoffLocation, TransactionHistory, User


class DropoffLocationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.buyer = User.objects.create_user(username='dropoff-buyer')
        cls.seller = User.objects.create_user(username='dropoff-seller')
        cls.listing = Listing.objects.create(seller=cls.seller, name='Drop-off jacket', price=150000, stock=2)
        cls.order = TransactionHistory.objects.create(
            buyer=cls.buyer, listing=cls.listing, item_name=cls.listing.name, price=150000,
        )
        cls.url = reverse('main:dropoff', args=[cls.order.pk])

    def setUp(self):
        self.client.force_login(self.buyer)
        self.location = {'address': 'UI Library, Depok', 'latitude': '-6.370375', 'longitude': '106.827413'}

    def test_page_has_map_address_form_and_actual_order_details(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'id="dropoff-map"')
        self.assertContains(response, 'id="location-picker-map"')
        self.assertContains(response, 'Save drop-off location')
        self.assertContains(response, f'#{self.order.pk}')
        self.assertContains(response, 'Drop-off jacket')
        self.assertContains(response, 'No location selected')
        self.assertFalse(DropoffLocation.objects.exists())

    def test_save_and_reload_preserve_address_and_map_coordinates(self):
        response = self.client.post(self.url, self.location)
        self.assertRedirects(response, self.url)
        saved = DropoffLocation.objects.get(transaction=self.order)
        self.assertEqual(saved.address, self.location['address'])
        self.assertEqual(saved.latitude, Decimal('-6.370375'))
        self.assertEqual(saved.longitude, Decimal('106.827413'))
        page = self.client.get(self.url)
        self.assertContains(page, 'UI Library, Depok')
        self.assertContains(page, 'value="-6.370375"')
        self.assertContains(page, 'value="106.827413"')
        self.assertContains(page, 'Location saved')

    def test_updating_location_does_not_duplicate_it_or_change_the_order(self):
        self.client.post(self.url, self.location)
        response = self.client.post(self.url, {
            'address': 'New address', 'latitude': '0', 'longitude': '0',
        })
        self.assertRedirects(response, self.url)
        self.assertEqual(DropoffLocation.objects.count(), 1)
        saved = DropoffLocation.objects.get(transaction=self.order)
        self.assertEqual(saved.address, 'New address')
        self.assertEqual(saved.latitude, 0)
        self.assertEqual(saved.longitude, 0)
        self.order.refresh_from_db()
        self.listing.refresh_from_db()
        self.assertEqual(self.order.status, 'ongoing')
        self.assertEqual(self.order.price, 150000)
        self.assertEqual(self.listing.stock, 2)

    def test_invalid_address_or_coordinates_are_rejected(self):
        for invalid in (
            {'address': ''}, {'address': 'x' * 501}, {'latitude': ''}, {'longitude': ''},
            {'latitude': '90.000001'}, {'latitude': '-90.000001'},
            {'longitude': '180.000001'}, {'longitude': '-180.000001'}, {'latitude': 'NaN'},
        ):
            with self.subTest(invalid=invalid):
                response = self.client.post(self.url, {**self.location, **invalid})
                self.assertEqual(response.status_code, 400)
                self.assertFalse(DropoffLocation.objects.exists())

    def test_other_users_cannot_read_or_overwrite_the_address(self):
        self.client.post(self.url, self.location)
        self.client.force_login(self.seller)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(self.url, {**self.location, 'address': 'Replaced'}).status_code, 404)
        self.assertEqual(DropoffLocation.objects.get(transaction=self.order).address, self.location['address'])

    def test_guests_must_sign_in_before_viewing_or_saving(self):
        self.client.logout()
        self.assertRedirects(
            self.client.get(self.url), reverse('main:login') + '?next=' + self.url,
            fetch_redirect_response=False,
        )
        self.assertEqual(self.client.post(self.url, self.location).status_code, 302)
        self.assertFalse(DropoffLocation.objects.exists())

    def test_save_requires_csrf_protection(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.buyer)
        self.assertEqual(client.post(self.url, self.location).status_code, 403)
        self.assertFalse(DropoffLocation.objects.exists())
