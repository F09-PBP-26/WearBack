from decimal import Decimal
from uuid import uuid4

from django import forms
from django.contrib.auth import authenticate, get_user_model, password_validation
from django.core.exceptions import ValidationError

from listings.forms import RupiahField

User = get_user_model()


class DropoffLocationForm(forms.Form):
    address = forms.CharField(
        max_length=500, label='Drop-off address',
        widget=forms.Textarea(attrs={'rows': 4, 'placeholder': 'Street, building, and delivery instructions'}),
    )
    latitude = forms.DecimalField(
        min_value=-90, max_value=90, max_digits=9, decimal_places=6,
        widget=forms.HiddenInput,
    )
    longitude = forms.DecimalField(
        min_value=-180, max_value=180, max_digits=9, decimal_places=6,
        widget=forms.HiddenInput,
    )


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField(max_length=254)
    location = forms.CharField(max_length=255)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'location']

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        existing = User.objects.filter(email__iexact=email)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise ValidationError('This email is already registered. Log in to that account to link SSO UI.')
        return email


class RegisterForm(ProfileForm):
    password = forms.CharField(strip=False, widget=forms.PasswordInput)
    password_confirm = forms.CharField(strip=False, widget=forms.PasswordInput)

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get('password')
        if password and password != cleaned.get('password_confirm'):
            self.add_error('password_confirm', 'Passwords do not match.')
        if password:
            user = User(**{key: cleaned.get(key, '') for key in ['first_name', 'last_name', 'email', 'location']})
            try:
                password_validation.validate_password(password, user)
            except ValidationError as errors:
                self.add_error('password', errors)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = 'local_' + uuid4().hex
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class LoginForm(forms.Form):
    email = forms.EmailField(max_length=254)
    password = forms.CharField(strip=False, widget=forms.PasswordInput)

    def __init__(self, *args, request=None, **kwargs):
        self.request = request
        self.user = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('email') and cleaned.get('password'):
            self.user = authenticate(self.request, email=cleaned['email'], password=cleaned['password'])
            if self.user is None:
                raise ValidationError('Email or password is incorrect.')
        return cleaned


class BidForm(forms.Form):
    amount = RupiahField(
        label='Your bid (Rp)',
        max_digits=12,
        decimal_places=2,
        min_value=Decimal('0.01'),
        widget=forms.TextInput(attrs={
            'inputmode': 'decimal',
            'autocomplete': 'off',
        }),
    )
