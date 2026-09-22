from django.contrib.auth import get_user_model
from django.contrib.sitemaps import Sitemap
from django.db.models import Max
from django.urls import reverse
from django.utils import timezone

from .models import Listing


class StaticSitemap(Sitemap):
    changefreq = "daily"
    priority = 1.0

    def items(self):
        return ["home", "listing_list"]

    def location(self, item):
        if item == "home":
            return reverse("marketplace:home")
        return reverse("marketplace:listing_list")

    def priority(self, item):
        return 1.0 if item == "home" else 0.9


class ListingSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.8

    def items(self):
        return (
            Listing.objects
            .select_related("user", "category", "city", "neighborhood")
            .filter(
                status=Listing.Status.PUBLISHED,
                expires_at__gt=timezone.now(),
                user__is_active=True,
                user__is_blocked=False,
            )
            .order_by("pk")
        )

    def lastmod(self, obj):
        return obj.updated_at or obj.published_at or obj.created_at

    def location(self, obj):
        return obj.get_absolute_url()


class ProfileSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        User = get_user_model()
        return (
            User.objects
            .filter(
                is_active=True,
                is_blocked=False,
                listings__status=Listing.Status.PUBLISHED,
                listings__expires_at__gt=timezone.now(),
            )
            .annotate(last_listing_update=Max("listings__updated_at"))
            .distinct()
            .order_by("pk")
        )

    def lastmod(self, obj):
        return obj.last_listing_update or obj.last_seen_at or obj.date_joined

    def location(self, obj):
        return obj.get_absolute_url()


SITEMAPS = {
    "static": StaticSitemap,
    "listings": ListingSitemap,
    "profiles": ProfileSitemap,
}
