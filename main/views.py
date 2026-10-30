from datetime import timedelta
import secrets
import time
from urllib.parse import urlencode, urlparse
from xml.etree.ElementTree import ParseError

from cas import CASError
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from requests import RequestException

from listings.models import Listing
from main.auth_utils import throttled
from main.forms import LoginForm, ProfileForm, RegisterForm
from main.models import CartItem, TransactionHistory
from main.sso import cas_client, resolve_identity

from listings.models import Listing

def safe_next(request, value):
    if value and url_has_allowed_host_and_scheme(value, {request.get_host()}, require_https=request.is_secure()):
        return value
    return reverse('main:show_main')


def page_context(request):
    context = {'sso_enabled': settings.SSO_ENABLED,
               'auth_notice': request.session.pop('auth_notice', ''),
               'auth_initial_mode': request.session.pop('auth_mode', ''),
               'auth_next': ''}
    if request.GET.get('login') == '1' or request.GET.get('register') == '1':
        if request.GET.get('next'):
            context['auth_next'] = safe_next(request, request.GET['next'])
    if request.user.is_authenticated:
        context['sso_linked'] = request.user.sso_identities.filter(provider='ui').exists()
        context['profile_complete'] = bool(
            request.user.email and request.user.first_name and request.user.last_name
            and request.user.location
        )
        if (not context['sso_linked']
                and not context['profile_complete']):
            context['auth_initial_mode'] = 'profile'
    return context


@never_cache
def show_main(request):
    context = page_context(request)
    context['catalog_items'] = Listing.objects.all()
    return render(request, 'index.html', context)


@never_cache
def auction(request):
    return render(request, 'auction.html', page_context(request))


def form_errors(form):
    return {field: [error['message'] for error in errors] for field, errors in form.errors.get_json_data().items()}


def too_many():
    response = JsonResponse({'errors': {'__all__': ['Too many attempts. Please try again in ten minutes.']}}, status=429)
    response['Retry-After'] = str(settings.AUTH_RATE_WINDOW)
    return response


def auth_redirect(request, mode):
    query = {mode: '1'}
    if request.GET.get('next'):
        query['next'] = safe_next(request, request.GET['next'])
    return redirect(reverse('main:show_main') + '?' + urlencode(query))


@never_cache
@sensitive_post_parameters('password')
@require_http_methods(['GET', 'POST'])
def login(request):
    if request.method == 'GET':
        return auth_redirect(request, 'login')
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
        return auth_redirect(request, 'register')
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

# Transaction 
@login_required
@never_cache
def transaction_history(request):
    now = timezone.now()
    TransactionHistory.objects.filter(buyer=request.user, status="ongoing", payment_deadline__isnull=False, payment_deadline__lte=now).update(
            status="cancelled",
            status_message="Payment time expired",
            updated_at=now,
    )
    transactions = TransactionHistory.objects.filter(buyer=request.user).order_by("-created_at")
    return render(request, "transactions.html", {**page_context(request), "transactions": transactions})

# Carts
@login_required
@never_cache
def cart(request):
    cart_items = CartItem.objects.filter(buyer=request.user).order_by("-created_at")
    return render(request, "carts.html", {**page_context(request), "cart_items": cart_items})

@login_required
@require_POST
def remove_cart_item(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, buyer=request.user)
    item.delete()

    return JsonResponse({
        "success": True,
        "message": "Item removed successfully."
    })

# Logic
@login_required
@require_POST
def checkout_cart(request):
    selected_ids = request.POST.get("selected_cart_ids", "")

    if not selected_ids:
        return redirect("main:cart")

    item_ids = list({int(item_id) for item_id in selected_ids.split(",") if item_id.strip()})

    if not item_ids:
        return redirect("main:cart")

    deadline = timezone.now() + timedelta(minutes=10)

    with transaction.atomic():
        cart_items = list(CartItem.objects
            .filter(buyer=request.user, id__in=item_ids, selected=True) 
            .select_related("listing", "listing__seller")
            .select_for_update()
        )

        if not cart_items:
            return redirect("main:cart")

        for item in cart_items:
            listing = item.listing

            if listing is None:
                return redirect("main:cart")
            if listing.price is None or listing.price <= 0:
                return redirect("main:cart")
            if item.quantity < 1 or item.quantity > listing.stock:
                return redirect("main:cart")

        for item in cart_items:
            listing = item.listing

            TransactionHistory.objects.create(
                buyer=request.user,
                listing=listing,
                item_name=listing.name,
                item_image_url=listing.image_url or "",
                price=listing.price * item.quantity,
                status="ongoing",
                item_count=item.quantity,
                seller_name=listing.seller.get_full_name().strip(),
                payment_deadline=deadline,
            )
        CartItem.objects.filter(buyer=request.user, id__in=[item.id for item in cart_items]).delete()
    return redirect("main:transaction_history")

@login_required
@require_POST
def add_to_cart(request, listing_id):
    listing = get_object_or_404(Listing, pk=listing_id)

    if listing.stock <= 0:
        return redirect("listings:detail", pk=listing.pk)
    
    try:
        quantity = int(request.POST.get("quantity", 1))
    except (TypeError, ValueError):
        quantity = 0

    if quantity < 1 or quantity > listing.stock:
        return redirect("listings:detail", pk=listing.pk)

    cart_item, created = CartItem.objects.get_or_create(
        buyer=request.user,
        listing=listing,
        defaults={
            "quantity": quantity,
            "selected": True,
        },
    )

    if not created:
        new_quantity = cart_item.quantity + quantity
        if new_quantity <= listing.stock:
            cart_item.quantity = new_quantity
            cart_item.save(update_fields=["quantity"])
        else:
            return redirect("listings:detail", pk=listing.pk)

    return redirect("main:cart")
