# Marché Local — Django / TailwindCSS / Alpine.js / HTMX

Complete starter platform for local classified listings. It is deliberately **not** an e-commerce cart: no cart, no checkout, no vendor catalog. The core object is an announcement with direct contact.

## Stack

- Django 5.2+
- Pillow
- SQLite by default; optional PostgreSQL through `DATABASE_URL`
- Gunicorn for Linux/production WSGI deployments
- TailwindCSS Play CDN in `templates/base.html` for the zero-build local starter
- Alpine.js and HTMX pinned via CDN in `templates/base.html`
- No `app.js`
- No `app.css`
- Precompiled Tailwind utilities are served from `static/marketplace/tailwind.css`
- Page-specific JavaScript is inline in the relevant template. Shared browser helpers live in `templates/base.html`.

## V1 behavior

### Real authentication

Marketplace users are real Django users. Signup asks for:

- username
- phone number
- password

Login accepts either username **or** phone number plus password. No marketplace tokens or localStorage identity tokens are used.

Authentication uses Django sessions and Django's password hashing. Phone numbers are normalized to a Cameroon-style `+237` format and validated before account creation.

### Posting

Browsing is public. Creating a listing requires login. The create-page submit guard opens the authentication modal when an anonymous visitor tries to publish; after HTMX authentication succeeds, the original multipart form is submitted normally so selected images are preserved.

### Listing lifetime

Each listing chooses its own lifetime at publication time: 1–30 days, or an exact expiration date/time that must remain within the next 30 days. The expiration date is stored on each listing. When due, the listing becomes `expired` and a renewal notification can be created.

Run:

```bash
python manage.py expire_listings
```

For production, run this command from cron or Windows Task Scheduler at least daily.

### Renewal

Owners can edit their listing, pause/resume it, mark it sold, archive it, or renew an expired/sold/paused listing. Renewal accepts a new duration from 1–30 days. Renewal reminders are created before expiry and the daily management command expires due listings.

### Owner analytics

Each listing tracks:

- views
- WhatsApp clicks
- phone clicks
- shares
- reports
- recent interaction events
- favorites through a separate user/listing relation

The owner dashboard also includes a responsive search/filter view, edit access, expiry date, remaining time, and future promotion controls.

Owner pages are server-authorized with Django sessions and `user=request.user` filters. The browser does not decide ownership.

### Reporting

Listing reporting is public and does not require login. User-profile reporting is also available without login.

### Favorites

Authenticated visitors can save active announcements in `/favoris/`. The favorite endpoint is HTMX-powered and server-authorized.

### Social sharing

Listings and profiles can be shared with:

- WhatsApp
- Facebook
- Instagram (link copied, then Instagram opened)
- native device sharing
- copy link

### Monetization toggle

The database includes future commercial models. V1 is free by default.

`PlatformSettings.monetization_enabled` is `False` initially.

When you are ready, set it to `True` in the admin. The future Boost models and plans already exist.

Seeded Boost plans:

- Top 3 jours — 300 XAF
- Top 7 jours — 500 XAF
- Top 14 jours — 1000 XAF

No monthly boost plan is used.

The owner page contains a promotion section only when monetization is enabled. The current checkout endpoint creates a pending `Payment` + `Boost` record but intentionally does not charge money; integrate your provider in `start_boost_checkout()` in `marketplace/views.py`.

### Promotion types

Listings and boost plans support:

- standard
- flash
- urgent
- push

Paid active boosts are ranked above organic listings. Organic listings are then ordered by recency / popularity according to the current view.

### Enterprise advertising

The database already includes:

- `EnterpriseAdPlan`
- `EnterpriseAd`
- `Payment`

`PlatformSettings.enterprise_ads_enabled` controls whether enterprise placements are exposed on the home page.

## Install

```bash
py -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set a production secret.

Then:

```bash
python manage.py migrate
python manage.py seed_marketplace
python manage.py createsuperuser
python manage.py runserver
```

Migration `0003_seed_cameroon_catalog` also inserts the starter Cameroon category/city/quartier catalog, so a fresh database gets visible categories immediately after `migrate`. `seed_marketplace` remains available as an idempotent way to refresh the catalog.

For a Linux production deployment with Gunicorn:

```bash
python manage.py migrate
python manage.py seed_marketplace
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:8000
```

Set `DJANGO_DEBUG=False`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` and enable `DJANGO_USE_HTTPS_SECURITY=True` behind HTTPS. `DATABASE_URL` may be set to a PostgreSQL connection string; without it the project uses SQLite.

Admin:

```text
http://127.0.0.1:8000/control-panel/
```

## Main routes

```text
/                         Home
/health/                  JSON health check
/annonces/                Search/listing page
/annonces/publier/        Publish
/annonces/<slug>/         Public listing
/annonces/<slug>/modifier/ Edit own listing
/favoris/                 Saved listings
/mes-annonces/            Owner listing dashboard
/mes-annonces/<slug>/     Owner detail & analytics
/profil/<username>/       Public profile
/profil/modifier/         Edit profile
/notifications/           In-app notifications
/control-panel/           Django admin
```

## Files intentionally absent

There is deliberately no:

```text
```

The project is organized so that the shared client behavior is in `templates/base.html`, with page-specific Alpine/JavaScript blocks in each page template.

## Payment integration point

The integration point is:

```python
marketplace.views.start_boost_checkout
```

At that point you can:

1. create the payment request with your provider;
2. store the provider reference in `Payment.reference` / `Payment.metadata`;
3. keep the `Boost` as `pending`;
4. on verified provider callback, set `Payment.status = success`, `paid_at`, `Boost.status = active`, `starts_at`, `ends_at`, and set `Listing.promo_type` from the selected plan.

Never activate a boost based only on a browser request. Verify the provider response server-side.

## Validation

The bundle is cleaned of Python cache files and checked for Python syntax, stale token authentication references, and obsolete share endpoint references.

The build environment used to assemble this archive does not have Django installed, so the full Django test suite cannot be executed here. After installing dependencies locally, run:

```bash
python manage.py check
python manage.py test
```


## Project checklists

See `TESTING_CHECKLIST.md` for the local V1 browser/test flow and `DEPLOYMENT_CHECKLIST.md` for production environment, scheduler and security steps.
