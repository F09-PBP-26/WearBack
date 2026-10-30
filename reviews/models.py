from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


REVIEW_TAGS = ['Quality', 'Description', 'Delivery', 'Packaging']


def validate_review_tags(value):
    if (not isinstance(value, list) or any(not isinstance(tag, str) or tag not in REVIEW_TAGS for tag in value)
            or len(value) != len(set(value))):
        raise ValidationError('Choose valid, unique review highlights.')


class Review(models.Model):
    """A verified buyer's review of a purchased product.

    Listing membership is checked against the product saved during checkout.
    Historical transactions without that relation cannot be reviewed.
    Call full_clean() in the submission service (or use a ModelForm); ordinary
    Django save() does not run model validation.
    """

    transaction = models.ForeignKey(
        'main.TransactionHistory', on_delete=models.PROTECT, related_name='reviews',
    )
    listing = models.ForeignKey(
        'listings.Listing', on_delete=models.PROTECT, related_name='reviews',
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='reviews_written',
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.CharField(max_length=500, blank=True)
    tags = models.JSONField(default=list, blank=True, validators=[validate_review_tags])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rating__gte=1, rating__lte=5),
                name='review_rating_between_1_and_5',
            ),
            models.UniqueConstraint(
                fields=['transaction', 'listing'], name='review_unique_transaction_listing',
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        # Query safely even when a form contains an invalid foreign key.
        order = self._meta.get_field('transaction').remote_field.model.objects.filter(
            pk=self.transaction_id,
        ).first() if self.transaction_id else None
        listing = self._meta.get_field('listing').remote_field.model.objects.filter(
            pk=self.listing_id,
        ).first() if self.listing_id else None
        if order:
            if not order.listing_id:
                errors['transaction'] = 'This transaction has no linked product and cannot be reviewed.'
            elif self.listing_id != order.listing_id:
                errors['listing'] = 'You can only review the product purchased in this transaction.'
            if order.status != 'completed':
                errors['transaction'] = 'Only completed transactions can be reviewed.'
            if self.reviewer_id and order.buyer_id != self.reviewer_id:
                errors['reviewer'] = 'Only the buyer of this transaction can write a review.'
        if listing and self.reviewer_id == listing.seller_id:
            errors['listing'] = 'You cannot review your own listing.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'Review for listing {self.listing_id}: {self.rating}/5'
