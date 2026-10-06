from unittest.mock import patch
from urllib.parse import parse_qs, urlparse
from xml.etree.ElementTree import ParseError

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from requests import Response, Timeout

from main.models import SSOIdentity
from main.sso import cas_client

User = get_user_model()
PASSWORD = 'Clothing-Cycle!37-Market'


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
