from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from listings.forms import ListingForm
from listings.models import Listing
from main.models import Bid
from main.views import AUCTION_DURATION, BID_EXTENSION, _format_rupiah, page_context


@never_cache
@require_GET
def index(request):
    return redirect(reverse('main:show_main') + '#catalog')


@never_cache
@require_GET
def detail(request, pk):
    listing = get_object_or_404(Listing.objects.select_related('seller'), pk=pk)
    approved_bids = listing.bids.filter(status=Bid.Status.APPROVED)
    highest_bid = approved_bids.order_by('-amount', 'approved_at', 'pk').first()
    first_bid = approved_bids.order_by('approved_at', 'pk').first()
    auction_bid_count = approved_bids.count()
    auction_end_at = (
        first_bid.approved_at + AUCTION_DURATION
        + BID_EXTENSION * max(auction_bid_count - 1, 0)
        if first_bid else None
    )
    auction_ended = bool(auction_end_at and auction_end_at <= timezone.now())
    current_bid = highest_bid.amount if highest_bid else listing.price
    can_manage = request.user.is_authenticated and listing.seller_id == request.user.pk
    pending_bids = listing.bids.filter(status=Bid.Status.PENDING)
    own_pending_bid = (
        pending_bids.filter(bidder=request.user).first()
        if request.user.is_authenticated else None
    )
    context = page_context(request)
    context.update(listing=listing,
                   contact_email=listing.contact_email if request.user.is_authenticated else '',
                   can_manage=can_manage,
                   seller_listing_count=Listing.objects.filter(seller_id=listing.seller_id).count(),
                   auction_bids=approved_bids.select_related('bidder')[:10],
                   auction_bid_count=auction_bid_count,
                   auction_pending_bids=pending_bids.select_related('bidder') if can_manage else (),
                   auction_has_pending_bid=pending_bids.exists(),
                   auction_own_pending_bid=own_pending_bid,
                   auction_current_bid=current_bid,
                   auction_current_bid_display=_format_rupiah(current_bid) if current_bid is not None else '',
                   auction_end_at=auction_end_at,
                   auction_ended=auction_ended,
                   auction_is_open=listing.is_available and not auction_ended,
                   auction_winner=highest_bid,
                   auction_is_highest_bidder=(
                       request.user.is_authenticated and highest_bid is not None
                       and highest_bid.bidder_id == request.user.pk
                   ))
    return render(request, 'listings/detail.html', context)


@never_cache
@login_required
@require_GET
def mine(request):
    context = page_context(request)
    listings = Listing.objects.filter(seller=request.user).annotate(
        auction_locked=Exists(Bid.objects.filter(
            listing_id=OuterRef('pk'),
            status__in=[Bid.Status.PENDING, Bid.Status.APPROVED],
        )),
    )
    context.update(listings=listings, own_listings=True)
    return render(request, 'listings/dashboard.html', context)


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def create(request):
    form = ListingForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        listing = form.save(commit=False)
        listing.seller = request.user
        listing.save()
        messages.success(request, 'Your item is now listed.')
        return redirect('listings:detail', pk=listing.pk)
    context = page_context(request)
    context.update(form=form, listing=None)
    return render(request, 'listings/form.html', context)


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def update(request, pk):
    if request.method == 'POST':
        with transaction.atomic():
            listing = get_object_or_404(
                Listing.objects.select_for_update(), pk=pk, seller=request.user,
            )
            if listing.bids.filter(status__in=[Bid.Status.PENDING, Bid.Status.APPROVED]).exists():
                messages.error(request, 'This listing cannot be changed after bidding has started.')
                return redirect('listings:detail', pk=listing.pk)
            form = ListingForm(request.POST, instance=listing)
            if form.is_valid():
                form.save()
                messages.success(request, 'Your changes have been saved.')
                return redirect('listings:detail', pk=listing.pk)
    else:
        listing = get_object_or_404(Listing, pk=pk, seller=request.user)
        if listing.bids.filter(status__in=[Bid.Status.PENDING, Bid.Status.APPROVED]).exists():
            messages.error(request, 'This listing cannot be changed after bidding has started.')
            return redirect('listings:detail', pk=listing.pk)
        form = ListingForm(instance=listing)
    context = page_context(request)
    context.update(form=form, listing=listing)
    return render(request, 'listings/form.html', context)


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def delete(request, pk):
    if request.method == 'POST':
        with transaction.atomic():
            listing = get_object_or_404(
                Listing.objects.select_for_update(), pk=pk, seller=request.user,
            )
            if listing.bids.filter(status__in=[Bid.Status.PENDING, Bid.Status.APPROVED]).exists():
                messages.error(request, 'This listing cannot be deleted after bidding has started.')
                return redirect('listings:detail', pk=listing.pk)
            listing.delete()
            messages.success(request, 'Listing deleted.')
            return redirect('listings:mine')
    listing = get_object_or_404(Listing, pk=pk, seller=request.user)
    if listing.bids.filter(status__in=[Bid.Status.PENDING, Bid.Status.APPROVED]).exists():
        messages.error(request, 'This listing cannot be deleted after bidding has started.')
        return redirect('listings:detail', pk=listing.pk)
    context = page_context(request)
    context['listing'] = listing
    return render(request, 'listings/confirm_delete.html', context)
