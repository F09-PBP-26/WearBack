import secrets
import time
from urllib.parse import urlencode, urlparse
from xml.etree.ElementTree import ParseError

from cas import CASError
from django.conf import settings
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.crypto import constant_time_compare
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from requests import RequestException

from main.auth_utils import throttled
from main.forms import LoginForm, ProfileForm, RegisterForm
from main.sso import cas_client, resolve_identity


def safe_next(request, value):
    if value and url_has_allowed_host_and_scheme(value, {request.get_host()}, require_https=request.is_secure()):
        return value
    return reverse('main:show_main')


def page_context(request):
    context = {'sso_enabled': settings.SSO_ENABLED,
               'auth_notice': request.session.pop('auth_notice', ''),
               'auth_initial_mode': request.session.pop('auth_mode', '')}
    if request.user.is_authenticated:
        context['sso_linked'] = request.user.sso_identities.filter(provider='ui').exists()
        if (not context['sso_linked']
                and (not request.user.email or not request.user.first_name or not request.user.last_name)):
            context['auth_initial_mode'] = 'profile'
    return context


@never_cache
def show_main(request):
    return render(request, 'index.html', page_context(request))


@never_cache
def auction(request):
    return render(request, 'auction.html', page_context(request))


def form_errors(form):
    return {field: [error['message'] for error in errors] for field, errors in form.errors.get_json_data().items()}


def too_many():
    response = JsonResponse({'errors': {'__all__': ['Too many attempts. Please try again in ten minutes.']}}, status=429)
    response['Retry-After'] = str(settings.AUTH_RATE_WINDOW)
    return response


@never_cache
@sensitive_post_parameters('password')
@require_http_methods(['GET', 'POST'])
def login(request):
    if request.method == 'GET':
        return redirect(reverse('main:show_main') + '?login=1')
    if throttled(request, 'login', request.POST.get('email', '')):
        return too_many()
    form = LoginForm(request.POST, request=request)
    if not form.is_valid():
        return JsonResponse({'errors': form_errors(form)}, status=400)
    auth_login(request, form.user)
    return JsonResponse({'redirect': safe_next(request, request.POST.get('next'))})


@never_cache
@sensitive_post_parameters('password', 'password_confirm')
@require_http_methods(['GET', 'POST'])
def register(request):
    if request.method == 'GET':
        return redirect(reverse('main:show_main') + '?register=1')
    if throttled(request, 'register'):
        return too_many()
    form = RegisterForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'errors': form_errors(form)}, status=400)
    try:
        with transaction.atomic():
            user = form.save()
    except IntegrityError:
        return JsonResponse({'errors': {'email': ['This email is already registered.']}}, status=400)
    auth_login(request, user, backend='main.backends.EmailBackend')
    return JsonResponse({'redirect': safe_next(request, request.POST.get('next'))}, status=201)


@require_POST
def logout(request):
    destination = safe_next(request, request.POST.get('next'))
    auth_logout(request)
    return redirect(destination)


@never_cache
@require_POST
def profile(request):
    if not request.user.is_authenticated:
        return JsonResponse({'errors': {'__all__': ['Please log in first.']}}, status=401)
    form = ProfileForm(request.POST, instance=request.user)
    if not form.is_valid():
        return JsonResponse({'errors': form_errors(form)}, status=400)
    try:
        with transaction.atomic():
            form.save()
    except IntegrityError:
        return JsonResponse({'errors': {'email': ['This email is already registered.']}}, status=400)
    return JsonResponse({'redirect': safe_next(request, request.POST.get('next'))})


def sso_error(request, message, destination=None):
    request.session['auth_notice'] = message
    request.session['auth_mode'] = 'login'
    return redirect(safe_next(request, destination))


def begin_sso(request, link=False):
    destination = safe_next(request, request.GET.get('next') or request.POST.get('next'))
    if not settings.SSO_ENABLED:
        return sso_error(request, 'SSO UI is currently unavailable.', destination)
    if throttled(request, 'sso'):
        return sso_error(request, 'Too many SSO attempts. Please try again in ten minutes.', destination)
    state = secrets.token_urlsafe(32)
    service = settings.SSO_SERVICE_URL or request.build_absolute_uri(reverse('main:sso_callback'))
    parsed = urlparse(service)
    if (parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.query or parsed.fragment
            or parsed.path != reverse('main:sso_callback') or (settings.PRODUCTION and parsed.scheme != 'https')):
        return sso_error(request, 'SSO callback configuration needs attention.', destination)
    service += '?' + urlencode({'state': state})
    try:
        url = cas_client(service).get_login_url()
    except ImproperlyConfigured:
        return sso_error(request, 'SSO server configuration needs attention.', destination)
    request.session['sso_attempt'] = {'state': state, 'service': service, 'next': destination,
                                      'expires': time.time() + 600,
                                      'link_user': request.user.pk if link else None}
    return redirect(url)


@never_cache
@require_GET
def sso_login(request):
    return begin_sso(request)


@never_cache
@require_POST
def sso_link(request):
    if not request.user.is_authenticated:
        return sso_error(request, 'Log in to your WearBack account before linking SSO UI.')
    return begin_sso(request, link=True)


@never_cache
@require_GET
def sso_callback(request):
    attempt = request.session.pop('sso_attempt', None)
    if not settings.SSO_ENABLED:
        return sso_error(request, 'SSO UI is currently unavailable.')
    if (not attempt or attempt['expires'] < time.time()
            or not constant_time_compare(attempt['state'], request.GET.get('state', ''))):
        return sso_error(request, 'Your SSO session expired. Please try again.')
    destination = attempt['next']
    ticket = request.GET.get('ticket', '')
    if not ticket.startswith('ST-') or len(ticket) > 512:
        return sso_error(request, 'SSO sign-in was cancelled or returned an invalid ticket.', destination)
    link_user = None
    if attempt['link_user']:
        if not request.user.is_authenticated or request.user.pk != attempt['link_user']:
            return sso_error(request, 'Log in again before linking SSO UI.', destination)
        link_user = request.user
    try:
        subject, attributes, _ = cas_client(attempt['service']).verify_ticket(ticket)
        if not subject:
            return sso_error(request, 'SSO could not verify your identity. Please try again.', destination)
        user = resolve_identity(subject, attributes or {}, link_user=link_user)
    except (CASError, RequestException, ImproperlyConfigured, IntegrityError, ValueError, ParseError, IndexError, AttributeError):
        return sso_error(request, 'SSO UI could not complete sign-in. Please try again.', destination)
    except ValidationError as error:
        return sso_error(request, error.messages[0], destination)
    if not user.is_active:
        return sso_error(request, 'This WearBack account is inactive.', destination)
    if not link_user:
        auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    return redirect(safe_next(request, destination))
