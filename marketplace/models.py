from datetime import timedelta
from decimal import Decimal
import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from .validators import normalize_cameroon_phone, validate_cameroon_phone, validate_image_upload


def listing_default_expiry():
    return timezone.now() + timedelta(days=getattr(settings, "PUBLIC_LISTING_DAYS", 30))


def listing_image_upload_path(instance, filename):
    extension = filename.rsplit(".", 1)[-1].lower()
    return f"listings/{timezone.now():%Y/%m}/{instance.listing_id}/{uuid.uuid4().hex}.{extension}"


def avatar_upload_path(instance, filename):
    extension = filename.rsplit(".", 1)[-1].lower()
    return f"avatars/{instance.pk or 'new'}/{uuid.uuid4().hex}.{extension}"


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class User(AbstractUser):
    REQUIRED_FIELDS = ["phone_number"]
    phone_number = models.CharField(max_length=20, unique=True)
    display_name = models.CharField(max_length=120, blank=True)
    bio = models.TextField(max_length=1200, blank=True)
    avatar = models.ImageField(upload_to=avatar_upload_path, blank=True, null=True, validators=[validate_image_upload])
    city = models.ForeignKey("City", on_delete=models.SET_NULL, null=True, blank=True, related_name="users")
    is_blocked = models.BooleanField(default=False)
    blocked_reason = models.TextField(blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    show_phone = models.BooleanField(default=False)

    class Meta:
        ordering = ["username"]
        indexes = [
            models.Index(fields=["phone_number", "is_blocked"]),
            models.Index(fields=["username"]),
        ]
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"

    def clean(self):
        super().clean()
        self.phone_number = normalize_cameroon_phone(self.phone_number)
        self.display_name = (self.display_name or "").strip()
        if not self.phone_number:
            raise ValidationError({"phone_number": "Le numéro de téléphone est obligatoire."})
        try:
            validate_cameroon_phone(self.phone_number)
        except ValidationError as exc:
            raise ValidationError({"phone_number": exc.messages}) from exc

    def save(self, *args, **kwargs):
        self.phone_number = normalize_cameroon_phone(self.phone_number)
        if not self.display_name:
            self.display_name = self.username
        super().save(*args, **kwargs)

    @property
    def public_name(self):
        return self.display_name or self.username

    @property
    def whatsapp_number(self):
        return self.phone_number.replace("+", "")

    def get_absolute_url(self):
        return reverse("marketplace:profile", kwargs={"username": self.username})

    def __str__(self):
        return self.username


class Category(TimeStampedModel):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "name"]
        indexes = [models.Index(fields=["is_active", "position"])]
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"

    def __str__(self):
        return self.name


class City(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    region = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Ville"
        verbose_name_plural = "Villes"

    def __str__(self):
        return self.name


class Neighborhood(TimeStampedModel):
    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name="neighborhoods")
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["city", "slug"], name="unique_neighborhood_per_city")]
        verbose_name = "Quartier"
        verbose_name_plural = "Quartiers"

    def __str__(self):
        return f"{self.name} — {self.city.name}"


class PlatformSettings(TimeStampedModel):
    singleton_key = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)
    site_name = models.CharField(max_length=120, default="Marché Local")
    tagline = models.CharField(max_length=180, default="Trouvez. Vendez. Partagez.")
    monetization_enabled = models.BooleanField(default=False)
    enterprise_ads_enabled = models.BooleanField(default=False)
    listing_days = models.PositiveIntegerField(default=30, validators=[MinValueValidator(1), MaxValueValidator(30)])
    renewal_notice_days = models.PositiveIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(30)])
    support_whatsapp = models.CharField(max_length=20, blank=True)

    class Meta:
        verbose_name = "Configuration plateforme"
        verbose_name_plural = "Configuration plateforme"

    def save(self, *args, **kwargs):
        self.singleton_key = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(singleton_key=1)
        return obj


class Listing(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Brouillon"
        PUBLISHED = "published", "Publié"
        PAUSED = "paused", "En pause"
        SOLD = "sold", "Vendu"
        EXPIRED = "expired", "Expiré"
        REJECTED = "rejected", "Refusé"
        SUSPENDED = "suspended", "Suspendu"
        ARCHIVED = "archived", "Archivé"

    class PriceType(models.TextChoices):
        FIXED = "fixed", "Prix fixe"
        NEGOTIABLE = "negotiable", "Négociable"
        FREE = "free", "Gratuit"
        CONTACT = "contact", "Prix sur demande"

    class Condition(models.TextChoices):
        NEW = "new", "Neuf"
        USED = "used", "Occasion"
        GOOD = "good", "Très bon état"
        REFURBISHED = "refurbished", "Reconditionné"
        NOT_APPLICABLE = "na", "Non applicable"

    class PromoType(models.TextChoices):
        STANDARD = "standard", "Standard"
        FLASH = "flash", "Flash"
        URGENT = "urgent", "Urgent"
        PUSH = "push", "Push"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="listings")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="listings")
    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name="listings")
    neighborhood = models.ForeignKey(Neighborhood, on_delete=models.PROTECT, related_name="listings", null=True, blank=True)
    title = models.CharField(max_length=180)
    slug = models.SlugField(max_length=240, unique=True)
    description = models.TextField(max_length=5000)
    price = models.DecimalField(max_digits=14, decimal_places=0, null=True, blank=True, validators=[MinValueValidator(Decimal("0"))])
    currency = models.CharField(max_length=3, default="XAF")
    price_type = models.CharField(max_length=20, choices=PriceType.choices, default=PriceType.CONTACT)
    condition = models.CharField(max_length=20, choices=Condition.choices, default=Condition.NOT_APPLICABLE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    promo_type = models.CharField(max_length=20, choices=PromoType.choices, default=PromoType.STANDARD)
    duration_days = models.PositiveIntegerField(default=30, validators=[MinValueValidator(1), MaxValueValidator(30)])
    published_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(default=listing_default_expiry)
    renewed_at = models.DateTimeField(null=True, blank=True)
    sold_at = models.DateTimeField(null=True, blank=True)
    moderation_note = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    views_count = models.PositiveIntegerField(default=0)
    whatsapp_clicks = models.PositiveIntegerField(default=0)
    call_clicks = models.PositiveIntegerField(default=0)
    share_count = models.PositiveIntegerField(default=0)
    report_count = models.PositiveIntegerField(default=0)
    last_viewed_at = models.DateTimeField(null=True, blank=True)
    meta_title = models.CharField(max_length=180, blank=True)
    meta_description = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]
        indexes = [
            models.Index(fields=["status", "-published_at"]),
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["category", "status"]),
            models.Index(fields=["city", "status"]),
            models.Index(fields=["promo_type", "status"]),
        ]
        verbose_name = "Annonce"
        verbose_name_plural = "Annonces"

    def clean(self):
        super().clean()
        if self.duration_days < 1 or self.duration_days > 30:
            raise ValidationError({"duration_days": "La durée doit être comprise entre 1 et 30 jours."})
        if self.category_id and not self.category.is_active:
            raise ValidationError({"category": "Cette catégorie n'est plus disponible."})
        if self.city_id and not self.city.is_active:
            raise ValidationError({"city": "Cette ville n'est plus disponible."})
        if self.neighborhood_id and self.neighborhood.city_id != self.city_id:
            raise ValidationError({"neighborhood": "Le quartier doit appartenir à la ville sélectionnée."})
        if self.neighborhood_id and not self.neighborhood.is_active:
            raise ValidationError({"neighborhood": "Ce quartier n'est plus disponible."})
        if self.price_type == self.PriceType.FIXED and self.price is None:
            raise ValidationError({"price": "Un prix est requis pour un prix fixe."})
        if self.price_type in {self.PriceType.FREE, self.PriceType.CONTACT}:
            self.price = None

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title) or "annonce"
            self.slug = f"{base[:205]}-{self.public_id.hex[:8]}"
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("marketplace:listing_detail", kwargs={"slug": self.slug})

    @property
    def is_active(self):
        return self.status == self.Status.PUBLISHED and self.expires_at > timezone.now()

    @property
    def days_left(self):
        if self.expires_at <= timezone.now():
            return 0
        return max(0, (self.expires_at - timezone.now()).days)

    def mark_sold(self):
        self.status = self.Status.SOLD
        self.sold_at = timezone.now()
        self.save(update_fields=["status", "sold_at", "updated_at"])

    def renew(self, days=None):
        days = int(days or self.duration_days or PlatformSettings.load().listing_days or settings.PUBLIC_LISTING_DAYS)
        days = max(1, min(30, days))
        now = timezone.now()
        self.status = self.Status.PUBLISHED
        self.published_at = now
        self.expires_at = now + timedelta(days=days)
        self.renewed_at = now
        self.sold_at = None
        self.save(update_fields=["status", "published_at", "expires_at", "renewed_at", "sold_at", "updated_at"])

    def __str__(self):
        return self.title


class ListingImage(TimeStampedModel):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to=listing_image_upload_path, validators=[validate_image_upload])
    position = models.PositiveIntegerField(default=0)
    is_cover = models.BooleanField(default=False)

    class Meta:
        ordering = ["position", "created_at"]
        constraints = [
            models.UniqueConstraint(fields=["listing", "position"], name="unique_listing_image_position"),
            models.UniqueConstraint(fields=["listing"], condition=Q(is_cover=True), name="unique_listing_cover_image"),
        ]
        verbose_name = "Image d'annonce"
        verbose_name_plural = "Images d'annonce"


class ListingEvent(TimeStampedModel):
    class Type(models.TextChoices):
        VIEW = "view", "Vue"
        WHATSAPP = "whatsapp", "WhatsApp"
        CALL = "call", "Appel"
        SHARE = "share", "Partage"
        COPY = "copy", "Copie du lien"
        REPORT = "report", "Signalement"

    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=20, choices=Type.choices)
    platform = models.CharField(max_length=30, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="listing_events")
    ip_hash = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["listing", "event_type", "-created_at"])]


class ContactEvent(TimeStampedModel):
    class Type(models.TextChoices):
        WHATSAPP = "whatsapp", "WhatsApp"
        CALL = "call", "Appel"

    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="contact_events")
    event_type = models.CharField(max_length=20, choices=Type.choices)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="contact_events")


class ShareEvent(TimeStampedModel):
    class Platform(models.TextChoices):
        WHATSAPP = "whatsapp", "WhatsApp"
        FACEBOOK = "facebook", "Facebook"
        INSTAGRAM = "instagram", "Instagram"
        COPY = "copy", "Copie du lien"
        NATIVE = "native", "Partage natif"
        OTHER = "other", "Autre"

    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="share_events")
    platform = models.CharField(max_length=20, choices=Platform.choices)


class Favorite(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites")
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="favorites")

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "listing"], name="unique_favorite_per_user_listing"),
        ]
        indexes = [models.Index(fields=["user", "-created_at"])]
        verbose_name = "Favori"
        verbose_name_plural = "Favoris"


class ProfileShareEvent(TimeStampedModel):
    class Platform(models.TextChoices):
        WHATSAPP = "whatsapp", "WhatsApp"
        FACEBOOK = "facebook", "Facebook"
        INSTAGRAM = "instagram", "Instagram"
        COPY = "copy", "Copie du lien"
        NATIVE = "native", "Partage natif"
        OTHER = "other", "Autre"

    profile = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile_share_events")
    platform = models.CharField(max_length=20, choices=Platform.choices)


class Report(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Ouvert"
        REVIEWED = "reviewed", "Examiné"
        ACTIONED = "actioned", "Action effectuée"
        DISMISSED = "dismissed", "Classé sans suite"

    class Reason(models.TextChoices):
        SCAM = "scam", "Arnaque présumée"
        PROHIBITED = "prohibited", "Contenu interdit"
        FALSE_INFO = "false_info", "Fausse information"
        SPAM = "spam", "Spam"
        SOLD = "sold", "Déjà vendu"
        OTHER = "other", "Autre"

    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="reports")
    reason = models.CharField(max_length=30, choices=Reason.choices)
    message = models.TextField(max_length=2000, blank=True)
    reporter_phone = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    admin_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]


class UserReport(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Ouvert"
        REVIEWED = "reviewed", "Examiné"
        ACTIONED = "actioned", "Action effectuée"
        DISMISSED = "dismissed", "Classé sans suite"

    target_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="received_reports")
    reporter_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="submitted_user_reports")
    reporter_phone = models.CharField(max_length=20, blank=True)
    reason = models.CharField(max_length=80)
    message = models.TextField(max_length=2000, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    admin_note = models.TextField(blank=True)


class Notification(TimeStampedModel):
    class Kind(models.TextChoices):
        RENEWAL = "renewal", "Renouvellement"
        EXPIRED = "expired", "Annonce expirée"
        SYSTEM = "system", "Système"
        MODERATION = "moderation", "Modération"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="notifications", null=True, blank=True)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.SYSTEM)
    title = models.CharField(max_length=180)
    message = models.TextField(max_length=1000)
    action_url = models.CharField(max_length=500, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["is_read", "-created_at"]
        indexes = [models.Index(fields=["user", "is_read", "-created_at"])]


class BoostPlan(TimeStampedModel):
    name = models.CharField(max_length=100)
    duration_days = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(30)])
    price = models.DecimalField(max_digits=12, decimal_places=0, validators=[MinValueValidator(Decimal("0"))])
    currency = models.CharField(max_length=3, default="XAF")
    is_active = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)
    badge = models.CharField(max_length=30, blank=True)
    promotion_type = models.CharField(max_length=20, choices=Listing.PromoType.choices, default=Listing.PromoType.PUSH)

    class Meta:
        ordering = ["position", "price"]


class Payment(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        SUCCESS = "success", "Réussi"
        FAILED = "failed", "Échec"
        CANCELLED = "cancelled", "Annulé"
        REFUNDED = "refunded", "Remboursé"

    provider = models.CharField(max_length=50, default="future")
    reference = models.CharField(max_length=150, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payments", null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=0)
    currency = models.CharField(max_length=3, default="XAF")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    metadata = models.JSONField(default=dict, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)


class Boost(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        ACTIVE = "active", "Actif"
        EXPIRED = "expired", "Expiré"
        CANCELLED = "cancelled", "Annulé"

    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="boosts")
    plan = models.ForeignKey(BoostPlan, on_delete=models.PROTECT, related_name="boosts")
    payment = models.OneToOneField(Payment, on_delete=models.PROTECT, related_name="boost", null=True, blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "ends_at"])]

    @property
    def is_active(self):
        now = timezone.now()
        return self.status == self.Status.ACTIVE and self.starts_at and self.ends_at and self.starts_at <= now < self.ends_at


class EnterpriseAdPlan(TimeStampedModel):
    name = models.CharField(max_length=120)
    duration_days = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(365)])
    price = models.DecimalField(max_digits=12, decimal_places=0, validators=[MinValueValidator(Decimal("0"))])
    currency = models.CharField(max_length=3, default="XAF")
    is_active = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)


class EnterpriseAd(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Brouillon"
        PENDING = "pending", "En attente"
        ACTIVE = "active", "Actif"
        EXPIRED = "expired", "Expiré"
        REJECTED = "rejected", "Refusé"

    business_name = models.CharField(max_length=180)
    title = models.CharField(max_length=180)
    description = models.TextField(max_length=2000, blank=True)
    image = models.ImageField(upload_to="enterprise/", blank=True, null=True, validators=[validate_image_upload])
    target_url = models.URLField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    plan = models.ForeignKey(EnterpriseAdPlan, on_delete=models.PROTECT, null=True, blank=True)
    payment = models.OneToOneField(Payment, on_delete=models.PROTECT, null=True, blank=True, related_name="enterprise_ad")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "-created_at"]


class SupportMessage(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="support_messages")
    name = models.CharField(max_length=120)
    phone_number = models.CharField(max_length=20, blank=True)
    message = models.TextField(max_length=3000)
    is_resolved = models.BooleanField(default=False)
