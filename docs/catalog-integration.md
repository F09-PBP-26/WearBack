# Homepage catalog integration

The homepage (`/`, catalog anchor `/#catalog`) reads all saved `Listing` records from the existing application database, newest first. It preserves the hero, shared navigation, authentication context, and catalog card layout. There is no separate catalog database, external catalog API, or synchronization job.

## Behavior

- Cards display the saved name, rupiah price, photo, size, condition/category labels, and location. Each card links to `/listings/<pk>/`. Missing values use explicit missing-field labels and the existing local photo placeholder. Broken images also fall back to that placeholder.
- All saved listings are visible, including sold-out and unpriced items. Their availability labels match the detail page; purchase controls remain disabled there. The model has no draft state.
- Search is case-insensitive and matches rendered card text. The six category buttons use the model's stable category values and combine with the current search. Filtering is performed in the browser over all rendered listings, without pagination or network requests. Larger catalogs may later need server-side search and pagination together.
- An empty database displays “No items listed yet” and an action to create the first item. This remains distinct from “No items match your filters,” which offers a search/category reset. The reset restores All, clears the search field, and returns keyboard focus to All.
- Creating, editing, or deleting an item is reflected on the next homepage request. The existing ownership checks, CSRF requirements, seller dashboard, and create/edit redirects are preserved.
- Public cards never render seller account or published contact email. Published contact is still available only on authenticated detail pages. A signed-in user's own profile form may contain their account email.
- `/listings/` is retained as a GET-only redirect to `/#catalog`; its old list template is removed. Detail-page and delete-confirmation navigation point directly to the homepage catalog. `/listings/mine/` remains the private seller dashboard.

## Setup and validation

No new model, migration, dependency, or environment variable is required. Existing listing migrations must already be applied. Development data is not seeded or changed by this integration. Generating the 50 sample listings required by the README remains separate work.

The complete Django suite passes 76 tests. Catalog tests cover empty/populated catalogs, multiple sellers, ordering, real fields and links, missing values, availability, contact privacy, create/edit/delete propagation, legacy-route redirects, and preservation of authentication context. Django checks, migration drift checks, JavaScript syntax checks, and whitespace checks pass.

Desktop/mobile browser verification uses an isolated database with synthetic accounts and items. Checks cover all categories, combined search, no-result reset, keyboard card navigation, valid/broken/missing photos, long names without horizontal overflow, login return from details, and newly created/edited items appearing on the homepage. Empty-marketplace behavior is checked separately from filtered no-result behavior.
