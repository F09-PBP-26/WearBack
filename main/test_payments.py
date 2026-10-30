from datetime import timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from listings.models import Listing
from main.models import Bid, CartItem, DropoffLocation, TransactionHistory, User


class PaymentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.buyer = User.objects.create_user(username='payment-buyer')
        cls.seller = User.objects.create_user(username='payment-seller')
        cls.listing = Listing.objects.create(
            seller=cls.seller, name='Payment jacket', price=150000, stock=3,
        )
        cls.order = TransactionHistory.objects.create(
            buyer=cls.buyer, listing=cls.listing, item_name=cls.listing.name,
            price=300000, item_count=2, payment_deadline=timezone.now() + timedelta(minutes=10),
        )
        cls.url = reverse('main:pay_transaction', args=[cls.order.pk])
        cls.dropoff_url = reverse('main:dropoff', args=[cls.order.pk])
        cls.history_url = reverse('main:transaction_history')

    def setUp(self):
        self.client.force_login(self.buyer)
        self.location = {
            'address': 'UI Library, Depok', 'latitude': '-6.370375', 'longitude': '106.827413',
        }

    def save_address(self):
        self.client.post(self.dropoff_url, self.location)

    def assert_unpaid(self):
        self.order.refresh_from_db()
        self.listing.refresh_from_db()
        self.assertEqual(self.order.status, 'ongoing')
        self.assertEqual(self.listing.stock, 3)

    def test_checkout_payment_seller_completion_and_review(self):
        cart_item = CartItem.objects.create(buyer=self.buyer, listing=self.listing, quantity=1)
        response = self.client.post(reverse('main:checkout_cart'), {'selected_cart_ids': str(cart_item.pk)})
        self.assertRedirects(response, self.history_url)
        order = TransactionHistory.objects.exclude(pk=self.order.pk).get(buyer=self.buyer)
        dropoff_url = reverse('main:dropoff', args=[order.pk])
        self.assertRedirects(self.client.post(dropoff_url, self.location), dropoff_url)
        response = self.client.post(reverse('main:pay_transaction', args=[order.pk]), follow=True)
        self.assertContains(response, 'Awaiting seller')
        self.assertNotContains(response, 'Your order is shipping.')
        self.assertContains(response, 'Demo payment confirmed')
        self.assertNotContains(response, 'id="pay-now-button"')
        order.refresh_from_db()
        self.listing.refresh_from_db()
        self.assertEqual(order.status, 'paid')
        self.assertIsNone(order.completed_at)
        self.assertEqual(order.price, 150000)
        self.assertIsNone(order.payment_deadline)
        self.assertEqual(self.listing.stock, 2)
        self.assertEqual(order.dropoff_location.address, self.location['address'])
        history = self.client.get(self.history_url)
        self.assertContains(history, 'View order details')
        self.assertContains(history, 'Payment confirmed · Waiting for the seller to complete the order')
        review_url = reverse('reviews:create', args=[order.pk])
        self.assertEqual(self.client.post(review_url, {'rating': 5}).status_code, 400)
        shipping_url = reverse('listings:ship_order', args=[order.pk])
        self.assertEqual(self.client.post(shipping_url).status_code, 404)
        self.client.force_login(self.seller)
        dashboard = self.client.get(reverse('listings:mine'))
        self.assertContains(dashboard, '1 order')
        self.assertContains(dashboard, shipping_url)
        self.assertRedirects(self.client.post(shipping_url), reverse('listings:mine'))
        order.refresh_from_db()
        self.listing.refresh_from_db()
        self.assertEqual(order.status, 'completed')
        self.assertIsNotNone(order.completed_at)
        self.assertEqual(self.listing.stock, 2)
        self.client.force_login(self.buyer)
        history = self.client.get(self.history_url)
        self.assertContains(history, 'Completed')
        self.assertNotContains(history, 'status-shipping')
        self.assertContains(history, reverse('main:transaction_review', args=[order.pk]))
        self.assertContains(self.client.get(dropoff_url), 'Your order is complete.')
        response = self.client.post(review_url, {'rating': 5, 'comment': 'Great purchase!'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(order.reviews.get().reviewer, self.buyer)

    def test_payment_button_requires_a_saved_address(self):
        page = self.client.get(self.dropoff_url)
        self.assertContains(page, 'Pay now')
        self.assertContains(page, 'aria-describedby="payment-help" disabled')
        self.assertContains(page, 'No money is charged')
        self.save_address()
        page = self.client.get(self.dropoff_url)
        self.assertNotContains(page, 'aria-describedby="payment-help" disabled')
        self.assertContains(self.client.get(self.history_url), 'Continue to payment')

    def test_invalid_address_edit_keeps_payment_disabled(self):
        self.save_address()
        response = self.client.post(self.dropoff_url, {**self.location, 'address': ''})
        self.assertContains(response, 'aria-describedby="payment-help" disabled', status_code=400)
        self.assertEqual(DropoffLocation.objects.get(transaction=self.order).address, self.location['address'])

    def test_direct_payment_without_address_is_rejected(self):
        response = self.client.post(self.url, follow=True)
        self.assertContains(response, 'Save your drop-off location before paying.')
        self.assert_unpaid()

    def test_repeat_payment_only_reduces_stock_once(self):
        self.save_address()
        self.assertRedirects(self.client.post(self.url), self.dropoff_url)
        self.assertRedirects(self.client.post(self.url), self.dropoff_url)
        self.order.refresh_from_db()
        self.listing.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertEqual(self.listing.stock, 1)
        self.assertIsNone(self.order.payment_deadline)
        self.client.get(self.history_url)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')

    def test_expired_payment_is_rejected_without_visiting_history(self):
        self.save_address()
        self.order.payment_deadline = timezone.now() - timedelta(seconds=1)
        self.order.save()
        response = self.client.post(self.url, follow=True)
        self.assertContains(response, 'Payment time expired')
        self.assertNotContains(response, 'id="pay-now-button"')
        self.order.refresh_from_db()
        self.listing.refresh_from_db()
        self.assertEqual(self.order.status, 'cancelled')
        self.assertEqual(self.listing.stock, 3)

    def test_expired_dropoff_page_does_not_offer_payment_or_address_edits(self):
        self.order.payment_deadline = timezone.now() - timedelta(seconds=1)
        self.order.save()
        response = self.client.get(self.dropoff_url)
        self.assertContains(response, 'Payment time expired')
        self.assertNotContains(response, 'id="pay-now-button"')
        self.client.post(self.dropoff_url, self.location)
        self.assertFalse(DropoffLocation.objects.exists())

    def test_legacy_order_without_deadline_can_pay(self):
        self.save_address()
        self.order.payment_deadline = None
        self.order.save()
        self.client.post(self.url)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')

    def test_unavailable_or_invalid_order_does_not_start_shipping(self):
        self.save_address()
        for changes in ({'listing': None}, {'item_count': 4}, {'item_count': 0}, {'price': 0}):
            with self.subTest(changes=changes):
                TransactionHistory.objects.filter(pk=self.order.pk).update(**changes)
                self.client.post(self.url)
                self.assert_unpaid()
                TransactionHistory.objects.filter(pk=self.order.pk).update(
                    listing=self.listing, item_count=2, price=300000,
                )

    def test_two_orders_cannot_ship_the_same_last_items(self):
        self.save_address()
        other_order = TransactionHistory.objects.create(
            buyer=self.buyer, listing=self.listing, item_name=self.listing.name,
            price=300000, item_count=2,
        )
        DropoffLocation.objects.create(transaction=other_order, **self.location)
        self.client.post(self.url)
        response = self.client.post(reverse('main:pay_transaction', args=[other_order.pk]), follow=True)
        self.assertContains(response, 'no longer available in the requested quantity')
        other_order.refresh_from_db()
        self.listing.refresh_from_db()
        self.assertEqual(other_order.status, 'ongoing')
        self.assertEqual(self.listing.stock, 1)

    def test_order_cannot_pay_after_item_enters_an_auction(self):
        self.save_address()
        Bid.objects.create(listing=self.listing, bidder=self.buyer, amount=160000)
        response = self.client.post(self.url, follow=True)
        self.assertContains(response, 'now in an auction')
        self.assert_unpaid()

    def test_final_states_cannot_be_paid_or_have_address_changed(self):
        self.save_address()
        for status in ('paid', 'delivered', 'completed', 'cancelled'):
            with self.subTest(status=status):
                TransactionHistory.objects.filter(pk=self.order.pk).update(status=status)
                self.client.post(self.url)
                self.client.post(self.dropoff_url, {**self.location, 'address': 'Replaced'})
                self.order.refresh_from_db()
                self.listing.refresh_from_db()
                self.assertEqual(self.order.status, status)
                self.assertEqual(self.listing.stock, 3)
                self.assertEqual(DropoffLocation.objects.get(transaction=self.order).address, self.location['address'])

    def test_payment_is_post_only_and_buyer_only(self):
        self.save_address()
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.client.force_login(self.seller)
        self.assertEqual(self.client.post(self.url).status_code, 404)
        self.assert_unpaid()

    def test_guests_and_requests_without_csrf_cannot_pay(self):
        self.save_address()
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.buyer)
        self.assertEqual(csrf_client.post(self.url).status_code, 403)
        self.client.logout()
        self.assertRedirects(
            self.client.post(self.url), reverse('main:login') + '?next=' + self.url,
            fetch_redirect_response=False,
        )
        self.assert_unpaid()
