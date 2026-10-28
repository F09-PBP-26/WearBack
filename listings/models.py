from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, URLValidator
from django.db import models


class Listing(models.Model):
    class Category(models.TextChoices):
        TOPS = 'tops', 'Tops'
        BOTTOMS = 'bottoms', 'Bottoms'
        OUTERWEAR = 'outerwear', 'Outerwear'
        SHOES = 'shoes', 'Shoes'
        LEGWEAR = 'legwear', 'Legwear'
        ACCESSORIES = 'accessories', 'Accessories'

    class Condition(models.TextChoices):
        LIKE_NEW = 'like_new', 'Like new'
        GREAT = 'great', 'Great'
        GOOD = 'good', 'Good'
        FAIR = 'fair', 'Fair'

    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='listings')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True,
                                validators=[MinValueValidator(Decimal('0.01'))])
    image_url = models.URLField(max_length=1000, blank=True, validators=[URLValidator(schemes=['https'])])
    category = models.CharField(max_length=20, choices=Category.choices, blank=True)
    size = models.CharField(max_length=32, blank=True)
    condition = models.CharField(max_length=20, choices=Condition.choices, blank=True)
    brand = models.CharField(max_length=100, blank=True)
    material = models.CharField(max_length=100, blank=True)
    style = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=100, blank=True)
    stock = models.PositiveIntegerField(default=1, validators=[MaxValueValidator(9999)])
    contact_email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        constraints = [models.CheckConstraint(condition=models.Q(price__isnull=True) | models.Q(price__gt=0),
                                               name='listing_price_positive')]

    def __str__(self):
        return self.name

    @property
    def price_display(self):
        if self.price is None:
            return 'Price not set'
        amount = f'{self.price:,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')
        return 'Rp' + (amount[:-3] if amount.endswith(',00') else amount)

    @property
    def is_available(self):
        return self.stock > 0 and self.price is not None
