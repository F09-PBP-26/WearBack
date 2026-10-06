from django.conf import settings
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.db.models.functions import Lower


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
