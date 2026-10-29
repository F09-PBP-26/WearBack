import re
from decimal import Decimal

from django import forms

from listings.models import Listing


class RupiahField(forms.DecimalField):
    def to_python(self, value):
        if isinstance(value, str):
            value = value.strip()
            if re.fullmatch(r'\d{1,3}(\.\d{3})+(,\d{1,2})?', value):
                value = value.replace('.', '')
            value = value.replace(',', '.')
        return super().to_python(value)


class ListingForm(forms.ModelForm):
    price = RupiahField(label='Price (Rp)', required=False, max_digits=12, decimal_places=2,
                        min_value=Decimal('0.01'), widget=forms.TextInput(attrs={'inputmode': 'decimal',
                                                                       'placeholder': 'e.g. 100.000'}))
    stock = forms.IntegerField(label='Available quantity', min_value=0, max_value=9999, required=False, initial=1,
                               help_text='Set to zero when the item is no longer available.')

    class Meta:
        model = Listing
        fields = ['name', 'description', 'price', 'image_url', 'category', 'size', 'condition',
                  'brand', 'material', 'style', 'location', 'stock', 'contact_email']
        labels = {'name': 'Item name', 'image_url': 'Photo URL', 'contact_email': 'Contact email (optional)',
                  'location': 'Location (city, optional)'}
        help_texts = {'image_url': 'Paste a direct HTTPS image link. Leave empty to show a placeholder.',
                      'stock': 'Set to zero when the item is no longer available.',
                      'contact_email': 'Only signed-in WearBack members can see this address.'}
        widgets = {'name': forms.TextInput(attrs={'placeholder': 'e.g. Ribbed socks'}),
                   'description': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Describe the item, fit, and any signs of wear.'}),
                   'image_url': forms.URLInput(attrs={'placeholder': 'Paste a direct image URL'}),
                   'location': forms.TextInput(attrs={'placeholder': 'e.g. Depok, Indonesia'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.label_suffix = ''
        if self.instance._state.adding:
            for name in ('price', 'category', 'size', 'condition'):
                self.fields[name].required = True
        self.fields['category'].choices = [('', 'Choose a category'), *Listing.Category.choices]
        self.fields['condition'].choices = [('', 'Choose a condition'), *Listing.Condition.choices]
        sizes = ['XXS', 'XS', 'Small', 'Medium', 'Large', 'XL', 'XXL', 'One size']
        current_size = self.data.get(self.add_prefix('size'), '') if self.is_bound else self.initial.get('size', '')
        if current_size and current_size not in sizes:
            sizes.append(current_size)
        self.fields['size'].widget = forms.Select(choices=[('', 'Choose a size'), *((size, size) for size in sizes)])
        if not self.is_bound and self.instance.price is not None:
            self.initial['price'] = self.instance.price_display.removeprefix('Rp')

    @property
    def preview_image_url(self):
        if self.is_bound:
            return self.cleaned_data.get('image_url', '') if 'image_url' not in self.errors else ''
        return self.instance.image_url

    @property
    def extra_details_have_errors(self):
        return any(name in self.errors for name in ('brand', 'material', 'style', 'location', 'stock', 'contact_email'))

    def clean_stock(self):
        value = self.cleaned_data.get('stock')
        return value if value is not None else self.instance.stock
