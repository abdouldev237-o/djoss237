from pathlib import Path
import os
from urllib.parse import unquote

from dotenv import load_dotenv

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


DEBUG = env_bool("DJANGO_DEBUG", True)
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-annonce-platform-secret-change-me"
    else:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY is required when DEBUG=False")

ALLOWED_HOSTS = [x.strip() for x in os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost,djoss237.vercel.app,.vercel.app").split(",") if x.strip()]
CSRF_TRUSTED_ORIGINS = [x.strip() for x in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if x.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "marketplace",
    'cloudinary',
    'cloudinary_storage'
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "marketplace.context_processors.marketplace_context",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
import dj_database_url

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# Vercel provides DATABASE_URL as a PostgreSQL URI. Keep the fallback local so
# Django's management commands can still run when the variable is unavailable.
if DATABASE_URL.startswith(("postgres://", "postgresql://")):
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=0,
            ssl_require=True,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "marketplace.User"
LOGIN_URL = "/?auth=required"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Douala"
USE_I18N = True
USE_TZ = True

SITE_NAME = os.getenv("DJANGO_SITE_NAME", "Djoss237").strip() or "Djoss237"
SITE_URL = os.getenv("DJANGO_SITE_URL", "").strip().rstrip("/")
GOOGLE_SITE_VERIFICATION = os.getenv("GOOGLE_SITE_VERIFICATION", "").strip()
BING_SITE_VERIFICATION = os.getenv("BING_SITE_VERIFICATION", "").strip()
INDEXNOW_KEY = os.getenv("INDEXNOW_KEY", "").strip()
INDEXNOW_ENABLED = env_bool("DJANGO_INDEXNOW_ENABLED", False)
SEO_DEFAULT_DESCRIPTION = os.getenv(
    "SEO_DEFAULT_DESCRIPTION",
    "Djoss237 — annonces locales au Cameroun : immobilier, véhicules, téléphones, services, emploi, restauration, agriculture et plus.",
).strip()


STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30
CSRF_COOKIE_SAMESITE = "Lax"

USE_HTTPS_SECURITY = env_bool("DJANGO_USE_HTTPS_SECURITY", False)
if USE_HTTPS_SECURITY:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_HSTS_SECONDS = 0

FILE_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 40 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 250

PUBLIC_LISTING_DAYS = int(os.getenv("PUBLIC_LISTING_DAYS", "30"))
PUBLIC_LISTING_MAX_IMAGES = int(os.getenv("PUBLIC_LISTING_MAX_IMAGES", "10"))
PUBLIC_LISTING_MAX_PER_HOUR = int(os.getenv("PUBLIC_LISTING_MAX_PER_HOUR", "5"))
PUBLIC_AUTH_MAX_ATTEMPTS_PER_HOUR = int(os.getenv("PUBLIC_AUTH_MAX_ATTEMPTS_PER_HOUR", "10"))
MONETIZATION_ENABLED = env_bool("DJANGO_MONETIZATION_ENABLED", False)
ENTERPRISE_ADS_ENABLED = env_bool("DJANGO_ENTERPRISE_ADS_ENABLED", False)

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "annonce-platform-cache",
    }
}


import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url

CLOUDINARY_STORAGE = { 
    "CLOUD_NAME":os.getenv('CLOUDINARY_CLOUD_NAME'),
    "API_KEY":os.getenv('CLOUDINARY_API_KEY'),
    "API_SECRET" :os.getenv('CLOUDINARY_API_SECRET')
}

cloudinary.config( 
    cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME'), 
    api_key = os.getenv('CLOUDINARY_API_KEY'), 
    api_secret = os.getenv('CLOUDINARY_API_SECRET'),
    secure=True
)
# Configuration       


STORAGES = {
    "default":{
        "BACKEND":"cloudinary_storage.storage.MediaCloudinaryStorage"
    },
    "staticfiles":{
        "BACKEND":"whitenoise.storage.CompressedManifestStaticFilesStorage"
    }
}
