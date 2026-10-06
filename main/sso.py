import logging
from urllib.parse import urlparse
from uuid import uuid4

from cas import CASClient, CASError
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.validators import validate_email
from django.db import transaction
from requests import Session

from main.models import SSOIdentity, User

# The CAS library's debug output contains provider attributes and tickets.
logging.getLogger('cas').setLevel(logging.WARNING)


class CASSession(Session):
    def __init__(self):
        super().__init__()
        # UI's CAS gateway rejects the default python-requests User-Agent.
        self.headers['User-Agent'] = 'WearBack/1.0'

    def request(self, method, url, **kwargs):
        kwargs['timeout'] = settings.SSO_TIMEOUT
        kwargs['allow_redirects'] = False
        response = super().request(method, url, **kwargs)
        response.raise_for_status()
        return response


def cas_client(service_url):
    server = urlparse(settings.SSO_SERVER_URL)
    if server.scheme != 'https' or not server.netloc or settings.SSO_CAS_VERSION not in ('2', '3'):
        raise ImproperlyConfigured('Configure an HTTPS CAS server and protocol version 2 or 3.')
    return CASClient(version=settings.SSO_CAS_VERSION, server_url=settings.SSO_SERVER_URL,
                     service_url=service_url, verify_ssl_certificate=True, session=CASSession())


def attribute(attributes, *names):
    attributes = {key.lower(): value for key, value in attributes.items() if isinstance(key, str)}
    for name in names:
        value = attributes.get(name.lower())
        if isinstance(value, (list, tuple)):
            value = value[0] if value else None
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ''


def provider_profile(attributes):
    email = attribute(attributes, 'mail', 'email', 'emailAddress', 'email_address').lower()
    try:
        validate_email(email)
        if len(email) > 254:
            email = None
    except ValidationError:
        email = None
    first_name = attribute(attributes, 'givenName', 'first_name')[:150]
    last_name = attribute(attributes, 'sn', 'last_name')[:150]
    if not first_name:
        full_name = attribute(attributes, 'displayName', 'nama', 'name').split(maxsplit=1)
        if full_name:
            first_name = full_name[0][:150]
            last_name = full_name[1][:150] if len(full_name) > 1 else ''
    return {'email': email, 'first_name': first_name, 'last_name': last_name}


def sync_profile(user, profile):
    fields = []
    email = profile['email']
    if email and email != user.email:
        if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
            raise ValidationError('Your SSO email is already registered. Log in to that WearBack account to link SSO UI.')
        user.email = email
        fields.append('email')
    for field in ('first_name', 'last_name'):
        if profile[field] and profile[field] != getattr(user, field):
            setattr(user, field, profile[field])
            fields.append(field)
    if fields:
        user.save(update_fields=fields)
    return user


@transaction.atomic
def resolve_identity(subject, attributes, link_user=None):
    """Only verified CAS subjects establish identity; email never links accounts."""
    if not isinstance(subject, str) or not subject.strip() or len(subject) > 255:
        raise CASError('Invalid CAS subject')
    identity = SSOIdentity.objects.select_related('user').filter(provider='ui', subject=subject).first()
    if identity:
        if link_user and identity.user_id != link_user.pk:
            raise ValidationError('This UI identity is already linked to another WearBack account.')
        return sync_profile(identity.user, provider_profile(attributes))
    if link_user:
        if SSOIdentity.objects.filter(provider='ui', user=link_user).exists():
            raise ValidationError('Your account is already linked to a different UI identity.')
        sync_profile(link_user, provider_profile(attributes))
        SSOIdentity.objects.create(provider='ui', subject=subject, user=link_user)
        return link_user
    profile = provider_profile(attributes)
    email = profile['email']
    if email and User.objects.filter(email__iexact=email).exists():
        raise ValidationError('Your SSO email is already registered. Log in to that WearBack account to link SSO UI.')
    user = User(username='sso_' + uuid4().hex, **profile)
    user.set_unusable_password()
    user.save()
    SSOIdentity.objects.create(provider='ui', subject=subject, user=user)
    return user
