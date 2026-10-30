from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from listings.models import Listing
from main.models import CartItem, TransactionHistory
from reviews.models import Review


class ReviewModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = get_user_model()
        cls.buyer = user.objects.create_user(username='review-buyer')
        cls.seller = user.objects.create_user(username='review-seller')
        cls.other = user.objects.create_user(username='review-other')
        cls.listing = Listing.objects.create(seller=cls.seller, name='Denim jacket', price=100000)
        cls.order = TransactionHistory.objects.create(
            buyer=cls.buyer, listing=cls.listing, item_name='Denim jacket', price=100000, status='completed',
        )

    def make_review(self, **changes):
        values = dict(transaction=self.order, listing=self.listing, reviewer=self.buyer,
                      rating=5, comment='Great condition.')
        values.update(changes)
        return Review(**values)

    def test_valid_review_and_optional_comment(self):
        review = self.make_review(comment='')
        review.full_clean()
        review.save()
        review.refresh_from_db()
        self.assertEqual(review.rating, 5)
        self.assertIsNotNone(review.created_at)
        self.assertIsNotNone(review.updated_at)

    def test_rating_bounds_at_validation_and_database(self):
        for value in [0, 6]:
            with self.subTest(rating=value):
                with self.assertRaises(ValidationError):
                    self.make_review(rating=value).full_clean()
                with self.assertRaises(IntegrityError), transaction.atomic():
                    self.make_review(rating=value).save()
        self.make_review(rating=1).full_clean()

    def test_comment_length(self):
        self.make_review(comment='a' * 500).full_clean()
        with self.assertRaises(ValidationError):
            self.make_review(comment='a' * 501).full_clean()

    def test_unpurchased_product_is_rejected_even_with_same_name(self):
        other_listing = Listing.objects.create(seller=self.seller, name=self.listing.name, price=100000)
        with self.assertRaises(ValidationError) as error:
            self.make_review(listing=other_listing).full_clean()
        self.assertIn('listing', error.exception.message_dict)

    def test_historical_order_without_link_cannot_be_reviewed(self):
        self.order.listing = None
        self.order.save()
        with self.assertRaises(ValidationError) as error:
            self.make_review().full_clean()
        self.assertIn('transaction', error.exception.message_dict)

    def test_only_transaction_buyer_can_review(self):
        with self.assertRaises(ValidationError) as error:
            self.make_review(reviewer=self.other).full_clean()
        self.assertIn('reviewer', error.exception.message_dict)

    def test_cannot_review_own_listing(self):
        self.listing.seller = self.buyer
        self.listing.save()
        with self.assertRaises(ValidationError) as error:
            self.make_review().full_clean()
        self.assertIn('listing', error.exception.message_dict)

    def test_only_completed_transactions_can_be_reviewed(self):
        for status in ['ongoing', 'delivered', 'cancelled']:
            with self.subTest(status=status):
                self.order.status = status
                self.order.save()
                with self.assertRaises(ValidationError) as error:
                    self.make_review().full_clean()
                self.assertIn('transaction', error.exception.message_dict)

    def test_duplicate_review_rejected_but_existing_review_editable(self):
        review = self.make_review()
        review.full_clean()
        review.save()
        with self.assertRaises(ValidationError):
            self.make_review().full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_review().save()
        review.rating = 4
        review.full_clean()
        review.save()
        self.assertEqual(Review.objects.get(pk=review.pk).rating, 4)


class TransactionReviewPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = get_user_model()
        cls.buyer = user.objects.create_user(username='detail-buyer', first_name='Test', last_name='Buyer', email='buyer@example.test')
        cls.other = user.objects.create_user(username='detail-other')
        cls.order = TransactionHistory.objects.create(
            buyer=cls.buyer, item_name='Actual jacket', price=245000,
            status='delivered', item_count=2, seller_name='Actual seller',
            order_number='WB-TEST-42', item_image_url='/static/img/products/vintage-denim-jacket.jpeg',
        )

    def url(self, pk=None):
        return reverse('main:transaction_review', args=[pk or self.order.pk])

    def test_anonymous_redirects_to_login(self):
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/?next=', response.url)

    def test_owner_sees_actual_order_without_preview_data(self):
        self.client.force_login(self.buyer)
        response = self.client.get(self.url())
        for value in ['WB-TEST-42', 'Actual jacket', 'Actual seller', 'Rp245.000', self.order.item_image_url]:
            self.assertContains(response, value)
        self.assertNotContains(response, '67420')
        self.assertNotContains(response, 'Sample order')
        self.assertNotContains(response, 'Toko Thrift Terbaik Indonesia')
        self.assertContains(response, reverse('main:transaction_history'))
        self.assertIn('no-store', response.headers['Cache-Control'])

    def test_other_buyer_and_missing_order_return_404(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url()).status_code, 404)
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get(self.url(self.order.pk + 1000)).status_code, 404)

    def test_only_delivered_and_completed_orders_are_accessible(self):
        self.client.force_login(self.buyer)
        for status, code in [('ongoing', 404), ('cancelled', 404), ('delivered', 200), ('completed', 200)]:
            with self.subTest(status=status):
                self.order.status = status
                self.order.save()
                self.assertEqual(self.client.get(self.url()).status_code, code)
                history = self.client.get(reverse('main:transaction_history'))
                if code == 200:
                    self.assertContains(history, self.url())
                else:
                    self.assertNotContains(history, self.url())

    def test_missing_image_and_seller_have_fallbacks(self):
        self.order.item_image_url = ''
        self.order.seller_name = ''
        self.order.save()
        self.client.force_login(self.buyer)
        response = self.client.get(self.url())
        self.assertContains(response, 'Product image unavailable')
        self.assertContains(response, 'Seller information unavailable')

    def test_post_cannot_create_review_or_change_status(self):
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.post(self.url(), {'rating': 5}).status_code, 405)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'delivered')
        self.assertFalse(Review.objects.exists())


class CheckoutReviewLinkTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = get_user_model()
        cls.buyer = user.objects.create_user(username='checkout-review-buyer')
        cls.seller = user.objects.create_user(username='checkout-review-seller', first_name='Test', last_name='Seller')
        cls.listing = Listing.objects.create(seller=cls.seller, name='Purchased jacket', price=150000, stock=3)

    def test_checkout_links_each_order_and_keeps_snapshot(self):
        second_listing = Listing.objects.create(seller=self.seller, name='Scarf', price=50000, stock=2)
        first = CartItem.objects.create(buyer=self.buyer, listing=self.listing, quantity=2)
        second = CartItem.objects.create(buyer=self.buyer, listing=second_listing, quantity=1)
        self.client.force_login(self.buyer)
        response = self.client.post(reverse('main:checkout_cart'), {
            'selected_cart_ids': f'{first.pk},{second.pk}',
        })
        self.assertRedirects(response, reverse('main:transaction_history'), fetch_redirect_response=False)
        orders = TransactionHistory.objects.filter(buyer=self.buyer)
        self.assertEqual(orders.count(), 2)
        order = orders.get(listing=self.listing)
        self.assertEqual(order.price, 300000)
        self.assertEqual(order.item_count, 2)
        self.assertEqual(order.seller_name, 'Test Seller')
        self.assertEqual(orders.get(listing=second_listing).price, 50000)
        self.assertFalse(CartItem.objects.filter(pk__in=[first.pk, second.pk]).exists())
        # Later product edits must not overwrite the purchased name or total.
        self.listing.name = 'Renamed jacket'
        self.listing.price = 999999
        self.listing.save()
        order.refresh_from_db()
        self.assertEqual(order.item_name, 'Purchased jacket')
        self.assertEqual(order.price, 300000)
        order.status = 'completed'
        order.save()
        Review(transaction=order, listing=self.listing, reviewer=self.buyer, rating=5).full_clean()

    def test_deleting_product_preserves_order_but_blocks_new_reviews(self):
        order = TransactionHistory.objects.create(
            buyer=self.buyer, listing=self.listing, item_name='Purchased jacket', price=150000, status='completed',
        )
        self.listing.delete()
        order.refresh_from_db()
        self.assertIsNone(order.listing_id)
        self.assertEqual(order.item_name, 'Purchased jacket')
        replacement = Listing.objects.create(seller=self.seller, name='Purchased jacket', price=150000)
        with self.assertRaises(ValidationError):
            Review(transaction=order, listing=replacement, reviewer=self.buyer, rating=5).full_clean()
