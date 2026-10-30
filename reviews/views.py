from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Avg, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from main.models import TransactionHistory
from main.views import page_context
from reviews.forms import ReviewFilterForm, ReviewForm
from reviews.models import Review


def editor_context(order, review=None, form=None):
    eligible = (order.status == 'completed' and order.listing_id
                and order.listing.seller_id != order.buyer_id)
    if form is None:
        form = ReviewForm(initial={'rating': review.rating, 'comment': review.comment, 'tags': review.tags}) if review else ReviewForm()
    return {
        'order': order, 'review': review, 'form': form, 'can_review': bool(eligible),
        'form_action': reverse('reviews:edit', args=[review.pk]) if review else reverse('reviews:create', args=[order.pk]),
    }


def editor_response(request, order, review=None, form=None, status=200, message=''):
    context = editor_context(order, review, form)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'html': render_to_string('reviews/components/editor.html', context, request=request),
                             'message': message}, status=status)
    if status < 400 and message:
        return redirect('main:transaction_review', transaction_id=order.pk)
    return render(request, 'reviews/edit.html', {**page_context(request), **context}, status=status)


def save_review(form, review):
    if not form.is_valid():
        return False
    review.rating = form.cleaned_data['rating']
    review.comment = form.cleaned_data['comment']
    review.tags = form.cleaned_data['tags']
    try:
        review.full_clean()
        # Savepoint lets an integrity failure become a readable form error.
        with transaction.atomic():
            review.save()
    except ValidationError as error:
        for message in error.messages:
            form.add_error(None, message)
        return False
    except IntegrityError:
        form.add_error(None, 'This order already has a review. Refresh the page to edit it.')
        return False
    return True


@never_cache
@login_required
@require_GET
def transaction_review(request, transaction_id):
    order = get_object_or_404(
        TransactionHistory.objects.select_related('listing'), pk=transaction_id, buyer=request.user,
        status__in=['delivered', 'completed'],
    )
    context = page_context(request)
    context['order'] = order
    context['order_total'] = 'Rp' + f'{order.price:,.0f}'.replace(',', '.')
    context.update(editor_context(order, order.reviews.filter(reviewer=request.user).first()))
    return render(request, 'reviews/transaction_detail.html', context)


@never_cache
@login_required
@require_POST
def review_create(request, transaction_id):
    with transaction.atomic():
        order = get_object_or_404(TransactionHistory.objects.select_for_update(), pk=transaction_id, buyer=request.user)
        form = ReviewForm(request.POST)
        review = Review(transaction=order, listing_id=order.listing_id, reviewer=request.user)
        if save_review(form, review):
            return editor_response(request, order, review, status=201, message='Review submitted.')
        return editor_response(request, order, form=form, status=400)


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def review_edit(request, pk):
    with transaction.atomic():
        review = get_object_or_404(Review.objects.select_for_update(), pk=pk, reviewer=request.user)
        order = review.transaction
        if request.method == 'GET':
            return editor_response(request, order, review)
        form = ReviewForm(request.POST)
        if save_review(form, review):
            return editor_response(request, order, review, message='Review updated.')
        return editor_response(request, order, review, form, status=400)


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def review_delete(request, pk):
    review = get_object_or_404(Review.objects.select_related('transaction'), pk=pk, reviewer=request.user)
    if request.method == 'GET':
        return render(request, 'reviews/delete.html', {**page_context(request), 'review': review})
    order = review.transaction
    review.delete()
    return editor_response(request, order, message='Review deleted.')


@never_cache
@login_required
@require_GET
def review_list(request):
    form = ReviewFilterForm(request.GET)
    reviews = Review.objects.select_related('listing', 'reviewer', 'transaction')
    average = None
    if form.is_valid():
        data = form.cleaned_data
        reviews = reviews.filter(listing__seller=request.user) if data['scope'] == 'received' else reviews.filter(reviewer=request.user)
        if data['rating']:
            reviews = reviews.filter(rating=int(data['rating']))
        if data['q']:
            reviews = reviews.filter(Q(transaction__item_name__icontains=data['q']) | Q(comment__icontains=data['q']))
        average = reviews.aggregate(value=Avg('rating'))['value']
        ordering = {'oldest': ['created_at', 'pk'], 'highest': ['-rating', '-created_at', '-pk']}
        reviews = reviews.order_by(*ordering.get(data['sort'], ['-created_at', '-pk']))
    else:
        reviews = reviews.none()
    page = Paginator(reviews, 9).get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)
    context = {'filter_form': form, 'page_obj': page, 'average': average, 'filter_query': params.urlencode()}
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'html': render_to_string('reviews/components/results.html', context, request=request)})
    return render(request, 'reviews/list.html', {**page_context(request), **context})
