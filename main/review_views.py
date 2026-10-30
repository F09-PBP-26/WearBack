"""UI preview for reviews until the transaction integration is ready."""

from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from main.views import page_context


@never_cache
@require_GET
def review_preview(request):
    # These are design fixtures, not a real customer's transaction.
    context = page_context(request)
    context['items'] = [
        {'id': 'scarf', 'name': 'Scarf Wool 1970’s',
         'image': 'img/reviews/Scarf Wool 1970 s.png',
         'details': 'Size M · Great condition', 'price': 'Rp300.000'},
        {'id': 'plaid', 'name': 'Plaid wool scarf',
         'image': 'img/reviews/Plaid Wool Scarf.png',
         'details': 'Size L · Good condition', 'price': 'Rp395.000'},
        {'id': 'jeans', 'name': 'Vintage straight jeans',
         'image': 'img/reviews/Vintage Straight Jeans.png',
         'details': 'Size 32 · Like new', 'price': 'Rp1.000.000'},
    ]
    context['rating_values'] = range(1, 6)
    context['review_tags'] = ['Quality', 'Description', 'Delivery', 'Packaging']
    return render(request, 'reviews/transaction_preview.html', context)
