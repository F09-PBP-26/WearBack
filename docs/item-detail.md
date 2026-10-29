# Item Detail Page

The page at `/listings/<pk>/` implements [Item details / Buyer in Figma](https://www.figma.com/design/hFYuWw7axnXovzTp1jMn6w/WearBack-UI-UX-Implement?node-id=4-459) using Django templates, existing CSS tokens, and plain JavaScript. It reuses the project's shared navbar and footer. Those existing shared components retain their current styling.

## Implemented behavior

- Responsive photo/purchase and specification/seller cards follow the Figma layout.
- Guests see public information and sign-in actions. Published contact email appears only after login.
- Customers can adjust quantity from one to the available stock. Add to cart opens the existing coming-soon dialog; it does not create a cart item or order.
- Owners see Edit/Delete controls. The delete dialog requires confirmation and posts with CSRF to the existing ownership-protected endpoint. Without JavaScript, its link opens the existing confirmation page.
- Zero stock shows a sold-out state. An absent price shows an unavailable state. Older listings display clear missing-field values without fabricated prices or specifications.
- Photos use an HTTPS URL entered by the seller. Missing or failed images display the local placeholder downloaded from Figma. User photos remain dynamic; the design screenshot is not used as a page asset.
- Seller listing counts come from the database. Ratings show an empty state until the reviews module is integrated.
- Create/update/delete success messages are dismissible. Dialogs support keyboard cancellation and return focus to their trigger.

New partials are `item-photo.html`, `item-specifications.html`, `item-seller.html`, `item-delete-dialog.html`, and `listing-notices.html` under `templates/components/`. Page interactions live in `static/js/listings.js`; the shared cart binder now supports multiple triggers and restores focus to the trigger used.

## Data and setup

The new migration adds optional price, photo URL, category, size, condition, brand, material, style, and location fields, plus stock defaulting to one. Existing data is retained. The Figma-based create/edit forms and Django admin expose these values so the detail page can display real information. See [seller screen notes](seller-screens.md).

```powershell
.\env\Scripts\python.exe manage.py migrate
```

Prices use `Decimal` and must be positive when supplied. The form accepts plain decimal values and Indonesian formatting, for example `300000`, `300.000`, and `1.234.567,50`. Display uses rupiah separators. Stock accepts whole numbers from zero to 9,999. Set stock to zero to mark an item unavailable. Model relations and ownership remain unchanged.

No new dependency or environment variable is required. The [homepage catalog](catalog-integration.md) now links to saved item details, and Browse items returns to `/#catalog`. Photo upload/storage, checkout/orders, and review statistics are separate work.

## Validation

The full Django suite passes 76 tests, including seller-screen and homepage catalog regressions. Detail coverage checks fields and viewer states, contact privacy, real seller counts, unavailable/legacy listings, localized prices, new-field validation, and the positive-price database constraint. Django checks, migration drift checks, and JavaScript syntax checks pass.

Browser checks used an isolated preview database: desktop and 390px mobile layouts; guest-to-buyer login; bounded quantity input; cart cancellation/focus; failed and valid photos; sold-out items; long text without horizontal overflow; owner-only delete confirmation/cancellation; and saving localized prices with dismissible success messages. The preview uses test accounts and does not seed the development database.
