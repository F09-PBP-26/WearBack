from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from listings.models import Listing
from main.models import TransactionHistory
from reviews.models import Review


class ReviewCrudTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = get_user_model()
        cls.buyer = user.objects.create_user(username='crud-buyer', email='private-buyer@example.test')
        cls.seller = user.objects.create_user(username='crud-seller')
        cls.other = user.objects.create_user(username='crud-other')
        cls.listing = Listing.objects.create(seller=cls.seller, name='Denim jacket', price=100000)
        cls.order = TransactionHistory.objects.create(
            buyer=cls.buyer, listing=cls.listing, item_name='Purchased denim', price=100000, status='completed',
        )

    def setUp(self):
        self.client.force_login(self.buyer)

    def create_url(self):
        return reverse('reviews:create', args=[self.order.pk])

    def submit(self, data=None):
        return self.client.post(self.create_url(), data if data is not None else {
            'rating': '5', 'comment': 'Great fit', 'tags': ['Quality', 'Delivery'],
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def saved(self):
        self.assertEqual(self.submit().status_code, 201)
        return Review.objects.get(transaction=self.order)

    def test_create_and_edit_via_ajax(self):
        review = self.saved()
        self.assertEqual(review.tags, ['Quality', 'Delivery'])
        self.assertEqual(review.reviewer, self.buyer)
        response = self.client.post(reverse('reviews:edit', args=[review.pk]), {
            'rating': '3', 'comment': 'Updated opinion', 'tags': ['Description'],
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Review updated.', response.json()['message'])
        review.refresh_from_db()
        self.assertEqual((review.rating, review.comment, review.tags), (3, 'Updated opinion', ['Description']))
        self.assertEqual(Review.objects.count(), 1)

    def test_html_fallback_create_edit_delete(self):
        response = self.client.post(self.create_url(), {'rating': '4', 'comment': 'Nice'})
        self.assertRedirects(response, reverse('main:transaction_review', args=[self.order.pk]))
        review = Review.objects.get()
        self.assertEqual(self.client.get(reverse('reviews:edit', args=[review.pk])).status_code, 200)
        response = self.client.post(reverse('reviews:edit', args=[review.pk]), {'rating': '2'})
        self.assertEqual(response.status_code, 302)
        delete_url = reverse('reviews:delete', args=[review.pk])
        self.assertContains(self.client.get(delete_url), 'Delete your review?')
        self.assertTrue(Review.objects.filter(pk=review.pk).exists())
        self.assertEqual(self.client.post(delete_url).status_code, 302)
        self.assertFalse(Review.objects.exists())

    def test_delete_ajax_and_resubmit(self):
        review = self.saved()
        response = self.client.post(reverse('reviews:delete', args=[review.pk]), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Submit review', response.json()['html'])
        self.assertFalse(Review.objects.exists())
        self.assertEqual(self.submit().status_code, 201)

    def test_invalid_fields_do_not_save(self):
        for data in [{}, {'rating': '0'}, {'rating': '6'}, {'rating': 'abc'},
                     {'rating': '5', 'comment': 'a' * 501}, {'rating': '5', 'tags': ['Forged']}]:
            with self.subTest(data=data):
                response = self.submit(data)
                self.assertEqual(response.status_code, 400)
                self.assertIn('review-errors', response.json()['html'])
                self.assertFalse(Review.objects.exists())

    def test_duplicate_submission_and_invalid_edit_keep_original(self):
        review = self.saved()
        self.assertEqual(self.submit().status_code, 400)
        response = self.client.post(reverse('reviews:edit', args=[review.pk]), {'rating': 9}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 400)
        review.refresh_from_db()
        self.assertEqual(review.rating, 5)
        self.assertEqual(Review.objects.count(), 1)

    def test_other_accounts_cannot_write_or_delete(self):
        review = self.saved()
        for user in [self.other, self.seller]:
            self.client.force_login(user)
            self.assertEqual(self.submit().status_code, 404)
            for action in ['edit', 'delete']:
                url = reverse(f'reviews:{action}', args=[review.pk])
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.client.post(url, {'rating': 1}).status_code, 404)
        review.refresh_from_db()
        self.assertEqual(review.rating, 5)

    def test_ids_from_browser_cannot_override_owner_or_product(self):
        response = self.submit({'rating': 5, 'reviewer': self.other.pk, 'listing': 9999, 'transaction': 9999})
        self.assertEqual(response.status_code, 201)
        review = Review.objects.get()
        self.assertEqual((review.reviewer_id, review.listing_id, review.transaction_id),
                         (self.buyer.pk, self.listing.pk, self.order.pk))

    def test_eligibility_enforced_on_post(self):
        for status in ['ongoing', 'delivered', 'cancelled']:
            self.order.status = status
            self.order.save()
            self.assertEqual(self.submit().status_code, 400)
        self.order.status = 'completed'
        self.order.listing = None
        self.order.save()
        self.assertEqual(self.submit().status_code, 400)
        self.order.listing = self.listing
        self.order.save()
        self.listing.seller = self.buyer
        self.listing.save()
        self.assertEqual(self.submit().status_code, 400)
        self.assertFalse(Review.objects.exists())

    def test_anonymous_access_and_safe_methods(self):
        self.assertEqual(self.client.get(self.create_url()).status_code, 405)
        self.client.logout()
        self.assertEqual(self.submit().status_code, 302)
        self.assertEqual(self.client.get(reverse('reviews:list')).status_code, 302)

    def test_csrf_required_for_all_mutations(self):
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.buyer)
        self.assertEqual(secure.post(self.create_url(), {'rating': 5}).status_code, 403)
        secure.get(reverse('main:transaction_review', args=[self.order.pk]))
        token = secure.cookies['csrftoken'].value
        response = secure.post(self.create_url(), {'rating': 5, 'csrfmiddlewaretoken': token})
        self.assertEqual(response.status_code, 302)
        review = Review.objects.get()
        for action in ['edit', 'delete']:
            self.assertEqual(secure.post(reverse(f'reviews:{action}', args=[review.pk]), {'rating': 1}).status_code, 403)

    def test_review_text_is_escaped_in_html_and_json_fragments(self):
        payload = '<script>alert(1)</script>'
        response = self.submit({'rating': 5, 'comment': payload})
        self.assertNotIn(payload, response.json()['html'])
        self.assertIn('&lt;script&gt;', response.json()['html'])
        response = self.client.get(reverse('reviews:list'))
        self.assertNotContains(response, payload)
        self.assertContains(response, '&lt;script&gt;')

    def test_database_filters_and_private_received_scope(self):
        self.saved()
        listing = Listing.objects.create(seller=self.other, name='Other item', price=20)
        order = TransactionHistory.objects.create(buyer=self.buyer, listing=listing, item_name='Other item', price=20, status='completed')
        Review.objects.create(transaction=order, listing=listing, reviewer=self.buyer, rating=2, comment='Small')
        url = reverse('reviews:list')
        response = self.client.get(url, {'rating': '5', 'q': 'denim'})
        self.assertEqual(response.context['page_obj'].paginator.count, 1)
        self.assertEqual(response.context['average'], 5)
        self.assertNotContains(response, 'Other item')
        self.assertEqual(self.client.get(url, {'sort': 'highest'}).context['page_obj'][0].rating, 5)
        self.assertContains(self.client.get(url, {'q': 'missing'}), 'No reviews match')
        response = self.client.get(url, {'rating': 'bad'})
        self.assertEqual(response.context['page_obj'].paginator.count, 0)
        self.client.force_login(self.seller)
        response = self.client.get(url, {'scope': 'received'})
        self.assertContains(response, 'Purchased denim')
        self.assertNotContains(response, 'Other item')
        self.assertNotContains(response, self.buyer.email)
        self.assertNotContains(response, 'Edit review')
        self.assertEqual(self.client.get(url).context['page_obj'].paginator.count, 0)

    def test_ajax_pagination_and_filter_errors(self):
        for i in range(11):
            order = TransactionHistory.objects.create(buyer=self.buyer, listing=self.listing, item_name=f'Product {i}', price=100, status='completed')
            Review.objects.create(transaction=order, listing=self.listing, reviewer=self.buyer, rating=4)
        response = self.client.get(reverse('reviews:list'), {'rating': '4', 'page': 2}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Page 2 of 2', response.json()['html'])
        self.assertIn('rating=4', response.json()['html'])
        response = self.client.get(reverse('reviews:list'), {'scope': 'arbitrary'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertIn('review-errors', response.json()['html'])
