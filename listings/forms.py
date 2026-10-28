from django import forms

from listings.models import Listing


class ListingForm(forms.ModelForm):
    class Meta:
        model = Listing
        fields = ['name', 'description', 'contact_email']
        labels = {'contact_email': 'Contact email (optional)'}
        help_texts = {'contact_email': 'Only signed-in WearBack members can see this address.'}
        widgets = {'description': forms.Textarea(attrs={'rows': 5})}
