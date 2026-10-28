from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from listings.models import Listing
from main.models import SSOIdentity

User = get_user_model()


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
                response = self.client.get(url)
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
