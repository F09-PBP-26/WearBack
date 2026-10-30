from datetime import timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from listings.models import Listing
from main.models import DropoffLocation, TransactionHistory, User


class SellerInstaShipTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.buyer = User.objects.create_user(username='shipping-buyer', first_name='Alex', last_name='Buyer')
        cls.seller = User.objects.create_user(username='shipping-seller')
        cls.other_seller = User.objects.create_user(username='shipping-other', is_staff=True, is_superuser=True)
        cls.listing = Listing.objects.create(seller=cls.seller, name='Paid vintage jacket', price=150000, stock=0)
        cls.order = TransactionHistory.objects.create(
            buyer=cls.buyer, listing=cls.listing, item_name=cls.listing.name, price=150000, status='paid',
        )
        cls.location = DropoffLocation.objects.create(
            transaction=cls.order, address='UI Library, Depok', latitude='-6.370375', longitude='106.827413',
        )
        cls.url = reverse('listings:ship_order', args=[cls.order.pk])
        cls.dashboard_url = reverse('listings:mine')

    def setUp(self):
        self.client.force_login(self.seller)

    def test_seller_confirms_paid_order_from_dashboard(self):
        page = self.client.get(self.dashboard_url)
        self.assertEqual(list(page.context['ready_to_ship']), [self.order])
        for text in ('1 order', 'Insta ship', 'complete it immediately', 'Alex Buyer', self.location.address, self.url):
            self.assertContains(page, text)
        self.assertNotContains(page, 'Confirm shipment')
        self.assertNotContains(page, 'id="ship-order-')
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertIsNone(self.order.completed_at)
        response = self.client.post(self.url, follow=True)
        self.assertContains(response, f'Order #{self.order.pk} is complete. Insta ship confirmed!')
        self.assertContains(response, 'Recently completed')
        self.assertEqual(list(response.context['ready_to_ship']), [])
        self.assertNotContains(response, 'data-dialog-open="ship-order-')
        self.order.refresh_from_db()
        self.listing.refresh_from_db()
        self.assertEqual(self.order.status, 'completed')
        self.assertIsNotNone(self.order.completed_at)
        self.assertEqual(self.listing.stock, 0)

    def test_buyer_and_other_seller_cannot_confirm_even_with_order_id(self):
        for user in (self.buyer, self.other_seller):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(self.client.post(self.url).status_code, 404)
                page = self.client.get(self.dashboard_url)
                self.assertEqual(list(page.context['ready_to_ship']), [])
                self.assertNotContains(page, self.location.address)
                self.assertNotContains(page, self.url)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertIsNone(self.order.completed_at)

    def test_dashboard_excludes_other_sellers_orders_and_private_addresses(self):
        listing = Listing.objects.create(seller=self.other_seller, name='Other seller private order', price=100000)
        order = TransactionHistory.objects.create(
            buyer=self.buyer, listing=listing, item_name=listing.name, price=100000, status='paid',
        )
        DropoffLocation.objects.create(
            transaction=order, address='Other seller private destination', latitude=0, longitude=0,
        )
        page = self.client.get(self.dashboard_url)
        self.assertEqual(list(page.context['ready_to_ship']), [self.order])
        self.assertNotContains(page, order.item_name)
        self.assertNotContains(page, 'Other seller private destination')

    def test_unpaid_or_final_orders_cannot_be_completed(self):
        for status in ('ongoing', 'delivered', 'completed', 'cancelled'):
            with self.subTest(status=status):
                TransactionHistory.objects.filter(pk=self.order.pk).update(status=status)
                self.assertRedirects(self.client.post(self.url), self.dashboard_url)
                self.order.refresh_from_db()
                self.assertEqual(self.order.status, status)
                self.assertIsNone(self.order.completed_at)
                self.assertNotContains(self.client.get(self.dashboard_url), self.url)

    def test_double_confirmation_preserves_original_completion_time_and_stock(self):
        self.client.post(self.url)
        self.order.refresh_from_db()
        completed_at = self.order.completed_at
        self.assertRedirects(self.client.post(self.url), self.dashboard_url)
        self.order.refresh_from_db()
        self.listing.refresh_from_db()
        self.assertEqual(self.order.status, 'completed')
        self.assertEqual(self.order.completed_at, completed_at)
        self.assertEqual(self.listing.stock, 0)

    def test_paid_order_without_address_cannot_be_completed(self):
        self.location.delete()
        response = self.client.post(self.url, follow=True)
        self.assertContains(response, 'needs a saved drop-off address')
        self.assertNotContains(response, 'data-dialog-open="ship-order-')
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertIsNone(self.order.completed_at)

    def test_historical_order_without_listing_cannot_be_claimed_by_seller(self):
        TransactionHistory.objects.filter(pk=self.order.pk).update(listing=None)
        self.assertEqual(self.client.post(self.url).status_code, 404)
        self.assertEqual(list(self.client.get(self.dashboard_url).context['ready_to_ship']), [])

    def test_get_does_not_confirm_and_post_requires_csrf(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.seller)
        self.assertEqual(csrf_client.post(self.url).status_code, 403)
        csrf_client.get(self.dashboard_url)
        token = csrf_client.cookies['csrftoken'].value
        self.assertRedirects(csrf_client.post(self.url, HTTP_X_CSRFTOKEN=token), self.dashboard_url)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'completed')

    def test_guests_must_sign_in(self):
        self.client.logout()
        self.assertRedirects(
            self.client.post(self.url), reverse('main:login') + '?next=' + self.url,
            fetch_redirect_response=False,
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')

    def test_paid_orders_do_not_expire_and_buyer_cannot_override_status(self):
        self.client.force_login(self.buyer)
        TransactionHistory.objects.filter(pk=self.order.pk).update(
            payment_deadline=timezone.now() - timedelta(minutes=1),
        )
        self.client.get(reverse('main:transaction_history'))
        self.client.post(reverse('main:pay_transaction', args=[self.order.pk]), {'status': 'completed'})
        page = self.client.get(reverse('main:dropoff', args=[self.order.pk]))
        self.assertContains(page, 'Awaiting seller')
        self.assertNotContains(page, 'id="pay-now-button"')
        self.assertNotContains(page, self.url)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertIsNone(self.order.completed_at)

    def test_listing_with_paid_order_cannot_be_deleted(self):
        for method in ('get', 'post'):
            with self.subTest(method=method):
                response = getattr(self.client, method)(reverse('listings:delete', args=[self.listing.pk]), follow=True)
                self.assertContains(response, 'paid orders awaiting seller confirmation and cannot be deleted')
                self.assertTrue(Listing.objects.filter(pk=self.listing.pk).exists())
                self.order.refresh_from_db()
                self.assertEqual(self.order.listing_id, self.listing.pk)

    def test_shipping_is_no_longer_an_order_status(self):
        self.assertNotIn('shipping', dict(TransactionHistory.STATUS_CHOICES))
