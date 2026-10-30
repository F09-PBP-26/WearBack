"""CSV parsing and validation shared by the admin preview and confirmation."""

import csv
import io

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from listings.forms import ListingForm


MAX_IMPORT_ROWS = 500
MAX_UPLOAD_BYTES = 2 * 1024 * 1024
CSV_FIELDS = (
    'name', 'seller', 'price', 'category', 'size', 'condition', 'stock',
    'image_url', 'description', 'brand', 'material', 'style', 'location', 'contact_email',
)
REQUIRED_COLUMNS = ('name', 'price', 'category', 'size', 'condition')


def read_listing_csv(upload):
    if not upload.name.lower().endswith('.csv'):
        raise ValidationError('Choose a .csv file saved as UTF-8.')
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError('The CSV file must be 2 MB or smaller.')
    content = upload.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValidationError('The CSV file must be 2 MB or smaller.')
    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError as error:
        raise ValidationError('Save the CSV as UTF-8 and upload it again.') from error
    if '\x00' in text:
        raise ValidationError('The CSV contains an invalid null character.')

    try:
        reader = csv.reader(io.StringIO(text, newline=''), strict=True)
        headers = next((
            [value.strip() for value in values] for values in reader if any(value.strip() for value in values)
        ), [])
        if not headers:
            raise ValidationError('The CSV is empty. Download the template to get started.')
        if len(set(headers)) != len(headers):
            raise ValidationError('Each column heading must appear only once.')
        unknown = set(headers) - set(CSV_FIELDS)
        if unknown:
            raise ValidationError('Unknown columns: %(columns)s.', params={'columns': ', '.join(sorted(unknown))})
        missing = set(REQUIRED_COLUMNS) - set(headers)
        if missing:
            raise ValidationError('Missing required columns: %(columns)s.',
                                  params={'columns': ', '.join(sorted(missing))})

        rows = []
        for values in reader:
            if not any(value.strip() for value in values):
                continue
            if len(values) != len(headers):
                raise ValidationError('CSV line %(line)s has a different number of values than the headings.',
                                      params={'line': reader.line_num})
            if len(rows) >= MAX_IMPORT_ROWS:
                raise ValidationError('Import at most %(limit)s items at a time.', params={'limit': MAX_IMPORT_ROWS})
            rows.append({'line': reader.line_num, 'values': dict(zip(headers, (value.strip() for value in values)))})
    except csv.Error as error:
        raise ValidationError('The CSV could not be read. Check commas and quoted values using the template.') from error
    if not rows:
        raise ValidationError('The CSV has no items. Add at least one item below the headings.')
    return rows


def validate_listing_rows(rows):
    """Recheck current sellers and the same item rules used by the listing form."""
    usernames = {row['values'].get('seller', '') for row in rows}
    sellers = {
        user.username: user for user in get_user_model().objects.filter(username__in=usernames, is_active=True)
    }
    listings, row_errors = [], []
    for row in rows:
        data = row['values']
        form = ListingForm(data=data)
        errors = []
        if not form.is_valid():
            errors.extend({
                'field': (form.fields[field].label or field) if field in form.fields else 'Item',
                'messages': list(messages),
            } for field, messages in form.errors.items())
        seller = sellers.get(data.get('seller', ''))
        if seller is None:
            errors.append({'field': 'Seller', 'messages': ['Enter an existing active seller username or choose a default seller.']})
        if errors:
            row_errors.append({'line': row['line'], 'errors': errors})
        else:
            listing = form.save(commit=False)
            listing.seller = seller
            listings.append(listing)
    return listings, row_errors


class ListingCSVImportForm(forms.Form):
    csv_file = forms.FileField(
        label='CSV file',
        help_text='UTF-8, comma-separated .csv; up to 500 items and 2 MB.',
        widget=forms.ClearableFileInput(attrs={'accept': '.csv,text/csv'}),
    )
    default_seller = forms.ModelChoiceField(
        queryset=None, required=False,
        help_text='Used when the seller column is blank or omitted. A seller username in the CSV overrides this choice.',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['default_seller'].queryset = get_user_model().objects.filter(is_active=True).order_by('username')
        self.row_errors = []

    def clean(self):
        cleaned = super().clean()
        if 'csv_file' not in cleaned or 'default_seller' not in cleaned:
            return cleaned
        try:
            rows = read_listing_csv(cleaned['csv_file'])
        except ValidationError as error:
            self.add_error('csv_file', error)
            return cleaned
        default_seller = cleaned['default_seller']
        for row in rows:
            if not row['values'].get('seller'):
                row['values']['seller'] = default_seller.username if default_seller else ''
        _, self.row_errors = validate_listing_rows(rows)
        if self.row_errors:
            self.add_error(None, 'No items have been added. Fix the CSV errors below and upload the file again.')
        else:
            self.rows = rows
        return cleaned
