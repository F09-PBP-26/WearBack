# Clothing Listing Module Checklist

Work through these steps in order. Add tests alongside each behavior as you implement it.

- [x] **1. Create and register the app.** `listings/` exists and `listings.apps.ListingsConfig` is in `INSTALLED_APPS`. Django's system check passed after registration.

- [x] **2. Define and implement the permissions foundation.** Guests can browse public listing information, creating requires login, and editing/deleting requires ownership. Published contact email is visible only to authenticated users. Basic listing routes and screens implement these rules, with permission and login-return tests passing. See the [permissions implementation notes](listings-permissions-plan.md). Coordinate availability with the transactions module when expanding the model.

- [ ] **3. Expand `Listing` in `listings/models.py`.** The permissions foundation already has seller, name, description, optional published contact email, and timestamps. Add `category`, `size`, `condition`, `price`, and `photo`. Ownership already references `settings.AUTH_USER_MODEL` with cascading deletion; review retention needs with the transaction module. Use `DecimalField` for price and enforce a positive price through validation and a database constraint. Define category/condition choices. Existing category filter values are `tops`, `bottoms`, `outerwear`, `shoes`, `legwear`, and `accessories`. Add `location` only if it will be collected; the current catalog's location is placeholder text.

- [ ] **4. Set up uploaded photos.** For uploaded photos, use `ImageField` and add Pillow to `requirements.txt`. Configure `MEDIA_ROOT` and `MEDIA_URL` in `config/settings.py`, development media URLs in `config/urls.py`, and an ignore rule for local uploads. Validate image contents and upload size on the server. Use `multipart/form-data` and pass `request.FILES` when binding forms. Plan persistent production storage and media serving; WhiteNoise handles static assets, not user uploads.

- [ ] **5. Generate and apply migrations.** Review the generated migration, then run the commands below from the repository root. The existing authentication adoption rules in `docs/authentication.md` still apply if working against a legacy database.

  ```powershell
  .\env\Scripts\python.exe manage.py makemigrations listings
  .\env\Scripts\python.exe manage.py migrate
  ```

- [ ] **6. Register `Listing` in `listings/admin.py`.** Show useful columns such as name, seller, category, price, and creation time. Create a sample listing in the admin to verify the model and photo storage.

- [ ] **7. Create a `ListingForm` in `listings/forms.py`.** Use `ModelForm` with an explicit list of editable fields. Exclude seller and timestamps. Validate required fields, price, choices, and photos, and show useful field errors. Set `listing.seller = request.user` in the create view instead of accepting an owner from submitted data.

- [ ] **8. Add named routes.** Create `listings/urls.py` with `app_name = 'listings'` and include it under `/listings/` in `config/urls.py`. Suggested routes: `create`, `detail`, `update`, `delete`, and `mine`. Use named URLs in redirects and templates. The existing homepage can remain the catalog route.

- [ ] **9. Implement the views in `listings/views.py`.** Create listings for the logged-in user, show public details, update/delete only listings owned by that user, and filter My listings by that user. Enforce ownership in the database lookup, not just by hiding buttons. GET may show forms or deletion confirmation; changes require CSRF-protected POST requests. Missing listings should return 404, and another user's listings must not be modified. Preserve the existing login popup behavior when directing guests to sign in.

- [ ] **10. Build and connect the UI.** Put listing templates under `templates/listings/` and extend `base.html`. Build create/edit forms, details, deletion confirmation, and My listings. Replace the coming-soon List an item action with the real create flow, and expose My listings from the account menu. Show edit/delete controls only to the owner, display validation errors, and preserve submitted text when validation fails. Reuse the existing CSS tokens and shared components.

- [ ] **11. Connect the homepage catalog to the database.** Update `main.views.show_main` to add real `catalog_items` while preserving `page_context(request)` for authentication notices and SSO state. Adapt `templates/components/catalog-item.html` to the model: it currently expects `image_url` and `price_display`, so supply properties or update those references. Render choice labels while keeping stable category values in `data-category`, preserve `data-catalog-name`, and link each card to its detail page. Replace the fake-item fallback in `templates/index.html` with a real empty state. Check that the existing search and category filters still work; they currently filter only cards already rendered in the browser.

- [ ] **12. Prepare at least 50 sample listings.** This count comes from `README.md`. Use synthetic data with valid categories, sizes, conditions, prices, and seller relationships. A repeatable management command or fixture will make setup easier for teammates. Document how to load it; keep credentials and the local database out of Git.

- [ ] **13. Complete automated verification.** Add meaningful tests in `listings/tests.py` for catalog/detail rendering, valid and invalid submissions, authentication, ownership, seller assignment, deletion methods, CSRF, image uploads, and missing listings. Use temporary upload storage in tests so files do not leak into development media. Then run:

  ```powershell
  .\env\Scripts\python.exe manage.py check
  .\env\Scripts\python.exe manage.py makemigrations --check --dry-run
  .\env\Scripts\python.exe manage.py test listings
  .\env\Scripts\python.exe manage.py test
  ```

- [ ] **14. Check the complete user journey manually.** Create a listing, see it in the catalog, open its details, edit it, and delete it. Repeat with a guest, its owner, and a different logged-in user. Check desktop/mobile layouts, keyboard and dialog focus, photos, empty states, validation errors, search, and filters. Verify existing local and SSO authentication still works. Update the existing template cache versions for changed CSS/JS.

- [ ] **15. Prepare the change for review.** Document model/migration and photo-storage setup, sample-data loading, and any new environment requirements. Update `AGENTS.md` to reflect implemented behavior. Commit the app, migrations, templates, source assets, and dependency/configuration changes together. Include validation results and screenshots in the PR.
