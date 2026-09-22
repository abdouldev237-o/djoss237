from django.conf import settings
from django.http import Http404, HttpResponse
from django.utils.cache import patch_cache_control


def site_origin(request):
    configured = getattr(settings, "SITE_URL", "").strip().rstrip("/")
    if configured:
        return configured
    return request.build_absolute_uri("/").rstrip("/")


def robots_txt(request):
    origin = site_origin(request)
    sitemap = f"{origin}/sitemap.xml"

    body = "\n".join(
        [
            "# Djoss237 — robots.txt",
            "# Public content is crawlable; private/account areas are not.",
            "",
            "User-agent: *",
            "Allow: /",
            "Disallow: /control-panel/",
            "Disallow: /connexion/",
            "Disallow: /inscription/",
            "Disallow: /deconnexion/",
            "Disallow: /htmx/",
            "Disallow: /mes-annonces/",
            "Disallow: /favoris/",
            "Disallow: /notifications/",
            "Disallow: /profil/modifier/",
            "",
            "# Allow OpenAI Search/Ads crawlers to discover public pages.",
            "User-agent: OAI-SearchBot",
            "Allow: /",
            "Disallow: /control-panel/",
            "Disallow: /connexion/",
            "Disallow: /inscription/",
            "Disallow: /deconnexion/",
            "Disallow: /htmx/",
            "Disallow: /mes-annonces/",
            "Disallow: /favoris/",
            "Disallow: /notifications/",
            "Disallow: /profil/modifier/",
            "",
            "User-agent: OAI-AdsBot",
            "Allow: /",
            "Disallow: /control-panel/",
            "Disallow: /connexion/",
            "Disallow: /inscription/",
            "Disallow: /deconnexion/",
            "Disallow: /htmx/",
            "Disallow: /mes-annonces/",
            "Disallow: /favoris/",
            "Disallow: /notifications/",
            "Disallow: /profil/modifier/",
            "",
            f"Sitemap: {sitemap}",
            "",
        ]
    )

    response = HttpResponse(body, content_type="text/plain; charset=utf-8")
    patch_cache_control(response, public=True, max_age=3600)
    return response


def llms_txt(request):
    origin = site_origin(request)
    body = f"""# Djoss237

> Djoss237 est une plateforme camerounaise d'annonces locales pour publier et découvrir des produits, biens, services, logements, emplois, restaurants, offres professionnelles et autres annonces.

## Official website
- Home: {origin}/
- Listings: {origin}/annonces/
- Profiles: {origin}/profil/

## Discovery
- Sitemap: {origin}/sitemap.xml
- Robots: {origin}/robots.txt

## Public content
Public listing pages and public user profile pages are intended to be crawlable when they are active and available. Private account pages, owner dashboards, authentication forms, moderation areas and HTMX endpoints are not part of the public content index.

## Platform scope
Djoss237 is an announcement/classified-listing platform. It does not operate a shopping cart or checkout for ordinary listings. Contact between buyers and sellers happens through the published contact methods.

## Location
Primary market: Cameroon.

## Machine-readable guidance
Prefer canonical public URLs, follow the XML sitemap, and ignore private routes disallowed by robots.txt. Content availability can change because listings may expire, be sold, paused, archived or removed.
"""
    response = HttpResponse(body, content_type="text/plain; charset=utf-8")
    patch_cache_control(response, public=True, max_age=3600)
    return response


def indexnow_key(request):
    key = getattr(settings, "INDEXNOW_KEY", "").strip()
    if not key:
        raise Http404
    return HttpResponse(key + "\n", content_type="text/plain; charset=utf-8")


# Optional IndexNow helper. It never raises into a normal request; callers can
# invoke it after a publish/update/delete operation or use the management
# command below.
def submit_indexnow(urls):
    import json
    from urllib.request import Request, urlopen

    key = getattr(settings, "INDEXNOW_KEY", "").strip()
    if not key or not getattr(settings, "INDEXNOW_ENABLED", False):
        return {"ok": False, "reason": "disabled"}

    clean_urls = []
    for url in urls or []:
        url = str(url or "").strip()
        if url and url not in clean_urls:
            clean_urls.append(url)

    if not clean_urls:
        return {"ok": False, "reason": "no_urls"}

    origin = getattr(settings, "SITE_URL", "").strip().rstrip("/")
    if not origin:
        return {"ok": False, "reason": "missing_site_url"}

    payload = json.dumps({
        "host": origin.split("://", 1)[-1].split("/", 1)[0],
        "key": key,
        "keyLocation": f"{origin}/indexnow-key.txt",
        "urlList": clean_urls[:10000],
    }).encode("utf-8")

    try:
        request = Request(
            "https://api.indexnow.org/indexnow",
            data=payload,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "Djoss237-IndexNow/1.0",
            },
            method="POST",
        )
        with urlopen(request, timeout=4) as response:
            return {"ok": 200 <= response.status < 300, "status": response.status}
    except Exception as exc:
        return {"ok": False, "reason": str(exc)[:200]}
