from django.conf import settings

from .models import Notification, PlatformSettings


def marketplace_context(request):
    config = PlatformSettings.load()
    unread = 0
    if request.user.is_authenticated:
        unread = Notification.objects.filter(user=request.user, is_read=False).count()

    configured_site_url = getattr(settings, "SITE_URL", "").strip().rstrip("/")
    canonical_url = (
        f"{configured_site_url}{request.path}"
        if configured_site_url
        else request.build_absolute_uri(request.path)
    )
    site_url = configured_site_url or request.build_absolute_uri("/").rstrip("/")

    return {
        "platform_settings": config,
        "unread_notifications": unread,
        "site_name": getattr(settings, "SITE_NAME", "Djoss237"),
        "site_url": site_url,
        "canonical_url": canonical_url,
        "seo_default_description": getattr(
            settings,
            "SEO_DEFAULT_DESCRIPTION",
            "Djoss237 — annonces locales au Cameroun.",
        ),
        "google_site_verification": getattr(settings, "GOOGLE_SITE_VERIFICATION", ""),
        "bing_site_verification": getattr(settings, "BING_SITE_VERIFICATION", ""),
    }
