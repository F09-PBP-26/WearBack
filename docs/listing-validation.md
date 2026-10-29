# Required fields for new listings

The seller's Create Item form requires name, price, category, size, and condition. Name was already required; the other four fields are now required when `ListingForm` represents an unsaved listing.

## Rules

- Price must be supplied and remain positive, with the existing decimal precision and Indonesian formatting support, such as `100.000` and `1.234.567,50`.
- Category and condition must be supplied and match existing model choices. Size must be nonblank and respect its existing 32-character limit; existing size handling is preserved.
- Django enforces these requirements on POST even when browser validation is bypassed. Invalid submissions render the existing error summary and field messages, retain entered values, and create no database row.
- Native HTML `required` attributes follow the form's field metadata. Labels use the same metadata for visible asterisks, with a “Fields marked * are required” explanation. Existing keyboard/focus and error behavior is reused.
- Optional photo, description, clothing specifications, location, and published-contact fields retain their current behavior. Stock may be zero, and an omitted stock value retains the existing default/preservation rules.

## Compatibility and scope

This requirement applies to creation through the seller form. Editing an existing listing retains the previous optional-field rules, including for older incomplete listings; it does not enforce permanent completeness after creation. Public catalog/detail fallbacks and owner-only edit/delete permissions remain unchanged.

The database model, migrations, admin form, and sample-data storage are unchanged. No migration, dependency, environment variable, or data backfill is required.

## Verification

`RequiredListingFieldsTests` covers missing/empty/whitespace values, name-only submissions and retained input, localized prices, zero stock, omitted optional fields, native required attributes, and legacy viewing/editing. Existing successful creation payloads were updated in ownership, valid-CSRF, SSO-user, and catalog tests; incomplete database fixtures remain in legacy tests. Existing invalid-input tests now provide complete baseline payloads and also check the size limit.

The focused five-test class and complete 81-test Django suite pass. Django checks and migration drift checks pass. Browser checks cover desktop/mobile required indicators, native empty-submission blocking, successful creation, server-side validation errors, retained input, and legacy editing using an isolated preview database.
