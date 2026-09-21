# Marché Local — Testing checklist

## Local smoke test

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# Linux/macOS
# source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python manage.py check
python manage.py migrate
python manage.py seed_marketplace
python manage.py test
python manage.py runserver
```

Open:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/health/`
- `http://127.0.0.1:8000/control-panel/`

## Browser flow

1. Browse `/annonces/` without an account.
2. Try `Publier` while logged out: the auth modal should open.
3. Create an account with username + Cameroon phone + password.
4. Publish an announcement for 1, 3, 7, 14, 21 or 30 days.
5. Publish another announcement using an exact expiration date/time within 30 days.
6. Upload up to 10 images and check the mobile preview.
7. Check the public detail page, WhatsApp, phone, share and report actions.
8. Log in with username and then with phone number.
9. Check `Mes annonces`, `Favoris`, `Notifications` and the public profile.
10. From the owner page, edit, pause/resume, mark sold, renew and archive an announcement.
11. Verify that another account cannot open or modify the owner's management URL.
12. Run `python manage.py expire_listings` with a due listing and verify the renewal/expiration notification.

## Monetization later

Keep `PlatformSettings.monetization_enabled=False` during V1 launch.

When the payment provider is connected:

1. Set the platform switch to `True`.
2. Activate the desired `BoostPlan` rows.
3. Replace the future checkout logic in `start_boost_checkout()` with the provider integration.
4. Activate `Boost` only after a verified provider success callback.
5. Keep all payment references and provider metadata server-side.

Do not trust a browser-supplied amount, price, promotion or payment status.
