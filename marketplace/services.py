from datetime import timedelta
import hashlib

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.contrib.auth import authenticate, get_user_model
from django.db import transaction
from django.db.models import F
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from .models import Listing, ListingEvent, ListingImage, Notification, PlatformSettings
from .validators import validate_cameroon_phone, normalize_cameroon_phone, validate_image_upload

User = get_user_model()


def request_ip(request):
    return request.META.get("REMOTE_ADDR", "unknown")


def hash_ip(request):
    raw = f"{request_ip(request)}|{settings.SECRET_KEY}".encode()
    return hashlib.sha256(raw).hexdigest()


def enforce_auth_rate_limit(request, identifier):
    key = f"annonce:auth:{request_ip(request)}:{identifier.strip().lower()}"
    count = cache.get(key, 0)
    limit = int(getattr(settings, "PUBLIC_AUTH_MAX_ATTEMPTS_PER_HOUR", 10))
    if count >= limit:
        raise ValidationError("Trop de tentatives. Veuillez réessayer plus tard.")
    cache.set(key, count + 1, 3600)


def enforce_listing_rate_limit(request, user):
    key = f"annonce:listing:{request_ip(request)}:{user.pk}"
    count = cache.get(key, 0)
    limit = int(getattr(settings, "PUBLIC_LISTING_MAX_PER_HOUR", 5))
    if count >= limit:
        raise ValidationError("Vous avez atteint la limite de publications récentes.")
    cache.set(key, count + 1, 3600)


def authenticate_identifier(request, identifier, password):
    identifier = identifier.strip()
    user = User.objects.filter(username__iexact=identifier).first()
    if not user:
        try:
            phone = normalize_cameroon_phone(identifier)
            user = User.objects.filter(phone_number=phone).first()
        except Exception:
            user = None
    if not user:
        return None
    return authenticate(request, username=user.username, password=password)


@transaction.atomic
def create_user_account(*, username, phone_number, password):
    username = username.strip()
    phone_number = validate_cameroon_phone(phone_number)
    if User.objects.filter(username__iexact=username).exists():
        raise ValidationError("Ce nom d'utilisateur est déjà utilisé.")
    if User.objects.filter(phone_number=phone_number).exists():
        raise ValidationError("Ce numéro de téléphone est déjà associé à un compte.")
    user = User(username=username, phone_number=phone_number, display_name=username, last_seen_at=timezone.now())
    user.set_password(password)
    user.full_clean()
    user.save()
    return user


@transaction.atomic
def create_public_listing(*, user, cleaned_data, uploaded_images):
    if not user or not user.is_authenticated:
        raise ValidationError("Connectez-vous pour publier une annonce.")
    if user.is_blocked:
        raise ValidationError("Votre compte ne peut pas publier d'annonce.")

    uploaded_images = list(uploaded_images) or []
    max_images = int(getattr(settings, "PUBLIC_LISTING_MAX_IMAGES", 10))
    if len(uploaded_images) > max_images:
        raise ValidationError(f"Vous pouvez envoyer au maximum {max_images} images.")

    settings_obj = PlatformSettings.load()
    default_days = min(30, settings_obj.listing_days or int(getattr(settings, "PUBLIC_LISTING_DAYS", 30)))
    now = timezone.now()
    duration_days = int(cleaned_data.get("duration_days") or default_days)
    duration_days = max(1, min(30, duration_days))
    expires_at = cleaned_data.get("expires_at") or (now + timedelta(days=duration_days))
    if expires_at > now + timedelta(days=30):
        raise ValidationError("Une annonce ne peut pas dépasser 30 jours de publication.")

    listing = Listing(
        user=user,
        category=cleaned_data["category"],
        city=cleaned_data["city"],
        neighborhood=cleaned_data.get("neighborhood"),
        title=cleaned_data["title"].strip(),
        description=cleaned_data["description"].strip(),
        price=cleaned_data.get("price"),
        price_type=cleaned_data["price_type"],
        condition=cleaned_data["condition"],
        status=Listing.Status.PUBLISHED,
        published_at=now,
        expires_at=expires_at,
        duration_days=duration_days,
    )

# Generate slug BEFORE full_clean().
    listing.generate_slug()

    listing.full_clean()
    listing.save()

    for index, image in enumerate(uploaded_images[:10], start=1):
        validate_image_upload(image)
        ListingImage.objects.create(listing=listing, image=image, position=index, is_cover=(index == 1))
   


    user.last_seen_at = now
    user.save(update_fields=["last_seen_at"])
    return listing


def expire_due_listings(create_notifications=True):
    now = timezone.now()
    due = list(
        Listing.objects.filter(
            status__in=[Listing.Status.PUBLISHED, Listing.Status.PAUSED],
            expires_at__lte=now,
        ).select_related("user")
    )
    changed = 0
    for listing in due:
        listing.status = Listing.Status.EXPIRED
        listing.save(update_fields=["status", "updated_at"])
        changed += 1
        if create_notifications:
            Notification.objects.get_or_create(
                user=listing.user,
                listing=listing,
                kind=Notification.Kind.EXPIRED,
                title="Votre annonce a expiré",
                defaults={
                    "message": f'« {listing.title} » n’est plus publiée. Renouvelez-la pour choisir une nouvelle durée de 1 à 30 jours.',
                    "action_url": reverse("marketplace:owner_listing_detail", kwargs={"slug": listing.slug}),
                },
            )
    return changed


def create_renewal_notifications():
    config = PlatformSettings.load()
    now = timezone.now()
    threshold = now + timedelta(days=config.renewal_notice_days)
    qs = Listing.objects.filter(
        status__in=[Listing.Status.PUBLISHED, Listing.Status.PAUSED],
        expires_at__gt=now,
        expires_at__lte=threshold,
    ).select_related("user")
    created = 0
    for listing in qs:
        exists = Notification.objects.filter(
            user=listing.user,
            listing=listing,
            kind=Notification.Kind.RENEWAL,
            created_at__date=now.date(),
        ).exists()
        if not exists:
            Notification.objects.create(
                user=listing.user,
                listing=listing,
                kind=Notification.Kind.RENEWAL,
                title="Renouvellement bientôt nécessaire",
                message=f'« {listing.title} » expire dans environ {max(1, listing.days_left)} jour(s).',
                action_url=reverse("marketplace:owner_listing_detail", kwargs={"slug": listing.slug}),
            )
            created += 1
    return created


def record_listing_event(request, listing, event_type, platform="", increment_field=None):
    ListingEvent.objects.create(
        listing=listing,
        event_type=event_type,
        platform=platform,
        user=request.user if request.user.is_authenticated else None,
        ip_hash=hash_ip(request),
    )
    if increment_field:
        Listing.objects.filter(pk=listing.pk).update(**{increment_field: F(increment_field) + 1})


def active_boost_subquery():
    from django.db.models import OuterRef, Exists
    from .models import Boost
    now = timezone.now()
    return Exists(
        Boost.objects.filter(
            listing_id=OuterRef("pk"),
            status=Boost.Status.ACTIVE,
            starts_at__lte=now,
            ends_at__gt=now,
        )
    )
