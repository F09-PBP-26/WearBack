from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from main.models import TransactionHistory
from main.views import page_context


@never_cache
@login_required
@require_GET
def transaction_review(request, transaction_id):
    order = get_object_or_404(
        TransactionHistory, pk=transaction_id, buyer=request.user,
        status__in=['delivered', 'completed'],
    )
    context = page_context(request)
    context['order'] = order
    context['order_total'] = 'Rp' + f'{order.price:,.0f}'.replace(',', '.')
    return render(request, 'reviews/transaction_detail.html', context)
