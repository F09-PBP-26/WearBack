from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from listings.forms import ListingForm
from listings.models import Listing
from main.views import page_context


@never_cache
@require_GET
def index(request):
    context = page_context(request)
    context.update(listings=Listing.objects.all(), own_listings=False)
    return render(request, 'listings/list.html', context)


@never_cache
@require_GET
def detail(request, pk):
    listing = get_object_or_404(Listing.objects.select_related('seller'), pk=pk)
    context = page_context(request)
    context.update(listing=listing,
                   contact_email=listing.contact_email if request.user.is_authenticated else '',
                   can_manage=request.user.is_authenticated and listing.seller_id == request.user.pk,
                   seller_listing_count=Listing.objects.filter(seller_id=listing.seller_id).count())
    return render(request, 'listings/detail.html', context)


@never_cache
@login_required
@require_GET
def mine(request):
    context = page_context(request)
    context.update(listings=Listing.objects.filter(seller=request.user), own_listings=True)
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
    listing = get_object_or_404(Listing, pk=pk, seller=request.user)
    form = ListingForm(request.POST if request.method == 'POST' else None, instance=listing)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Your changes have been saved.')
        return redirect('listings:detail', pk=listing.pk)
    context = page_context(request)
    context.update(form=form, listing=listing)
    return render(request, 'listings/form.html', context)


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def delete(request, pk):
    listing = get_object_or_404(Listing, pk=pk, seller=request.user)
    if request.method == 'POST':
        listing.delete()
        messages.success(request, 'Listing deleted.')
        return redirect('listings:mine')
    context = page_context(request)
    context['listing'] = listing
    return render(request, 'listings/confirm_delete.html', context)
