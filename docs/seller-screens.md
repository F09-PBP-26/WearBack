# Seller screens

The seller pages implement the [Seller Dashboard](https://www.figma.com/design/hFYuWw7axnXovzTp1jMn6w/WearBack-UI-UX-Implement?node-id=1-151), [Seller Create Item](https://www.figma.com/design/hFYuWw7axnXovzTp1jMn6w/WearBack-UI-UX-Implement?node-id=1-115), and [Seller Edit Item](https://www.figma.com/design/hFYuWw7axnXovzTp1jMn6w/WearBack-UI-UX-Implement?node-id=1-214) frames using Django templates and plain CSS/JavaScript. The existing shared navbar and footer retain their styling.

- `/listings/mine/` shows only the signed-in seller's items, actual counts, prices, clothing details, detail links, and edit controls. Missing prices show “Needs details”; zero stock shows “Sold out.” There is no draft state in the model. An empty shop offers a first-item action.
- `/listings/create/` and `/listings/<pk>/edit/` share the Figma photo sidebar and item-details card. The size dropdown preserves existing custom values, and prices display in Indonesian format without changing their stored value on an unchanged save.
- Photo previews update from direct HTTPS URLs, with empty, loading, invalid-URL, and failed-image messages. Dashboard photos fall back to the local placeholder. Image uploads are not implemented.
- Additional stock, brand, material, style, location, and published-contact fields remain available under “More item details.” The panel opens when one of its fields fails validation. Published contact visibility continues to follow the existing authentication rules.
- Failed submissions retain entered values and show a focusable error summary with links to fields. Successful create/edit actions keep the existing redirect to item details and display a success notice. Save buttons prevent repeat submissions.
- Cancel and the dashboard back link ask before leaving a changed form. Other navigation uses the browser's unsaved-change prompt. Owner deletion uses the existing CSRF-protected confirmation flow, with the confirmation page as the no-JavaScript fallback.
- “Ready to ship” shows an empty state until checkout/orders are integrated. “Try Insta ship demo” opens the Figma confirmation dialog; it does not create shipments, book couriers, or mutate orders. Example paid orders from the mockup are not displayed as real transactions.

Shared seller markup lives in `templates/listings/seller-base.html` and the `seller-field.html` / `seller-status.html` component partials. Styles live in `static/css/seller.css`; interactions extend `static/js/listings.js`. The dropdown chevron and edit icon are downloaded Figma SVGs with their original 18px and 20px geometry.

No additional migration or dependency is needed for this redesign. Apply listing migration `0002` from the item-detail implementation when upgrading from the permissions milestone. The homepage still uses placeholder catalog items; saved items are available through `/listings/`, the seller dashboard, and their detail routes.

Validation includes the complete 69-test Django suite, Django system/migration checks, JavaScript syntax checks, and desktop/mobile browser checks of the seller flows using an isolated test database.
