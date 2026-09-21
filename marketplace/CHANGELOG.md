# Changelog

## V1.2 — Home catalog & frontend polish

- Added a visible Cameroon-oriented category explorer on the home page.
- Added starter catalog data migration so categories/cities/quartiers appear after `migrate` on a fresh database.
- Root category links now include their child-category listings.
- Improved rotating home spotlight with pause-on-hover/focus, previous/next controls and progress indicator.
- Added a favicon to remove the default `/favicon.ico` 404.
- Pinned Alpine.js/HTMX CDN assets to stable versions and moved Alpine/HTMX off jsDelivr.
- Kept mobile overflow prevention and 16px form controls for mobile browsers.

## V1.1 — Final V1 package

- Replaced marketplace token/localStorage identity with real Django session authentication.
- Added per-listing lifetime selection from 1 to 30 days and exact expiration date/time.
- Added automatic expiration + renewal reminder workflow.
- Added owner edit, pause/resume, sold, renew and archive actions.
- Added owner analytics: views, WhatsApp, calls, shares and reports.
- Added HTMX favorites, authentication, listing filters, neighborhoods, reports and notifications.
- Added a favorites page and public profile sharing/reporting.
- Expanded Cameroon-oriented category seed data.
- Added optional PostgreSQL `DATABASE_URL` support and dotenv loading.
- Added Gunicorn production dependency and deployment/testing checklists.
- Kept TailwindCSS + Alpine.js + HTMX architecture with no `app.js` or `app.css`.
