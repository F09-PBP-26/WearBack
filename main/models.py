from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


class User(AbstractUser):
    """WearBack account; usernames are internal, local login uses email."""

    id = models.AutoField(primary_key=True)
    email = models.EmailField(blank=True, null=True)
    groups = models.ManyToManyField(Group, blank=True, related_name='wearback_users', related_query_name='wearback_user')
    user_permissions = models.ManyToManyField(Permission, blank=True, related_name='wearback_users', related_query_name='wearback_user')

    class Meta:
        db_table = 'auth_user'
        constraints = [models.UniqueConstraint(Lower('email'), condition=models.Q(email__isnull=False), name='wearback_email_unique')]

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower() if self.email else None
        super().save(*args, **kwargs)


class SSOIdentity(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sso_identities')
    provider = models.CharField(max_length=32, default='ui')
    subject = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['provider', 'subject'], name='sso_subject_unique'),
            models.UniqueConstraint(fields=['provider', 'user'], name='sso_user_unique'),
        ]

    def __str__(self):
        return f'{self.provider}: {self.subject}'


class AuthThrottle(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    attempts = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)

class TransactionHistory(models.Model):
    STATUS_CHOICES = [
        ("ongoing", "Ongoing"),
        ("delivered", "Delivered"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transaction_histories")
    item_name = models.CharField(max_length=255)
    item_image_url = models.URLField(blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ongoing")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    order_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    item_summary = models.CharField(max_length=255, blank=True,)
    item_count = models.PositiveIntegerField(default=1)
    seller_name = models.CharField(max_length=255, blank=True)
    status_message = models.CharField(max_length=255, blank=True)
    payment_deadline = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.item_name} - {self.get_status_display()}"

class CartItem(models.Model):
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart_items")

    # Data item sementara
    listing = models.ForeignKey("listings.Listing", on_delete=models.SET_NULL, null=True, blank=True, related_name="cart_items")
    quantity = models.PositiveIntegerField(default=1)
    selected = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.item_name} - {self.buyer}"