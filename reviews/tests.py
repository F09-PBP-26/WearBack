from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from listings.models import Listing
from main.models import TransactionHistory
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
            buyer=cls.buyer, item_name='Denim jacket', price=100000, status='completed',
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
