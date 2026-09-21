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

- Real Django session authentication with username + Cameroon phone + password.
- Per-listing publication lifetime: 1–30 days or an exact expiry date/time within 30 days.
- Automatic expiration and renewal reminder workflow.
- Owner edit, pause/resume, sold, renew and archive actions.
- Owner analytics for views, WhatsApp, calls, shares and reports.
- HTMX-powered authentication, neighborhood loading, listing filters, favorites, reports and notification updates.
- Favorites page and public profile sharing/reporting.
- Expanded Cameroon-oriented seed categories for services, work, rental, real estate, restaurants and local activities.
- Optional PostgreSQL via `DATABASE_URL` and `.env` loading through python-dotenv.
- Gunicorn dependency and deployment/testing checklists.
- No `app.js` or `app.css`.
\n## 1.4.0\n- Fixed profile/modifier/ route precedence.\n- Added separate owner listing statistics page.\n- Fixed listing form required-field handling and city/quartier fallback.\n- Added persistent server-rendered duration value so Alpine failure cannot blank duration_days.\n- Added local compiled Tailwind CSS; removed Tailwind CDN warning.\n- Added logo.png slot in static and enhanced mobile auth modal scrolling.\n- Added category selector to homepage hero search.\n