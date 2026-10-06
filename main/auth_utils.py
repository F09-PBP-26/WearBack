from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from main.models import AuthThrottle


def throttled(request, scope, subject=None):
    """Database-backed limits shared by all workers; do not trust forwarded IPs."""
    now = timezone.now()
    keys = [f"{scope}:ip:{request.META.get('REMOTE_ADDR', 'unknown')}"]
    if subject:
        keys.append(f'{scope}:subject:{subject.strip().lower()}')
    exceeded = False
    with transaction.atomic():
        AuthThrottle.objects.filter(expires_at__lte=now).delete()
        for raw_key in keys:
            key = salted_hmac('wearback-auth-throttle', raw_key, algorithm='sha256').hexdigest()
            counter, _ = AuthThrottle.objects.select_for_update().get_or_create(
                key=key, defaults={'expires_at': now + timedelta(seconds=settings.AUTH_RATE_WINDOW)}
            )
            counter.attempts += 1
            counter.save(update_fields=['attempts'])
            exceeded = exceeded or counter.attempts > settings.AUTH_RATE_LIMIT
    return exceeded
