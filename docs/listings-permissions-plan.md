# Listing Permissions Plan

Status: implemented. The initial permissions foundation has since been extended with the Figma-based item detail page, optional price/clothing fields, stock, and HTTPS photo URLs. See [item detail notes](item-detail.md) for the current fields, UI states, and validation. Sample-data loading, file uploads, and homepage catalog integration remain later work.

For the first version, any authenticated user can create listings. Buyer and seller are activities of an account, not separate account types. A user becomes the seller of a particular listing by creating it. Password and SSO sessions receive the same listing access. No new user role field, seller group, or permission package is needed for this policy.

| Action | Guest | Logged-in non-owner | Listing owner |
| --- | --- | --- | --- |
| Browse catalog and public listing details | Allowed | Allowed | Allowed |
| View published seller contact details, if provided | Sign in required | Allowed | Allowed |
| Create a listing | Sign in required | Allowed | Allowed |
| View My listings | Sign in required | Own listings only | Own listings only |
| Open edit/delete forms for this listing | Sign in required | Denied | Allowed |
| Submit edits or deletion for this listing | Sign in required | Denied | Allowed |

Staff accounts follow the same ownership rules on marketplace views. Administrative changes belong in Django admin, governed by its existing permissions.

## Implementation order

- [x] **1. Add the ownership field.** `Listing.seller` is a required foreign key to `settings.AUTH_USER_MODEL` with `related_name='listings'`. Deleting a seller cascades to their listings. Future transaction/order retention requirements must be considered before changing account-deletion behavior. `main.User` has no new buyer/seller role fields.

- [x] **2. Separate public and authenticated reads.** `/listings/` and detail pages show public listing fields to guests. My listings filters by `seller=request.user`. Only authenticated detail responses show the optional published contact email; account login email and CAS attributes are never used as contact information. Guests receive no contact values in their HTML. Listing routes serve HTML, with private/no-store cache headers.

- [x] **3. Protect private views with Django authentication.** `login_required` protects create, update, delete, and My listings, including form display and submission. Local and SSO sessions use the same `request.user` checks. Guests are redirected to login before a view can change a listing.

- [x] **4. Preserve the login return destination.** GET login/registration retain a `safe_next()`-validated return URL when opening the homepage popup. `page_context()` passes it to the dialog's `data-next`, and JavaScript uses it for password/registration/profile submissions and SSO links. Popup query flags are removed from the current URL. External destinations fall back to the homepage. A guest opening the create page can sign in and return there; failed POST bodies and uploads are not replayed.

- [x] **5. Assign ownership on the server.** `ListingForm` explicitly lists editable product/contact fields and excludes seller/timestamps. Creation uses `form.save(commit=False)` and `listing.seller = request.user`. Submitted `seller`/`seller_id` fields cannot choose or transfer ownership.

- [x] **6. Enforce ownership in update/delete queries.** Both GET forms and POST submissions fetch objects with an owner filter after authentication:

  ```python
  listing = get_object_or_404(Listing, pk=pk, seller=request.user)
  ```

  A nonexistent listing or another user's listing returns 404 on these protected routes. Avoid staff/superuser bypasses in marketplace views. Deletion requires a CSRF-protected POST; a GET confirmation must not change data. Creation and editing also require CSRF-protected POSTs. Existing Django CSRF middleware stays enabled.

- [x] **7. Reflect the policy in the UI.** The navbar's List an item action opens the create page, and the account menu includes My listings. The public listing index also offers a create link that sends guests through login. Detail pages show edit/delete controls only to the owner. Templates reuse the base layout, login dialog, and CSS tokens.

- [x] **8. Verify the policy with focused tests.** `listings/tests.py` covers guest/owner/non-owner access, staff and superuser denial, published-contact visibility, forged ownership, My listings isolation, form validation, CSRF rejection and valid tokens, safe deletion methods, and missing objects. `main.tests.AuthReturnTests` covers popup return destinations, password/registration and mocked SSO flows, failed SSO, and rejection of external return URLs. All 54 tests passed, along with Django checks and the migration drift check.

Run the listing tests and the existing authentication suite after implementation:

```powershell
.\env\Scripts\python.exe manage.py check
.\env\Scripts\python.exe manage.py test listings
.\env\Scripts\python.exe manage.py test
```

Apply the new schema before running these routes on another checkout:

```powershell
.\env\Scripts\python.exe manage.py migrate
```

For an existing legacy auth database, follow `docs/authentication.md` first. The migration is already applied in this development checkout. No new environment variables or dependencies are required for this permissions foundation.

Routes: `/listings/`, `/listings/create/`, `/listings/mine/`, `/listings/<pk>/`, `/listings/<pk>/edit/`, and `/listings/<pk>/delete/`. The homepage catalog remains a separate placeholder view until the full catalog integration step.

Browser smoke checks on an isolated test database confirmed guest contact restrictions, guest-to-login redirection, keyboard login submission returning to the create form, owner-only management controls, and detail/edit layouts at a 390px mobile viewport. The preview's sample accounts and listings are separate from the development database.
