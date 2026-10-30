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
from django.db.models import Count, OuterRef, Q, Subquery
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
from main.forms import BidForm, LoginForm, ProfileForm, RegisterForm
from main.models import Bid, CartItem, TransactionHistory
from main.sso import cas_client, resolve_identity


AUCTION_DURATION = timedelta(hours=24)
BID_EXTENSION = timedelta(minutes=30)


def _format_rupiah(amount):
    formatted = f'{amount:,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')
    return 'Rp' + (formatted[:-3] if formatted.endswith(',00') else formatted)


def _auction_listings():
    highest_bid = Bid.objects.filter(
        listing_id=OuterRef('pk'), status=Bid.Status.APPROVED,
    ).order_by('-amount', 'approved_at', 'pk')
    first_bid = Bid.objects.filter(
        listing_id=OuterRef('pk'), status=Bid.Status.APPROVED,
    ).order_by('approved_at', 'pk')
    listings = Listing.objects.filter(price__isnull=False).annotate(
        auction_highest_bid=Subquery(highest_bid.values('amount')[:1]),
        auction_first_bid_at=Subquery(first_bid.values('approved_at')[:1]),
        auction_bid_count=Count('bids', filter=Q(bids__status=Bid.Status.APPROVED)),
    )
    now = timezone.now()
    active = []
    ended = []
    for listing in listings:
        current_bid = listing.auction_highest_bid or listing.price
        listing.auction_current_bid = current_bid
        listing.auction_current_bid_display = _format_rupiah(current_bid)
        listing.auction_end_at = (
            listing.auction_first_bid_at + AUCTION_DURATION
            + BID_EXTENSION * max(listing.auction_bid_count - 1, 0)
            if listing.auction_first_bid_at else None
        )
        listing.auction_ended = bool(listing.auction_end_at and listing.auction_end_at <= now)
        if listing.auction_ended:
            ended.append(listing)
        elif listing.auction_bid_count and listing.stock > 0:
            active.append(listing)
    return active, ended


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
    context = page_context(request)
    context['auction_items'], context['ended_auction_items'] = _auction_listings()
    context['auction_category_count'] = len({
        item.category for item in context['auction_items'] if item.category
    })
    return render(request, 'auction.html', context)


@login_required
@never_cache
@require_POST
def place_bid(request, listing_id):
    form = BidForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Enter a valid bid amount in rupiah.')
        return redirect('listings:detail', pk=listing_id)

    amount = form.cleaned_data['amount']
    with transaction.atomic():
        listing = get_object_or_404(
            Listing.objects.select_for_update(), pk=listing_id,
        )
        now = timezone.now()
        if not listing.is_available:
            messages.error(request, 'This item is not available for bidding.')
            return redirect('listings:detail', pk=listing.pk)
        if listing.seller_id == request.user.pk:
            messages.error(request, 'You cannot bid on your own listing.')
            return redirect('listings:detail', pk=listing.pk)

        approved_bids = Bid.objects.filter(
            listing=listing, status=Bid.Status.APPROVED,
        )
        first_bid = approved_bids.order_by('approved_at', 'pk').first()
        if first_bid and first_bid.approved_at + AUCTION_DURATION + BID_EXTENSION * max(
            approved_bids.count() - 1, 0
        ) <= now:
            messages.error(request, 'Bidding for this item has ended.')
            return redirect('listings:detail', pk=listing.pk)

        if not first_bid:
            has_pending_bid = Bid.objects.filter(
                listing=listing, status=Bid.Status.PENDING,
            ).exists()
            if has_pending_bid:
                messages.error(request, 'A bid is already waiting for seller approval.')
                return redirect('listings:detail', pk=listing.pk)
            try:
                with transaction.atomic():
                    Bid.objects.create(
                        listing=listing, bidder=request.user, amount=amount,
                        status=Bid.Status.PENDING,
                    )
            except IntegrityError:
                messages.error(request, 'A bid is already waiting for seller approval.')
                return redirect('listings:detail', pk=listing.pk)
            messages.success(request, 'Your bid is waiting for seller approval.')
            return redirect('listings:detail', pk=listing.pk)

        highest_bid = approved_bids.order_by('-amount', 'approved_at', 'pk').first()
        if amount <= highest_bid.amount:
            messages.error(
                request,
                f'Your bid must be higher than the current bid of {_format_rupiah(highest_bid.amount)}.',
            )
            return redirect('listings:detail', pk=listing.pk)

        Bid.objects.create(
            listing=listing, bidder=request.user, amount=amount,
            status=Bid.Status.APPROVED, approved_at=now,
        )

    messages.success(request, 'Your bid has been placed.')
    return redirect('listings:detail', pk=listing_id)


@login_required
@never_cache
@require_POST
def decide_bid(request, listing_id, bid_id):
    with transaction.atomic():
        listing = get_object_or_404(
            Listing.objects.select_for_update(), pk=listing_id, seller=request.user,
        )
        bid = get_object_or_404(
            Bid.objects.select_for_update(), pk=bid_id, listing=listing,
            status=Bid.Status.PENDING,
        )
        if not listing.is_available:
            messages.error(request, 'This listing is not available for bidding.')
            return redirect('listings:detail', pk=listing.pk)

        decision = request.POST.get('decision')
        if decision == 'approve':
            if Bid.objects.filter(listing=listing, status=Bid.Status.APPROVED).exists():
                messages.error(request, 'An auction has already started for this listing.')
                return redirect('listings:detail', pk=listing.pk)
            bid.status = Bid.Status.APPROVED
            bid.approved_at = timezone.now()
            bid.save(update_fields=['status', 'approved_at'])
            messages.success(request, 'Bid approved. The auction has started.')
        elif decision == 'reject':
            bid.status = Bid.Status.REJECTED
            bid.save(update_fields=['status'])
            messages.success(request, 'Bid rejected. The listing can receive a new offer.')
        else:
            messages.error(request, 'Choose whether to approve or reject this bid.')
    return redirect('listings:detail', pk=listing_id)


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
            if listing.bids.filter(status__in=[Bid.Status.PENDING, Bid.Status.APPROVED]).exists():
                messages.error(
                    request,
                    f'{listing.name} is in an auction and cannot be purchased through the cart.',
                )
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

    if listing.bids.filter(status__in=[Bid.Status.PENDING, Bid.Status.APPROVED]).exists():
        messages.error(request, 'This item has received a bid and is available through the auction only.')
        return redirect("listings:detail", pk=listing.pk)
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
