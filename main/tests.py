from unittest.mock import patch
from urllib.parse import parse_qs, urlparse
from xml.etree.ElementTree import ParseError

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils.html import escape
from requests import Response, Timeout

from listings.models import Listing
from main.models import SSOIdentity
from main.sso import cas_client

User = get_user_model()
PASSWORD = 'Clothing-Cycle!37-Market'


class CatalogTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user(username='catalog-seller', email='private-catalog@example.test',
                                             first_name='Catalog', last_name='Seller')
        cls.other = User.objects.create_user(username='catalog-other', first_name='Other', last_name='Seller')

    def test_empty_marketplace_has_no_dummy_cards(self):
        response = self.client.get(reverse('main:show_main'))
        self.assertQuerySetEqual(response.context['catalog_items'], [])
        self.assertContains(response, 'No items listed yet')
        self.assertContains(response, 'List the first item')
        self.assertNotContains(response, 'data-catalog-name=')
        self.assertNotContains(response, 'catalog-socks.png')
        self.assertNotContains(response, 'Item Name')

    def test_catalog_displays_all_sellers_newest_first_with_detail_links(self):
        first = Listing.objects.create(seller=self.seller, name='Wool coat', price=150000,
                                        category='outerwear', condition='like_new', size='L',
                                        image_url='https://example.com/coat.jpg', location='Bandung')
        second = Listing.objects.create(seller=self.other, name='Silk scarf', price='1234.50')
        response = self.client.get(reverse('main:show_main'))
        self.assertQuerySetEqual(response.context['catalog_items'], [second, first])
        for text in ('Wool coat', 'Silk scarf', 'Rp150.000', 'Rp1.234,50', 'Outerwear', 'Like new',
                     'Bandung', 'data-category="outerwear"', first.image_url):
            self.assertContains(response, text)
        for item in (first, second):
            self.assertContains(response, 'href="' + reverse('listings:detail', args=[item.pk]) + '"')
        self.assertNotContains(response, 'No items listed yet')

    def test_catalog_keeps_contact_private_for_guests_and_members(self):
        listing = Listing.objects.create(seller=self.seller, name='Private-contact coat',
                                          contact_email='published-catalog@example.test')
        for user in (None, self.other, self.seller):
            with self.subTest(user=user):
                if user:
                    self.client.force_login(user)
                response = self.client.get(reverse('main:show_main'))
                self.assertContains(response, listing.name)
                if user != self.seller:
                    self.assertNotContains(response, self.seller.email)
                self.assertNotContains(response, listing.contact_email)
                self.assertIn('no-store', response.headers['Cache-Control'])

    def test_unavailable_and_legacy_items_have_honest_metadata(self):
        Listing.objects.create(seller=self.seller, name='Legacy item')
        Listing.objects.create(seller=self.seller, name='Sold item', price=50000, stock=0)
        response = self.client.get(reverse('main:show_main'))
        for text in ('Price not set', 'Currently unavailable', 'Sold out', 'Not specified',
                     'Location not provided', 'item-photo-placeholder.png', 'data-category=""'):
            self.assertContains(response, text)
        for text in ('Rp100.000', 'Gray socks', 'Like New', 'Depok, Indonesia'):
            self.assertNotContains(response, text)

    def test_catalog_reflects_create_edit_and_delete_without_exposing_management(self):
        viewer = Client()
        self.client.force_login(self.seller)
        response = self.client.post(reverse('listings:create'), {
            'name': 'New catalog shirt', 'price': '75.000', 'category': 'tops', 'condition': 'good',
            'size': 'Medium', 'stock': 2,
        })
        listing = Listing.objects.get(name='New catalog shirt')
        self.assertRedirects(response, reverse('listings:detail', args=[listing.pk]), fetch_redirect_response=False)
        response = viewer.get(reverse('main:show_main'))
        self.assertContains(response, listing.name)
        self.assertContains(response, 'Rp75.000')
        self.assertNotContains(response, reverse('listings:update', args=[listing.pk]))
        response = self.client.post(reverse('listings:update', args=[listing.pk]), {
            'name': 'Renamed catalog shirt', 'price': '65.000', 'category': 'bottoms', 'stock': 0,
        })
        self.assertEqual(response.status_code, 302)
        response = viewer.get(reverse('main:show_main'))
        for text in ('Renamed catalog shirt', 'Rp65.000', 'data-category="bottoms"', 'Sold out'):
            self.assertContains(response, text)
        self.assertNotContains(response, 'New catalog shirt')
        response = self.client.post(reverse('listings:delete', args=[listing.pk]))
        self.assertRedirects(response, reverse('listings:mine'), fetch_redirect_response=False)
        response = viewer.get(reverse('main:show_main'))
        self.assertNotContains(response, 'Renamed catalog shirt')
        self.assertContains(response, 'No items listed yet')

    def test_legacy_index_redirects_and_detail_returns_to_catalog(self):
        self.assertRedirects(self.client.get(reverse('listings:index')),
                             reverse('main:show_main') + '#catalog')
        self.assertEqual(self.client.post(reverse('listings:index')).status_code, 405)
        listing = Listing.objects.create(seller=self.seller, name='Browse back test')
        response = self.client.get(reverse('listings:detail', args=[listing.pk]))
        self.assertContains(response, 'href="' + reverse('main:show_main') + '#catalog"')

    @override_settings(SSO_ENABLED=False)
    def test_catalog_preserves_login_destination_and_auth_notice(self):
        session = self.client.session
        session['auth_notice'] = 'Test authentication notice'
        session.save()
        response = self.client.get(reverse('main:show_main'), {
            'login': '1', 'next': reverse('listings:create'),
        })
        self.assertEqual(response.context['auth_next'], reverse('listings:create'))
        self.assertEqual(response.context['auth_notice'], 'Test authentication notice')
        self.assertFalse(response.context['sso_enabled'])
        self.assertContains(response, 'No items listed yet')


@override_settings(SSO_SERVER_URL='https://sso.ui.ac.id/cas2/', SSO_CAS_VERSION='2', SSO_TIMEOUT=8)
class CASClientTests(TestCase):
    @patch('requests.Session.request')
    def test_transport_and_real_cas_xml_parser(self, mocked):
        response = Response()
        response.status_code = 200
        response._content = b'''<cas:serviceResponse xmlns:cas="http://www.yale.edu/tp/cas">
          <cas:authenticationSuccess><cas:user>test-subject</cas:user>
          <cas:attributes><cas:mail>test@example.com</cas:mail></cas:attributes>
          </cas:authenticationSuccess></cas:serviceResponse>'''
        mocked.return_value = response
        service = 'http://127.0.0.1:8000/sso/callback/?state=test-state'
        client = cas_client(service)
        self.assertEqual(client.session.headers['User-Agent'], 'WearBack/1.0')
        subject, attributes, _ = client.verify_ticket('ST-test')
        self.assertEqual(subject, 'test-subject')
        self.assertEqual(attributes['mail'], 'test@example.com')
        args, kwargs = mocked.call_args
        self.assertEqual(args, ('GET', 'https://sso.ui.ac.id/cas2/serviceValidate'))
        self.assertEqual(kwargs['params']['service'], service)
        self.assertEqual(kwargs['params']['ticket'], 'ST-test')
        self.assertTrue(kwargs['verify'])
        self.assertEqual(kwargs['timeout'], 8)
        self.assertFalse(kwargs['allow_redirects'])

    @patch('requests.Session.request')
    def test_invalid_cas_ticket_is_not_authenticated(self, mocked):
        response = Response()
        response.status_code = 200
        response._content = b'''<cas:serviceResponse xmlns:cas="http://www.yale.edu/tp/cas">
          <cas:authenticationFailure code="INVALID_TICKET">Invalid ticket</cas:authenticationFailure>
          </cas:serviceResponse>'''
        mocked.return_value = response
        subject, _, _ = cas_client('http://127.0.0.1:8000/sso/callback/?state=test').verify_ticket('ST-test')
        self.assertIsNone(subject)


class PasswordAuthTests(TestCase):
    def payload(self, **changes):
        return dict(first_name='Demo', last_name='User', email='demo@example.com',
                    password=PASSWORD, password_confirm=PASSWORD, **changes)

    def test_registration_hashes_password_and_starts_session(self):
        data = self.payload()
        data['email'] = 'Demo@Example.COM'
        response = self.client.post(reverse('main:register'), data)
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email='demo@example.com')
        self.assertTrue(user.check_password(PASSWORD))
        self.assertNotEqual(user.password, PASSWORD)
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)
        page = self.client.get(reverse('main:auction'))
        self.assertContains(page, 'Log out')
        self.assertContains(page, 'Demo')

    def test_duplicate_email_case_insensitive(self):
        User.objects.create_user(username='existing', email='demo@example.com', password=PASSWORD)
        data = self.payload()
        data['email'] = 'DEMO@example.com'
        response = self.client.post(reverse('main:register'), data)
        self.assertEqual(response.status_code, 400)
        self.assertIn('email', response.json()['errors'])
        self.assertEqual(User.objects.count(), 1)

    def test_database_enforces_email_uniqueness(self):
        User.objects.create_user(username='one', email='demo@example.com')
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(username='two', email='DEMO@example.com')

    def test_weak_password_and_confirmation(self):
        data = self.payload()
        data.update(password='123', password_confirm='other')
        response = self.client.post(reverse('main:register'), data)
        self.assertEqual(response.status_code, 400)
        self.assertIn('password', response.json()['errors'])
        self.assertIn('password_confirm', response.json()['errors'])
        self.assertFalse(User.objects.exists())

    def test_email_login_and_logout(self):
        user = User.objects.create_user(username='internal', email='demo@example.com', password=PASSWORD)
        response = self.client.post(reverse('main:login'), {'email': 'DEMO@example.com', 'password': PASSWORD, 'next': '/auction/'})
        self.assertEqual(response.json()['redirect'], '/auction/')
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)
        self.assertEqual(self.client.get(reverse('main:logout')).status_code, 405)
        self.assertEqual(self.client.post(reverse('main:logout'), {'next': '/auction/'}).url, '/auction/')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_bad_password_inactive_and_unusable_password(self):
        user = User.objects.create_user(username='internal', email='demo@example.com', password=PASSWORD)
        for password, inactive in [('wrong', False), (PASSWORD, True)]:
            user.is_active = not inactive
            user.save()
            response = self.client.post(reverse('main:login'), {'email': user.email, 'password': password})
            self.assertEqual(response.status_code, 400)
            self.assertNotIn('_auth_user_id', self.client.session)
        user.is_active = True
        user.set_unusable_password()
        user.save()
        self.assertEqual(self.client.post(reverse('main:login'), {'email': user.email, 'password': PASSWORD}).status_code, 400)

    def test_login_never_accepts_external_next(self):
        User.objects.create_user(username='internal', email='demo@example.com', password=PASSWORD)
        response = self.client.post(reverse('main:login'), {'email': 'demo@example.com', 'password': PASSWORD, 'next': 'https://evil.example/'})
        self.assertEqual(response.json()['redirect'], '/')

    def test_csrf_required_for_registration_login_logout_and_profile(self):
        client = Client(enforce_csrf_checks=True)
        for name in ['register', 'login', 'logout', 'profile', 'sso_link']:
            self.assertEqual(client.post(reverse('main:' + name), self.payload()).status_code, 403)

    @override_settings(AUTH_RATE_LIMIT=2)
    def test_rate_limit(self):
        for _ in range(2):
            self.assertEqual(self.client.post(reverse('main:login'), {'email': 'demo@example.com', 'password': 'wrong'}).status_code, 400)
        response = self.client.post(reverse('main:login'), {'email': 'demo@example.com', 'password': 'wrong'})
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response)

    def test_profile_requires_login_and_preserves_user_identity(self):
        self.assertEqual(self.client.post(reverse('main:profile'), self.payload()).status_code, 401)
        user = User.objects.create_user(username='internal')
        self.client.force_login(user)
        response = self.client.post(reverse('main:profile'), self.payload())
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.email, 'demo@example.com')
        self.assertEqual(user.username, 'internal')
        self.assertFalse(user.has_usable_password())

    def test_existing_username_admin_login_remains_supported(self):
        user = User.objects.create_superuser(username='admin', email='admin@example.com', password=PASSWORD)
        self.assertTrue(self.client.login(username='admin', password=PASSWORD))
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 200)


@override_settings(SSO_ENABLED=True, SSO_SERVER_URL='https://sso.ui.ac.id/cas2/',
                   SSO_CAS_VERSION='2', SSO_SERVICE_URL='', PRODUCTION=False)
class SSOTests(TestCase):
    def start(self, client=None, link=False):
        client = client or self.client
        if link:
            response = client.post(reverse('main:sso_link'), {'next': '/auction/'})
        else:
            response = client.get(reverse('main:sso_login'), {'next': '/auction/'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('https://sso.ui.ac.id/cas2/login?'))
        return client.session['sso_attempt']

    def callback(self, attempt, ticket='ST-demo', **kwargs):
        return self.client.get(reverse('main:sso_callback'), {'state': attempt['state'], 'ticket': ticket}, **kwargs)

    @patch('main.views.cas_client')
    def test_first_and_repeat_sso_login(self, mocked):
        mocked.return_value.get_login_url.return_value = 'https://sso.ui.ac.id/cas2/login?service=demo'
        mocked.return_value.verify_ticket.return_value = ('ui-subject', {'mail': 'ui@example.com', 'givenName': 'Demo', 'sn': 'User'}, None)
        attempt = self.start()
        response = self.callback(attempt)
        self.assertEqual(response.url, '/auction/')
        user = User.objects.get(sso_identities__subject='ui-subject')
        self.assertFalse(user.has_usable_password())
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)
        self.client.logout()
        self.callback(self.start())
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(SSOIdentity.objects.count(), 1)
        self.assertEqual(mocked.return_value.verify_ticket.call_count, 2)

    def test_redirect_uses_exact_callback_and_session_state(self):
        attempt = self.start()
        query = parse_qs(urlparse(attempt['service']).query)
        self.assertEqual(query['state'][0], attempt['state'])
        self.assertEqual(urlparse(attempt['service']).path, reverse('main:sso_callback'))

    @patch('main.views.cas_client')
    def test_unsolicited_or_mismatched_callback_never_verifies(self, mocked):
        self.client.get(reverse('main:sso_callback'), {'ticket': 'ST-attack', 'state': 'attack'})
        mocked.assert_not_called()
        mocked.return_value.get_login_url.return_value = 'https://sso.ui.ac.id/cas2/login?service=demo'
        self.start()
        self.client.get(reverse('main:sso_callback'), {'ticket': 'ST-attack', 'state': 'wrong'})
        mocked.return_value.verify_ticket.assert_not_called()
        self.assertFalse(User.objects.exists())

    @patch('main.views.cas_client')
    def test_non_ascii_state_is_rejected_without_verification(self, mocked):
        mocked.return_value.get_login_url.return_value = 'https://sso.ui.ac.id/cas2/login?service=demo'
        self.start()
        response = self.client.get(reverse('main:sso_callback'), {'ticket': 'ST-attack', 'state': 'é'})
        self.assertEqual(response.status_code, 302)
        mocked.return_value.verify_ticket.assert_not_called()
        self.assertNotIn('sso_attempt', self.client.session)

    @patch('main.views.cas_client')
    def test_expired_replayed_and_cancelled_flows(self, mocked):
        mocked.return_value.get_login_url.return_value = 'https://sso.ui.ac.id/cas2/login?service=demo'
        attempt = self.start()
        session = self.client.session
        session['sso_attempt'] = dict(attempt, expires=0)
        session.save()
        self.callback(attempt)
        mocked.return_value.verify_ticket.assert_not_called()
        attempt = self.start()
        self.callback(attempt, ticket='')
        self.callback(attempt)
        mocked.return_value.verify_ticket.assert_not_called()

    @patch('main.views.cas_client')
    def test_network_failure_and_invalid_ticket_return_popup_error(self, mocked):
        mocked.return_value.get_login_url.return_value = 'https://sso.ui.ac.id/cas2/login?service=demo'
        for result in [Timeout('network'), ParseError('malformed response'), (None, None, None)]:
            if isinstance(result, Exception):
                mocked.return_value.verify_ticket.side_effect = result
            else:
                mocked.return_value.verify_ticket.side_effect = None
                mocked.return_value.verify_ticket.return_value = result
            response = self.callback(self.start())
            page = self.client.get(response.url)
            self.assertEqual(page.context['auth_initial_mode'], 'login')
            self.assertTrue(page.context['auth_notice'])
            self.assertFalse(User.objects.exists())

    @patch('main.views.cas_client')
    def test_email_collision_does_not_link_existing_account(self, mocked):
        local = User.objects.create_user(username='local', email='same@example.com', password=PASSWORD)
        mocked.return_value.get_login_url.return_value = 'https://sso.ui.ac.id/cas2/login?service=demo'
        mocked.return_value.verify_ticket.return_value = ('ui-subject', {'mail': local.email}, None)
        response = self.callback(self.start())
        self.assertFalse(SSOIdentity.objects.exists())
        self.assertEqual(User.objects.count(), 1)
        self.assertNotIn('_auth_user_id', self.client.session)
        page = self.client.get(response.url)
        self.assertEqual(page.context['auth_initial_mode'], 'login')
        self.assertIn('SSO email is already registered', page.context['auth_notice'])

    @patch('main.views.cas_client')
    def test_existing_sso_account_refreshes_email_and_does_not_prompt(self, mocked):
        user = User.objects.create_user(username='sso-existing')
        SSOIdentity.objects.create(subject='ui-subject', user=user)
        mocked.return_value.get_login_url.return_value = 'https://sso.ui.ac.id/cas2/login?service=demo'
        mocked.return_value.verify_ticket.return_value = ('ui-subject', {'EmailAddress': ['UI@Example.com'], 'nama': 'Demo'}, None)
        response = self.callback(self.start())
        user.refresh_from_db()
        self.assertEqual(user.email, 'ui@example.com')
        self.assertEqual(user.first_name, 'Demo')
        self.assertEqual(user.last_name, '')
        self.assertEqual(self.client.get(response.url).context['auth_initial_mode'], '')

    @patch('main.views.cas_client')
    def test_missing_provider_email_does_not_force_manual_entry(self, mocked):
        mocked.return_value.get_login_url.return_value = 'https://sso.ui.ac.id/cas2/login?service=demo'
        mocked.return_value.verify_ticket.return_value = ('ui-subject', {'nama': 'Demo User'}, None)
        response = self.callback(self.start())
        self.assertIsNone(User.objects.get(sso_identities__subject='ui-subject').email)
        self.assertEqual(self.client.get(response.url).context['auth_initial_mode'], '')

    @patch('main.views.cas_client')
    def test_authenticated_explicit_link_and_account_collision(self, mocked):
        owner = User.objects.create_user(username='owner', email='owner@example.com', password=PASSWORD)
        self.client.force_login(owner)
        mocked.return_value.get_login_url.return_value = 'https://sso.ui.ac.id/cas2/login?service=demo'
        mocked.return_value.verify_ticket.return_value = ('ui-subject', {}, None)
        self.callback(self.start(link=True))
        self.assertEqual(SSOIdentity.objects.get(subject='ui-subject').user_id, owner.pk)
        other = User.objects.create_user(username='other', email='other@example.com', password=PASSWORD)
        self.client.force_login(other)
        self.callback(self.start(link=True))
        self.assertEqual(SSOIdentity.objects.get(subject='ui-subject').user_id, owner.pk)
        self.assertEqual(int(self.client.session['_auth_user_id']), other.pk)
        self.assertIn('already linked', self.client.session['auth_notice'])

    @patch('main.views.cas_client')
    def test_link_requires_same_authenticated_session(self, mocked):
        self.assertNotIn('sso_attempt', self.client.session)
        self.client.post(reverse('main:sso_link'))
        mocked.assert_not_called()
        user = User.objects.create_user(username='owner')
        self.client.force_login(user)
        mocked.return_value.get_login_url.return_value = 'https://sso.ui.ac.id/cas2/login?service=demo'
        attempt = self.start(link=True)
        session = self.client.session
        del session['_auth_user_id']
        session.save()
        self.callback(attempt)
        mocked.return_value.verify_ticket.assert_not_called()

    @patch('main.views.cas_client')
    def test_inactive_sso_account_cannot_log_in(self, mocked):
        user = User.objects.create_user(username='inactive', is_active=False)
        SSOIdentity.objects.create(subject='ui-subject', user=user)
        mocked.return_value.get_login_url.return_value = 'https://sso.ui.ac.id/cas2/login?service=demo'
        mocked.return_value.verify_ticket.return_value = ('ui-subject', {}, None)
        self.callback(self.start())
        self.assertNotIn('_auth_user_id', self.client.session)

    @override_settings(SSO_ENABLED=False)
    def test_disabled_sso_is_hidden_and_returns_notice(self):
        self.assertNotContains(self.client.get('/'), 'Continue with SSO UI')
        response = self.client.get(reverse('main:sso_login'))
        self.assertIn('unavailable', self.client.session['auth_notice'])
        self.assertEqual(response.url, '/')

    @override_settings(SSO_SERVER_URL='http://sso.ui.ac.id/cas2/')
    def test_insecure_provider_configuration_is_rejected(self):
        self.client.get(reverse('main:sso_login'))
        self.assertNotIn('sso_attempt', self.client.session)
        self.assertIn('configuration', self.client.session['auth_notice'])

    def test_sso_external_return_url_is_rejected(self):
        self.client.get(reverse('main:sso_login'), {'next': 'https://evil.example/'})
        self.assertEqual(self.client.session['sso_attempt']['next'], '/')

    @override_settings(SSO_SERVICE_URL='https://wearback.example/sso/callback/', PRODUCTION=True)
    def test_configured_production_callback(self):
        response = self.client.get(reverse('main:sso_login'), secure=True)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.client.session['sso_attempt']['service'].startswith('https://wearback.example/sso/callback/?state='))


@override_settings(SSO_ENABLED=True, SSO_SERVER_URL='https://sso.ui.ac.id/cas2/',
                   SSO_CAS_VERSION='2', SSO_SERVICE_URL='', PRODUCTION=False)
class AuthReturnTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='return-member', email='return@example.com',
                                            first_name='Return', last_name='Member', password=PASSWORD)

    def test_auth_entry_preserves_listing_destination_and_escapes_dialog_attribute(self):
        destination = reverse('listings:create') + '?source=menu&note="example"#form'
        for mode in ('login', 'register'):
            with self.subTest(mode=mode):
                response = self.client.get(reverse('main:' + mode), {'next': destination}, follow=True)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context['auth_next'], destination)
                self.assertEqual(parse_qs(urlparse(response.redirect_chain[-1][0]).query)[mode], ['1'])
                self.assertContains(response, 'data-next="' + escape(destination) + '"')

    def test_plain_auth_entry_still_opens_the_expected_popup(self):
        for mode in ('login', 'register'):
            with self.subTest(mode=mode):
                response = self.client.get(reverse('main:' + mode))
                self.assertEqual(response.url, '/?' + mode + '=1')
                self.assertEqual(self.client.get(response.url).context['auth_next'], '')

    def test_external_auth_entry_and_direct_popup_destinations_are_rejected(self):
        for unsafe in ('https://evil.example/', '//evil.example/', 'javascript:alert(1)'):
            for mode in ('login', 'register'):
                with self.subTest(unsafe=unsafe, mode=mode):
                    response = self.client.get(reverse('main:' + mode), {'next': unsafe}, follow=True)
                    self.assertEqual(response.context['auth_next'], '/')
                    self.assertContains(response, 'data-next="/"')
                    self.assertNotContains(response, unsafe)
                    response = self.client.get('/', {mode: '1', 'next': unsafe})
                    self.assertEqual(response.context['auth_next'], '/')

    def test_ordinary_pages_do_not_override_login_destination_from_unrelated_query(self):
        response = self.client.get('/', {'next': reverse('listings:create')})
        self.assertEqual(response.context['auth_next'], '')

    def test_guest_can_return_to_create_page_after_password_login(self):
        destination = reverse('listings:create')
        response = self.client.get(destination, follow=True)
        self.assertEqual(response.context['auth_next'], destination)
        response = self.client.post(reverse('main:login'), {
            'email': self.user.email, 'password': PASSWORD, 'next': response.context['auth_next'],
        })
        self.assertEqual(response.json()['redirect'], destination)
        self.assertContains(self.client.get(response.json()['redirect']), 'Create item')

    def test_registration_can_return_to_create_page(self):
        destination = reverse('listings:create')
        page = self.client.get(reverse('main:register'), {'next': destination}, follow=True)
        response = self.client.post(reverse('main:register'), {
            'first_name': 'New', 'last_name': 'Member', 'email': 'new-return@example.com',
            'password': PASSWORD, 'password_confirm': PASSWORD, 'next': page.context['auth_next'],
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['redirect'], destination)
        self.assertContains(self.client.get(destination), 'Create item')

    def test_registration_rejects_an_external_return_destination(self):
        response = self.client.post(reverse('main:register'), {
            'first_name': 'New', 'last_name': 'Member', 'email': 'unsafe-return@example.com',
            'password': PASSWORD, 'password_confirm': PASSWORD, 'next': 'https://evil.example/',
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['redirect'], '/')

    @patch('main.views.cas_client')
    def test_sso_from_popup_returns_to_create_page(self, mocked):
        destination = reverse('listings:create')
        page = self.client.get(destination, follow=True)
        mocked.return_value.get_login_url.return_value = 'https://sso.ui.ac.id/cas2/login?service=demo'
        mocked.return_value.verify_ticket.return_value = (
            'return-sso-member', {'mail': 'return-sso@example.com', 'givenName': 'SSO', 'sn': 'Member'}, None,
        )
        self.client.get(reverse('main:sso_login'), {'next': page.context['auth_next']})
        attempt = self.client.session['sso_attempt']
        self.assertEqual(attempt['next'], destination)
        response = self.client.get(reverse('main:sso_callback'), {'state': attempt['state'], 'ticket': 'ST-test'})
        self.assertRedirects(response, destination)
        self.assertContains(self.client.get(destination), 'Create item')

    @patch('main.views.cas_client')
    def test_failed_sso_retains_notice_and_destination_through_login_redirect(self, mocked):
        destination = reverse('listings:create')
        mocked.return_value.get_login_url.return_value = 'https://sso.ui.ac.id/cas2/login?service=demo'
        mocked.return_value.verify_ticket.side_effect = Timeout('network')
        self.client.get(reverse('main:sso_login'), {'next': destination})
        attempt = self.client.session['sso_attempt']
        response = self.client.get(reverse('main:sso_callback'), {
            'state': attempt['state'], 'ticket': 'ST-test',
        }, follow=True)
        self.assertEqual(response.context['auth_next'], destination)
        self.assertEqual(response.context['auth_initial_mode'], 'login')
        self.assertIn('could not complete', response.context['auth_notice'])
