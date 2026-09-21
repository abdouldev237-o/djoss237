from datetime import timedelta
import json
import uuid
from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import BooleanField, Case, Count, Exists, F, IntegerField, Max, OuterRef, Prefetch, Q, Subquery, Sum, Value, When
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .forms import LoginForm, ProfileForm, PublicListingForm, ReportForm, SignupForm
from .models import (
    Boost,
    BoostPlan,
    Category,
    City,
    ContactEvent,
    Favorite,
    EnterpriseAd,
    Listing,
    ListingEvent,
    ListingImage,
    Notification,
    PlatformSettings,
    ProfileShareEvent,
    Report,
    ShareEvent,
    UserReport,
)
from .validators import validate_image_upload
from .services import (
    create_public_listing,
    create_renewal_notifications,
    expire_due_listings,
    enforce_auth_rate_limit,
    enforce_listing_rate_limit,
    record_listing_event,
    create_user_account,
    authenticate_identifier,
)


def is_htmx(request):
    return request.headers.get("HX-Request") == "true"


def health_check(request):
    if request.method != "GET":
        return HttpResponse(status=405)
    return JsonResponse({"ok": True, "service": "annonce-platform"})


def base_public_queryset():
    now = timezone.now()
    qs = (
        Listing.objects.select_related("user", "category", "city", "neighborhood")
        .prefetch_related("images")
        .filter(
            status=Listing.Status.PUBLISHED,
            expires_at__gt=now,
            user__is_active=True,
            user__is_blocked=False,
        )
    )
    config = PlatformSettings.load()
    if config.monetization_enabled:
        boost_qs = Boost.objects.filter(
            listing_id=OuterRef("pk"),
            status=Boost.Status.ACTIVE,
            starts_at__lte=now,
            ends_at__gt=now,
        )
        qs = qs.annotate(
            has_active_boost=Exists(boost_qs),
            boost_price=Subquery(
                boost_qs.order_by("-plan__price").values("plan__price")[:1],
                output_field=IntegerField(),
            ),
        )
    else:
        qs = qs.annotate(
            has_active_boost=Value(False, output_field=BooleanField()),
            boost_price=Value(0, output_field=IntegerField()),
        )
    return qs


def ordered_public_queryset(qs):
    # Paid/boosted content is intentionally separated first only when enabled.
    return qs.order_by(
        Case(
            When(has_active_boost=True, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        ),
        Case(
            When(has_active_boost=True, then=F("boost_price")),
            default=Value(0),
            output_field=IntegerField(),
        ).desc(),
        "-published_at",
        "-views_count",
    )


def home(request):
    expire_due_listings(create_notifications=True)
    create_renewal_notifications()
    queryset = ordered_public_queryset(base_public_queryset())
    hero_listings = list(queryset[:8])
    listings = queryset[:12]
    category_children = Prefetch(
        "children",
        queryset=Category.objects.filter(is_active=True).order_by("position", "name"),
        to_attr="active_children",
    )
    categories = (
        Category.objects
        .filter(is_active=True, parent__isnull=True)
        .prefetch_related(category_children)
        .annotate(
            active_children_count=Count("children", filter=Q(children__is_active=True)),
            active_listing_count=Count(
                "listings",
                filter=Q(
                    listings__status=Listing.Status.PUBLISHED,
                    listings__expires_at__gt=timezone.now(),
                    listings__user__is_active=True,
                    listings__user__is_blocked=False,
                ),
                distinct=True,
            ),
        )
        .order_by("position", "name")
    )
    cities = City.objects.filter(is_active=True).order_by("name")

    enterprise_ads = []
    config = PlatformSettings.load()
    if config.enterprise_ads_enabled:
        now = timezone.now()
        enterprise_ads = (
            EnterpriseAd.objects.filter(
                status=EnterpriseAd.Status.ACTIVE,
                starts_at__lte=now,
                ends_at__gt=now,
            )
            .order_by("position", "-created_at")[:3]
        )

    return render(
        request,
        "marketplace/home.html",
        {
            "hero_listings": hero_listings,
            "listings": listings,
            "categories": categories,
            "cities": cities,
            "enterprise_ads": enterprise_ads,
        },
    )


@require_GET
def listing_list(request):
    expire_due_listings(create_notifications=True)
    queryset = base_public_queryset()
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    city = request.GET.get("city", "").strip()
    neighborhood = request.GET.get("neighborhood", "").strip()
    minimum = request.GET.get("min_price", "").strip()
    maximum = request.GET.get("max_price", "").strip()
    sort = request.GET.get("sort", "newest")

    if query:
        queryset = queryset.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(category__name__icontains=query)
            | Q(city__name__icontains=query)
            | Q(neighborhood__name__icontains=query)
        )
    if category:
        selected_category = Category.objects.filter(is_active=True, slug=category).first()
        if selected_category and selected_category.parent_id is None:
            queryset = queryset.filter(
                Q(category_id=selected_category.pk)
                | Q(category__parent_id=selected_category.pk)
            )
        else:
            queryset = queryset.filter(category__slug=category)
    if city:
        queryset = queryset.filter(city__slug=city)
    if neighborhood:
        queryset = queryset.filter(neighborhood__slug=neighborhood)
    if minimum:
        queryset = queryset.filter(price__gte=minimum)
    if maximum:
        queryset = queryset.filter(price__lte=maximum)

    if sort == "price_asc":
        queryset = queryset.order_by(
            Case(When(has_active_boost=True, then=Value(0)), default=Value(1), output_field=IntegerField()),
            "price",
            "-published_at",
        )
    elif sort == "price_desc":
        queryset = queryset.order_by(
            Case(When(has_active_boost=True, then=Value(0)), default=Value(1), output_field=IntegerField()),
            "-price",
            "-published_at",
        )
    elif sort == "popular":
        queryset = queryset.order_by(
            Case(When(has_active_boost=True, then=Value(0)), default=Value(1), output_field=IntegerField()),
            "-views_count",
            "-published_at",
        )
    else:
        queryset = ordered_public_queryset(queryset)

    paginator = Paginator(queryset, 24)
    page_obj = paginator.get_page(request.GET.get("page"))

    selected_city = City.objects.filter(slug=city, is_active=True).first() if city else None
    params = request.GET.copy()
    params.pop("page", None)

    context = {
        "page_obj": page_obj,
        "categories": Category.objects.filter(is_active=True).order_by("position", "name"),
        "cities": City.objects.filter(is_active=True).order_by("name"),
        "neighborhoods": selected_city.neighborhoods.filter(is_active=True).order_by("name") if selected_city else [],
        "query": query,
        "selected_category": category,
        "selected_city": city,
        "selected_neighborhood": neighborhood,
        "sort": sort,
        "querystring": params.urlencode(),
    }

    if is_htmx(request):
        return render(request, "marketplace/partials/listing_results.html", context)
    return render(request, "marketplace/listing_list.html", context)


@require_GET
def listing_detail(request, slug):
    listing = get_object_or_404(base_public_queryset(), slug=slug)

    # Keep the owner from inflating public traffic stats, and lightly de-duplicate
    # repeat page refreshes from the same visitor for 20 minutes.
    is_owner = request.user.is_authenticated and request.user.pk == listing.user_id
    if not is_owner:
        view_key = f"listing-view:{request.session.session_key or request.META.get('REMOTE_ADDR', 'unknown')}:{listing.pk}"
        if not cache.get(view_key):
            cache.set(view_key, True, 20 * 60)
            record_listing_event(request, listing, ListingEvent.Type.VIEW, increment_field="views_count")
            listing.views_count += 1
            listing.last_viewed_at = timezone.now()
            Listing.objects.filter(pk=listing.pk).update(last_viewed_at=listing.last_viewed_at)

    is_favorite = False
    if request.user.is_authenticated:
        is_favorite = Favorite.objects.filter(user=request.user, listing=listing).exists()

    return render(
        request,
        "marketplace/listing_detail.html",
        {
            "listing": listing,
            "is_owner": is_owner,
            "is_favorite": is_favorite,
        },
    )


@require_GET
def neighborhoods_htmx(request):
    """Return only <option> elements for a city selected in the listing form.

    Accepts either a numeric City primary key or a City slug so the endpoint
    remains compatible with old forms and current forms.
    """
    city_value = (request.GET.get("city") or "").strip()
    selected_slug = (request.GET.get("neighborhood") or "").strip()
    city = None

    if city_value:
        if city_value.isdigit():
            city = City.objects.filter(
                pk=int(city_value),
                is_active=True,
            ).first()
        if city is None:
            city = City.objects.filter(
                slug=city_value,
                is_active=True,
            ).first()

    neighborhoods = (
        city.neighborhoods.filter(is_active=True).order_by("name")
        if city else Neighborhood.objects.none()
    )

    return render(
        request,
        "marketplace/partials/neighborhood_options.html",
        {
            "neighborhoods": neighborhoods,
            "selected_slug": selected_slug,
            "selected_id": selected_slug,
            "selected_city": city,
        },
    )


@require_http_methods(["GET", "POST"])
def create_listing(request):
    if not request.user.is_authenticated:
        if request.method == "POST":
            if is_htmx(request):
                response = HttpResponse("", status=401)
                response["HX-Trigger"] = "marketplace-open-auth"
                return response
            return redirect(f"{reverse('marketplace:home')}?auth=required")
        return render(
            request,
            "marketplace/listing_form.html",
            {"form": PublicListingForm(), "auth_required": True},
        )

    if request.user.is_blocked:
        return render(
            request,
            "marketplace/listing_form.html",
            {"form": PublicListingForm(), "blocked": True},
        )

    if request.method == "GET":
        return render(request, "marketplace/listing_form.html", {"form": PublicListingForm()})

    form = PublicListingForm(request.POST, request.FILES)
    if not form.is_valid():
        return render(request, "marketplace/listing_form.html", {"form": form}, status=200)

    try:
        enforce_listing_rate_limit(request, request.user)
        listing = create_public_listing(
            user=request.user,
            cleaned_data=form.cleaned_data,
            uploaded_images=form.cleaned_data.get("images", []),
        )
    except ValidationError as exc:
        for error in exc.messages:
            form.add_error(None, error)
        return render(request, "marketplace/listing_form.html", {"form": form}, status=200)

    absolute_url = request.build_absolute_uri(listing.get_absolute_url())
    return render(
        request,
        "marketplace/post_success.html",
        {"listing": listing, "share_url": absolute_url},
    )


@login_required
@require_http_methods(["GET", "POST"])
def edit_listing(request, slug):
    listing = get_object_or_404(
        Listing.objects.select_related("user", "category", "city", "neighborhood").prefetch_related("images"),
        slug=slug,
        user=request.user,
    )

    if listing.status == Listing.Status.ARCHIVED:
        messages.warning(request, "Cette annonce est archivée et ne peut plus être modifiée.")
        return redirect("marketplace:my_listings")

    if request.method == "GET":
        form = PublicListingForm(instance=listing)
    else:
        form = PublicListingForm(request.POST, request.FILES, instance=listing)
        if form.is_valid():
            try:
                enforce_listing_rate_limit(request, request.user)
                extra_images = list(form.cleaned_data.get("images", []))
                max_images = int(getattr(settings, "PUBLIC_LISTING_MAX_IMAGES", 10))
                existing_count = listing.images.count()
                if existing_count + len(extra_images) > max_images:
                    raise ValidationError(f"Votre annonce ne peut pas dépasser {max_images} photos au total.")

                listing = form.save(commit=False)
                listing.duration_days = form.cleaned_data["duration_days"]
                listing.expires_at = form.cleaned_data["expires_at"]

                if listing.status == Listing.Status.EXPIRED and listing.expires_at > timezone.now():
                    # Editing does not silently republish an expired listing.
                    listing.status = Listing.Status.EXPIRED

                listing.save()

                for image in extra_images:
                    validate_image_upload(image)
                next_position = listing.images.aggregate(max_position=Max("position"))["max_position"] or 0
                for offset, image in enumerate(extra_images, start=1):
                    ListingImage.objects.create(
                        listing=listing,
                        image=image,
                        position=next_position + offset,
                        is_cover=(existing_count == 0 and offset == 1),
                    )

                messages.success(request, "Votre annonce a été mise à jour.")
                return redirect("marketplace:owner_listing_detail", slug=listing.slug)
            except ValidationError as exc:
                for error in exc.messages:
                    form.add_error(None, error)

    return render(
        request,
        "marketplace/listing_form.html",
        {"form": form, "listing": listing, "editing": True},
    )


@require_GET
def public_user_form(request):
    return render(request, "marketplace/partials/auth_login.html", {"form": LoginForm()})


@require_GET
def public_signup_form(request):
    return render(request, "marketplace/partials/auth_signup.html", {"form": SignupForm()})


@require_POST
def login_htmx(request):
    form = LoginForm(request.POST)
    if not form.is_valid():
        return render(request, "marketplace/partials/auth_login.html", {"form": form})

    try:
        enforce_auth_rate_limit(request, form.cleaned_data["identifier"])
    except ValidationError as exc:
        form.add_error(None, str(exc))
        return render(request, "marketplace/partials/auth_login.html", {"form": form}, status=429)

    user = authenticate_identifier(
        request,
        form.cleaned_data["identifier"],
        form.cleaned_data["password"],
    )
    if not user:
        form.add_error(None, "Identifiant ou mot de passe incorrect.")
        return render(request, "marketplace/partials/auth_login.html", {"form": form})
    if user.is_blocked:
        form.add_error(None, "Ce compte est temporairement bloqué.")
        return render(request, "marketplace/partials/auth_login.html", {"form": form}, status=403)

    login(request, user)
    user.last_seen_at = timezone.now()
    user.save(update_fields=["last_seen_at"])
    response = render(
        request,
        "marketplace/partials/auth_success.html",
        {"user": user, "mode": "login"},
    )
    response["HX-Trigger"] = json.dumps(
        {"marketplace-authenticated": {"user_id": user.pk, "username": user.username}}
    )
    next_url = request.POST.get("next", "").strip()
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        response["HX-Redirect"] = next_url
    return response


@require_POST
def signup_htmx(request):
    form = SignupForm(request.POST)
    if not form.is_valid():
        return render(request, "marketplace/partials/auth_signup.html", {"form": form})

    try:
        enforce_auth_rate_limit(request, form.cleaned_data["phone_number"])
        user = create_user_account(
            username=form.cleaned_data["username"],
            phone_number=form.cleaned_data["phone_number"],
            password=form.cleaned_data["password1"],
        )
    except ValidationError as exc:
        form.add_error(None, exc.messages[0] if getattr(exc, "messages", None) else str(exc))
        return render(request, "marketplace/partials/auth_signup.html", {"form": form})

    login(request, user)
    response = render(
        request,
        "marketplace/partials/auth_success.html",
        {"user": user, "mode": "signup"},
    )
    response["HX-Trigger"] = json.dumps(
        {"marketplace-authenticated": {"user_id": user.pk, "username": user.username}}
    )
    next_url = request.POST.get("next", "").strip()
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        response["HX-Redirect"] = next_url
    return response


@require_POST
def logout_view(request):
    logout(request)
    if is_htmx(request):
        response = render(request, "marketplace/partials/auth_logged_out.html")
        response["HX-Trigger"] = "marketplace-logged-out"
        return response
    return redirect("marketplace:home")


@require_POST
def toggle_favorite(request, slug):
    if not request.user.is_authenticated:
        response = HttpResponse("", status=401)
        response["HX-Trigger"] = "marketplace-open-auth"
        return response

    listing = get_object_or_404(base_public_queryset(), slug=slug)
    favorite, created = Favorite.objects.get_or_create(user=request.user, listing=listing)
    if not created:
        favorite.delete()
        is_favorite = False
    else:
        is_favorite = True

    template = "marketplace/partials/favorite_button.html"
    response = render(
        request,
        template,
        {"listing": listing, "is_favorite": is_favorite},
    )
    response["HX-Trigger"] = json.dumps(
        {"favorite-changed": {"listing_id": listing.pk, "active": is_favorite}}
    )
    return response


@login_required
@require_POST
def start_boost_checkout(request, slug):
    config = PlatformSettings.load()
    if not config.monetization_enabled:
        return JsonResponse({"ok": False, "error": "La monétisation est désactivée."}, status=404)

    listing = get_object_or_404(Listing, slug=slug, user=request.user)
    plan_id = request.POST.get("plan")
    plan = get_object_or_404(BoostPlan, pk=plan_id, is_active=True)

    reference = f"BOOST-{uuid.uuid4().hex[:18].upper()}"
    from .models import Payment

    payment = Payment.objects.create(
        provider="future",
        reference=reference,
        user=request.user,
        amount=plan.price,
        currency=plan.currency,
        status=Payment.Status.PENDING,
        metadata={"listing_id": listing.pk, "plan_id": plan.pk},
    )
    boost = Boost.objects.create(
        listing=listing,
        plan=plan,
        payment=payment,
        status=Boost.Status.PENDING,
    )
    return JsonResponse(
        {
            "ok": True,
            "checkout_ready": False,
            "message": "Paiement en attente. Branchez votre fournisseur dans start_boost_checkout().",
            "payment_reference": payment.reference,
            "boost_id": boost.pk,
            "amount": str(plan.price),
            "currency": plan.currency,
            "duration_days": plan.duration_days,
            "promotion_type": plan.promotion_type,
        }
    )


@login_required
def favorites(request):
    favorites_qs = (
        Favorite.objects.filter(user=request.user, listing__status=Listing.Status.PUBLISHED, listing__expires_at__gt=timezone.now(), listing__user__is_active=True, listing__user__is_blocked=False)
        .select_related("listing__user", "listing__category", "listing__city", "listing__neighborhood")
        .prefetch_related("listing__images")
        .order_by("-created_at")
    )
    return render(request, "marketplace/favorites.html", {"favorites": favorites_qs})


@login_required
def my_listings(request):
    expire_due_listings(create_notifications=True)
    listings = (
        request.user.listings
        .select_related("category", "city", "neighborhood")
        .prefetch_related("images")
        .order_by("-created_at")
    )
    stats = listings.aggregate(
        total=Count("id"),
        views=Sum("views_count"),
        whatsapp=Sum("whatsapp_clicks"),
        calls=Sum("call_clicks"),
        shares=Sum("share_count"),
    )
    return render(request, "marketplace/my_listings.html", {"listings": listings, "stats": stats})


@login_required
def owner_listing_detail(request, slug):
    expire_due_listings(create_notifications=True)
    listing = get_object_or_404(
        Listing.objects.select_related("user", "category", "city", "neighborhood").prefetch_related("images"),
        slug=slug,
        user=request.user,
    )
    events = listing.events.select_related("user").order_by("-created_at")[:30]
    config = PlatformSettings.load()
    boost_plans = BoostPlan.objects.filter(is_active=True).order_by("position", "price") if config.monetization_enabled else []
    return render(
        request,
        "marketplace/owner_listing_detail.html",
        {
            "listing": listing,
            "events": events,
            "boost_plans": boost_plans,
            "boost_checkout_url_json": json.dumps(
                reverse("marketplace:start_boost_checkout", kwargs={"slug": listing.slug})
            ),
        },
    )


@login_required
@require_GET
def owner_listing_stats(request, slug):
    """Detailed 14-day analytics page for the listing owner."""
    expire_due_listings(create_notifications=True)
    listing = get_object_or_404(
        Listing.objects.select_related("user", "category", "city", "neighborhood"),
        slug=slug,
        user=request.user,
    )

    from django.db.models.functions import TruncDate
    from datetime import timedelta

    today = timezone.localdate()
    start_date = today - timedelta(days=13)
    event_rows = (
        listing.events
        .filter(created_at__date__gte=start_date)
        .annotate(day=TruncDate("created_at"))
        .values("day", "event_type")
        .annotate(total=Count("id"))
        .order_by("day", "event_type")
    )
    matrix = {}
    for row in event_rows:
        matrix[(row["day"], row["event_type"])] = row["total"]

    days = []
    for offset in range(14):
        day = start_date + timedelta(days=offset)
        views = matrix.get((day, ListingEvent.Type.VIEW), 0)
        whatsapp = matrix.get((day, ListingEvent.Type.WHATSAPP), 0)
        calls = matrix.get((day, ListingEvent.Type.CALL), 0)
        shares = matrix.get((day, ListingEvent.Type.SHARE), 0)
        days.append({
            "date": day,
            "label": day.strftime("%d/%m"),
            "views": views,
            "whatsapp": whatsapp,
            "calls": calls,
            "shares": shares,
            "total": views + whatsapp + calls + shares,
        })

    return render(
        request,
        "marketplace/owner_listing_stats.html",
        {
            "listing": listing,
            "days": days,
            "period_views": sum(item["views"] for item in days),
            "period_whatsapp": sum(item["whatsapp"] for item in days),
            "period_calls": sum(item["calls"] for item in days),
            "period_shares": sum(item["shares"] for item in days),
        },
    )


@login_required
@require_POST
def owner_toggle_pause(request, slug):
    listing = get_object_or_404(Listing, slug=slug, user=request.user)
    now = timezone.now()
    if listing.status == Listing.Status.PUBLISHED:
        listing.status = Listing.Status.PAUSED
        listing.save(update_fields=["status", "updated_at"])
        messages.success(request, "Annonce mise en pause.")
    elif listing.status == Listing.Status.PAUSED and listing.expires_at > now:
        listing.status = Listing.Status.PUBLISHED
        listing.save(update_fields=["status", "updated_at"])
        messages.success(request, "Annonce remise en ligne.")
    else:
        messages.warning(request, "Cette annonce ne peut pas être reprise dans son état actuel.")
    return redirect("marketplace:owner_listing_detail", slug=listing.slug)


@login_required
@require_POST
def owner_mark_sold(request, slug):
    listing = get_object_or_404(Listing, slug=slug, user=request.user)
    listing.mark_sold()
    Notification.objects.create(
        user=request.user,
        listing=listing,
        kind=Notification.Kind.SYSTEM,
        title="Annonce marquée comme vendue",
        message=f"« {listing.title} » est maintenant marquée comme vendue.",
        action_url=reverse("marketplace:owner_listing_detail", kwargs={"slug": listing.slug}),
    )
    messages.success(request, "Annonce marquée comme vendue.")
    return redirect("marketplace:owner_listing_detail", slug=listing.slug)


@login_required
@require_POST
def owner_renew(request, slug):
    listing = get_object_or_404(Listing, slug=slug, user=request.user)
    raw_days = request.POST.get("days", "30").strip()
    try:
        days = max(1, min(30, int(raw_days)))
    except ValueError:
        days = 30

    listing.renew(days=days)
    Notification.objects.create(
        user=request.user,
        listing=listing,
        kind=Notification.Kind.RENEWAL,
        title="Annonce renouvelée",
        message=f"« {listing.title} » est à nouveau publiée pour {days} jours.",
        action_url=reverse("marketplace:owner_listing_detail", kwargs={"slug": listing.slug}),
    )
    messages.success(request, f"Annonce renouvelée pour {days} jours.")
    return redirect("marketplace:owner_listing_detail", slug=listing.slug)


@login_required
@require_POST
def owner_delete(request, slug):
    listing = get_object_or_404(Listing, slug=slug, user=request.user)
    listing.status = Listing.Status.ARCHIVED
    listing.save(update_fields=["status", "updated_at"])
    messages.success(request, "Annonce supprimée de votre espace public.")
    return redirect("marketplace:my_listings")


@require_GET
def listing_whatsapp(request, slug):
    listing = get_object_or_404(base_public_queryset(), slug=slug)
    record_listing_event(request, listing, ListingEvent.Type.WHATSAPP, increment_field="whatsapp_clicks")
    ContactEvent.objects.create(
        listing=listing,
        event_type=ContactEvent.Type.WHATSAPP,
        user=request.user if request.user.is_authenticated else None,
    )
    message = f"Bonjour, j’ai trouvé votre annonce « {listing.title} » sur DJOSS237. Est-elle toujours disponible ?"
    return redirect(f"https://wa.me/{listing.user.whatsapp_number}?text={quote(message)}")


from django.http import HttpResponseRedirect
from django.db.models import F
from django.utils.html import escape
import re

@require_GET
def listing_call(request, slug):
    listing = get_object_or_404(
        Listing.objects.select_related("user"),
        slug=slug,
    )

    raw_phone = (listing.user.phone_number or "").strip()

    if not raw_phone:
        return HttpResponse(
            """
            <!doctype html>
            <html lang="fr">
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width,initial-scale=1">
                <title>Numéro indisponible</title>
            </head>
            <body>
                <p>Le numéro du vendeur n'est pas disponible.</p>
            </body>
            </html>
            """,
            status=200,
        )

    # Keep only characters appropriate for a tel URI.
    phone = re.sub(r"[^\d+]", "", raw_phone)

    if not phone:
        return HttpResponse(
            "Numéro de téléphone invalide.",
            status=400,
        )

    # ---------------------------------------------------------
    # Track the interaction
    # ---------------------------------------------------------
    Listing.objects.filter(
        pk=listing.pk,
    ).update(
        call_clicks=F("call_clicks") + 1,
    )

    ContactEvent.objects.create(
        listing=listing,
        event_type="call",
    )

    tel_url = f"tel:{phone}"

    # ---------------------------------------------------------
    # IMPORTANT:
    # Django cannot HttpResponseRedirect() to tel:
    # Let the browser perform the tel navigation.
    # ---------------------------------------------------------
    html = f"""
    <!doctype html>
    <html lang="fr">
    <head>
        <meta charset="utf-8">

        <meta
            name="viewport"
            content="width=device-width,initial-scale=1,viewport-fit=cover"
        >

        <meta
            http-equiv="refresh"
            content="0;url={escape(tel_url)}"
        >

        <title>Appel — DJOSS237</title>

        <style>
            * {{
                box-sizing: border-box;
            }}

            html,
            body {{
                margin: 0;
                min-height: 100%;
                font-family:
                    Inter,
                    system-ui,
                    -apple-system,
                    BlinkMacSystemFont,
                    "Segoe UI",
                    sans-serif;
                background: #f8fafc;
                color: #0f172a;
            }}

            body {{
                display: grid;
                place-items: center;
                padding:
                    max(24px, env(safe-area-inset-top))
                    20px
                    max(24px, env(safe-area-inset-bottom));
            }}

            .card {{
                width: min(100%, 460px);
                padding: 28px;
                border-radius: 26px;
                background: white;
                border: 1px solid rgba(15, 23, 42, .08);
                box-shadow:
                    0 25px 60px rgba(15, 23, 42, .08);
                text-align: center;
            }}

            .icon {{
                width: 58px;
                height: 58px;
                margin: 0 auto 16px;
                display: grid;
                place-items: center;
                border-radius: 18px;
                background: #f1f5f9;
                font-size: 25px;
            }}

            h1 {{
                margin: 0;
                font-size: 1.2rem;
                letter-spacing: -.03em;
            }}

            p {{
                margin: 9px 0 20px;
                color: #64748b;
                font-size: .9rem;
                line-height: 1.6;
            }}

            .btn {{
                display: inline-flex;
                align-items: center;
                justify-content: center;
                min-height: 46px;
                padding: 0 18px;
                border-radius: 13px;
                background: #0f172a;
                color: white;
                text-decoration: none;
                font-weight: 800;
                font-size: .84rem;
            }}
        </style>
    </head>

    <body>

        <main class="card">

            <div class="icon">☎</div>

            <h1>
                Ouverture de l'appel…
            </h1>

            <p>
                Le navigateur essaie d'ouvrir l'application
                téléphone avec le numéro du vendeur.
            </p>

            <a
                class="btn"
                href="{escape(tel_url)}"
            >
                Appeler maintenant
            </a>

        </main>

        <script>
            window.setTimeout(function () {{
                window.location.href = {tel_url!r};
            }}, 80);
        </script>

    </body>
    </html>
    """

    return HttpResponse(
        html,
        content_type="text/html; charset=utf-8",
    )

@require_POST
def event_share(request, slug):
    listing = get_object_or_404(base_public_queryset(), slug=slug)
    platform = request.POST.get("platform", "other")
    valid = {value for value, _ in ShareEvent.Platform.choices}
    platform = platform if platform in valid else ShareEvent.Platform.OTHER
    key = f"annonce:share:{request.META.get('REMOTE_ADDR', 'unknown')}:{listing.pk}:{platform}"
    count = cache.get(key, 0)
    new_count = listing.share_count
    if count < 30:
        cache.set(key, count + 1, 3600)
        ShareEvent.objects.create(listing=listing, platform=platform)
        record_listing_event(
            request,
            listing,
            ListingEvent.Type.SHARE,
            platform=platform,
            increment_field="share_count",
        )
        new_count += 1
    return JsonResponse({"ok": True, "count": new_count})


@require_GET
def report_form(request, slug):
    listing = get_object_or_404(base_public_queryset(), slug=slug)
    return render(
        request,
        "marketplace/partials/report_form.html",
        {"form": ReportForm(), "listing": listing},
    )


@require_POST
def report_listing(request, slug):
    listing = get_object_or_404(base_public_queryset(), slug=slug)
    form = ReportForm(request.POST)
    if not form.is_valid():
        return render(
            request,
            "marketplace/partials/report_form.html",
            {"form": form, "listing": listing},
            status=200,
        )
    report = form.save(commit=False)
    report.listing = listing
    report.save()
    Listing.objects.filter(pk=listing.pk).update(report_count=F("report_count") + 1)
    ListingEvent.objects.create(
        listing=listing,
        event_type=ListingEvent.Type.REPORT,
        user=request.user if request.user.is_authenticated else None,
    )
    return render(request, "marketplace/partials/report_success.html")


@require_GET
def profile(request, username):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = get_object_or_404(User, username__iexact=username, is_active=True, is_blocked=False)
    listings = base_public_queryset().filter(user=user).order_by("-published_at", "-views_count")
    return render(
        request,
        "marketplace/profile.html",
        {
            "profile_user": user,
            "listings": listings,
            "is_owner": request.user.is_authenticated and request.user.pk == user.pk,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def profile_edit(request):
    if request.method == "GET":
        form = ProfileForm(instance=request.user)
    else:
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Votre profil a été mis à jour.")
            return redirect("marketplace:profile", username=request.user.username)
    return render(request, "marketplace/profile_edit.html", {"form": form})


@require_POST
def profile_share_event(request, username):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = get_object_or_404(User, username__iexact=username, is_active=True, is_blocked=False)
    platform = request.POST.get("platform", "other")
    valid = {value for value, _ in ProfileShareEvent.Platform.choices}
    if platform not in valid:
        platform = ProfileShareEvent.Platform.OTHER
    ProfileShareEvent.objects.create(profile=user, platform=platform)
    return JsonResponse({"ok": True})


@login_required
@require_GET
def notification_list(request):
    create_renewal_notifications()
    expire_due_listings(create_notifications=True)
    notifications = request.user.notifications.all()[:100]
    return render(request, "marketplace/notifications.html", {"notifications": notifications})


@login_required
@require_POST
def mark_notification_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.is_read = True
    notification.read_at = timezone.now()
    notification.save(update_fields=["is_read", "read_at", "updated_at"])
    if is_htmx(request):
        response = render(request, "marketplace/partials/notification_item.html", {"notification": notification})
        unread = request.user.notifications.filter(is_read=False).count()
        response["HX-Trigger"] = json.dumps({"notifications-updated": {"unread": unread}})
        return response
    return redirect("marketplace:notifications")


@login_required
@require_POST
def mark_all_notifications_read(request):
    request.user.notifications.filter(is_read=False).update(is_read=True, read_at=timezone.now())
    if is_htmx(request):
        response = HttpResponse("", status=204)
        response["HX-Trigger"] = json.dumps({"notifications-updated": {"unread": 0}})
        return response
    return redirect("marketplace:notifications")


@require_GET
def report_user_form(request, username):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    target = get_object_or_404(User, username__iexact=username, is_active=True)
    return render(request, "marketplace/partials/report_user_form.html", {"target_user": target})


@require_POST
def report_user(request, username):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    target = get_object_or_404(User, username__iexact=username, is_active=True)
    reason = request.POST.get("reason", "Autre").strip()[:80]
    message = request.POST.get("message", "").strip()[:2000]
    reporter_phone = request.POST.get("reporter_phone", "").strip()[:20]
    UserReport.objects.create(
        target_user=target,
        reporter_user=request.user if request.user.is_authenticated else None,
        reporter_phone=reporter_phone,
        reason=reason or "Autre",
        message=message,
    )
    return render(request, "marketplace/partials/report_user_success.html")
