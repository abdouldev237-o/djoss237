#!/bin/bash

# Install dependencies
python3 -m pip install -r requirements.txt

# Collect static files (Vercel auto-runs this if STATIC_ROOT is set, but explicit is safer)
python3 manage.py collectstatic --noinput

# Run database migrations
python3 manage.py migrate --noinput

python3 manage.py seed_marketplace

# python manage.py submit_indexnow --all-active