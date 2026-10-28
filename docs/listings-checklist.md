# Clothing Listing Module Checklist

Work through these steps in order. Add tests alongside each behavior as you implement it.

- [x] **1. Create and register the app.** `listings/` exists and `listings.apps.ListingsConfig` is in `INSTALLED_APPS`. Django's system check passed after registration.

- [x] **2. Define and implement the permissions foundation.** Guests can browse public listing information, creating requires login, and editing/deleting requires ownership. Published contact email is visible only to authenticated users. Basic listing routes and screens implement these rules, with permission and login-return tests passing. See the [permissions implementation notes](listings-permissions-plan.md). Coordinate availability with the transactions module when expanding the model.

- [x] **3. Expand the listing fields for the item detail page.** The model now has optional price, HTTPS photo URL, category, size, condition, brand, material, style, location, and stock, in addition to ownership, description, contact email, and timestamps. Prices use `DecimalField` with positive validation and a database constraint. Category values match existing catalog filters. Review account-deletion retention needs with the transaction module. See [item detail notes](item-detail.md).

- [ ] **4. Add file uploads if required beyond the Figma photo-URL flow.** The implemented detail page accepts direct HTTPS image URLs, matching the current create/edit Figma designs, with a local missing/broken-image fallback. Actual file uploads remain an optional extension: use `ImageField`/Pillow, configure media storage and serving, validate uploads, and bind `request.FILES`. WhiteNoise handles static assets, not user uploads.

- [x] **5. Generate and apply the current migrations.** Listing migrations `0001` and `0002` are applied locally. On another checkout, apply them before opening the new detail page. Generate further migrations after future model changes. Authentication adoption rules in `docs/authentication.md` still apply to legacy databases.

  ```powershell
  .\env\Scripts\python.exe manage.py makemigrations listings
  .\env\Scripts\python.exe manage.py migrate
  ```

- [x] **6. Register `Listing` in Django admin.** Name, seller, price, stock, and creation time are displayed, with category/condition filters and search. Detail fields can be edited in the admin.

- [x] **7. Create and validate `ListingForm`.** An explicit editable-field list excludes seller/timestamps. It supports the new detail fields, Indonesian-formatted prices, nonnegative stock, category/condition choices, and HTTPS photo URLs. Creation assigns the seller from `request.user`.

- [x] **8. Add named routes.** The `listings` namespace includes `index`, `create`, `detail`, `update`, `delete`, and `mine` under `/listings/`. The homepage catalog remains a separate route.

- [x] **9. Implement CRUD and ownership checks.** Creation requires login, update/delete queries require ownership, and My listings filters by the current user. GET deletion only shows confirmation; changes require CSRF-protected POSTs. Missing/unauthorized objects return 404. The login popup preserves safe return destinations.

- [x] **10. Implement the seller screen designs.** The Figma-based item detail, Seller Create Item, Seller Edit Item, and Seller Dashboard pages are implemented. Shared components cover photo previews/fallbacks, validation, notices, and delete/unsaved-change dialogs. The dashboard uses real owned listings and an honest empty shipping state with the Figma demo dialog. See [seller screen notes](seller-screens.md).

- [ ] **11. Connect the homepage catalog to the database.** Update `main.views.show_main` to add real `catalog_items` while preserving `page_context(request)` for authentication notices and SSO state. Adapt `templates/components/catalog-item.html` to the model: it currently expects `image_url` and `price_display`, so supply properties or update those references. Render choice labels while keeping stable category values in `data-category`, preserve `data-catalog-name`, and link each card to its detail page. Replace the fake-item fallback in `templates/index.html` with a real empty state. Check that the existing search and category filters still work; they currently filter only cards already rendered in the browser.

- [ ] **12. Prepare at least 50 sample listings.** This count comes from `README.md`. Use synthetic data with valid categories, sizes, conditions, prices, and seller relationships. A repeatable management command or fixture will make setup easier for teammates. Document how to load it; keep credentials and the local database out of Git.

- [ ] **13. Extend verification as the remaining module work is implemented.** All 69 current tests pass, including ownership, detail viewer states, seller inventory isolation/availability, unchanged edit values, localized prices, validation, and missing objects. Add coverage for homepage integration and any future file uploads; use temporary storage for upload tests. Run:

  ```powershell
  .\env\Scripts\python.exe manage.py check
  .\env\Scripts\python.exe manage.py makemigrations --check --dry-run
  .\env\Scripts\python.exe manage.py test listings
  .\env\Scripts\python.exe manage.py test
  ```

- [ ] **14. Check the complete user journey manually.** Create a listing, see it in the catalog, open its details, edit it, and delete it. Repeat with a guest, its owner, and a different logged-in user. Check desktop/mobile layouts, keyboard and dialog focus, photos, empty states, validation errors, search, and filters. Verify existing local and SSO authentication still works. Update the existing template cache versions for changed CSS/JS.

- [ ] **15. Prepare the change for review.** Document model/migration and photo-storage setup, sample-data loading, and any new environment requirements. Update `AGENTS.md` to reflect implemented behavior. Commit the app, migrations, templates, source assets, and dependency/configuration changes together. Include validation results and screenshots in the PR.
