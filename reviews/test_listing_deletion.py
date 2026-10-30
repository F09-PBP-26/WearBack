from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse

from listings.models import Listing
from main.models import TransactionHistory
from reviews.models import Review


class ReviewedListingDeletionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = get_user_model()
        cls.seller = user.objects.create_user(username='protected-seller')
        cls.buyer = user.objects.create_user(username='protected-buyer')
        cls.listing = Listing.objects.create(seller=cls.seller, name='Reviewed jacket', price=100000)
        cls.order = TransactionHistory.objects.create(
            buyer=cls.buyer, listing=cls.listing, item_name=cls.listing.name,
            price=100000, status='completed',
        )
        cls.review = Review.objects.create(
            transaction=cls.order, listing=cls.listing, reviewer=cls.buyer, rating=5,
        )

    def test_reviewed_listing_get_and_post_show_notice_and_preserve_data(self):
        self.client.force_login(self.seller)
        for method in ['get', 'post']:
            with self.subTest(method=method):
                response = getattr(self.client, method)(reverse('listings:delete', args=[self.listing.pk]), follow=True)
                self.assertRedirects(response, reverse('listings:detail', args=[self.listing.pk]))
                self.assertContains(response, 'This listing has buyer reviews and cannot be deleted.')
                self.assertContains(response, 'Set its stock to 0')
                self.assertTrue(Listing.objects.filter(pk=self.listing.pk).exists())
                self.assertTrue(Review.objects.filter(pk=self.review.pk).exists())
                self.order.refresh_from_db()
                self.assertEqual(self.order.listing_id, self.listing.pk)

    def test_non_owner_still_receives_404(self):
        self.client.force_login(self.buyer)
        for method in ['get', 'post']:
            response = getattr(self.client, method)(reverse('listings:delete', args=[self.listing.pk]))
            self.assertEqual(response.status_code, 404)

    def test_protection_added_after_check_is_handled(self):
        unreviewed = Listing.objects.create(seller=self.seller, name='New item', price=50)
        self.client.force_login(self.seller)
        with patch.object(Listing, 'delete', side_effect=ProtectedError('Protected', {self.review})):
            response = self.client.post(reverse('listings:delete', args=[unreviewed.pk]), follow=True)
        self.assertRedirects(response, reverse('listings:detail', args=[unreviewed.pk]))
        self.assertContains(response, 'linked to protected records')
        self.assertTrue(Listing.objects.filter(pk=unreviewed.pk).exists())
