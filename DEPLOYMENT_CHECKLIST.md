# Marché Local — Deployment checklist

## Required environment

Set:

```env
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=replace-with-a-long-random-secret
DJANGO_ALLOWED_HOSTS=example.com,www.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://example.com,https://www.example.com
DJANGO_USE_HTTPS_SECURITY=True
DJANGO_MONETIZATION_ENABLED=False
DJANGO_ENTERPRISE_ADS_ENABLED=False
```

For PostgreSQL, also set:

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DATABASE?sslmode=require
```

Without `DATABASE_URL`, the project uses SQLite.

## Commands

```bash
python manage.py migrate
python manage.py seed_marketplace
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:8000
```

## Expiration scheduler

Run this at least once per day:

```bash
python manage.py expire_listings
```

Use cron, a platform scheduler, or Windows Task Scheduler.

The command both expires due listings and creates renewal reminders.

## Media/static

Tailwind utilities are precompiled into `static/marketplace/tailwind.css`; Alpine.js, HTMX and Lucide remain CDN-loaded. There is intentionally no `app.css` or `app.js`. For a deployment that must also work without Internet access, vendor Alpine.js, HTMX and Lucide into `static/vendor/`.

Production media uploads under `/media/` must be served by the deployment platform or a reverse proxy/object storage. Do not commit user-uploaded media to Git.

## Security

- Keep `DJANGO_DEBUG=False` in production.
- Use HTTPS and `DJANGO_USE_HTTPS_SECURITY=True`.
- Use a strong secret key.
- Restrict `DJANGO_ALLOWED_HOSTS`.
- Set trusted CSRF origins for the production domains.
- Never activate a boost from a browser-only success response.
- Keep owner authorization on the server using `request.user` and object ownership filters.
