# Extension notes

## Where shared browser code lives

`templates/base.html`

Contains:

- Tailwind CDN
- Alpine.js CDN
- HTMX CDN
- Lucide CDN
- CSRF helper
- toast helper
- share helper
- copy helper
- HTMX lifecycle hooks
- authentication lifecycle hooks

## Where page behavior lives

Each page keeps its own small Alpine component / script:

- `home.html` — hero carousel
- `listing_form.html` — submit auth guard, image preview, description counter
- `listing_detail.html` — gallery, share, report modal
- `my_listings.html` — search/filter
- `owner_listing_detail.html` — confirmation + future boost checkout
- `profile.html` — profile sharing/report modal

## Authentication lifecycle

1. Anonymous user opens login/signup modal.
2. HTMX loads `auth_login.html` or `auth_signup.html`.
3. `login_htmx` / `signup_htmx` performs normal Django authentication.
4. Response uses `hx-swap-oob` to update:
   - `#headerNavAccountSlot`
   - `#authHeaderSlot`
5. `HX-Trigger: marketplace-authenticated` tells the current page that authentication is complete.
6. The base-page listener closes the modal and resumes a pending publication form when one exists.

## Expiration worker

`python manage.py expire_listings`

The command handles both due listings and renewal reminders. In production it should be scheduled once daily.

## Commercial switch

Admin model:

`PlatformSettings.monetization_enabled`

Default:

`False`

Do not trust a front-end flag for charging or boost activation. The backend decides whether commercial features are enabled.


## Finalization notes

- Authentication is Django session auth: username + Cameroon phone number + password.
- Listing lifetime is selected per post, from 1 to 30 days, or an exact date/time within 30 days.
- `marketplace:edit_listing` reuses the publication form and appends new photos without exceeding the 10-photo limit.
- Favorites are available at `/favoris/` and require login.
- `/health/` is a JSON smoke-check endpoint.
- `DATABASE_URL` is optional; PostgreSQL is used when a postgres URL is provided, otherwise SQLite is used.
- No `app.js` or `app.css` is part of the project.
