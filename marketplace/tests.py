from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import PublicListingForm
from .models import Category, City, Favorite, Listing, Neighborhood, Notification, Report
from .services import expire_due_listings

User = get_user_model()


class MarketplaceBaseTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="abdoul",
            phone_number="693149222",
            password="StrongPass123!",
        )
        self.other_user = User.objects.create_user(
            username="seller2",
            phone_number="690892646",
            password="StrongPass123!",
        )
        self.category = Category.objects.create(name="Services", slug="services", is_active=True)
        self.city = City.objects.create(name="Douala", slug="douala", region="Littoral", is_active=True)
        self.neighborhood = Neighborhood.objects.create(city=self.city, name="Bonapriso", slug="bonapriso", is_active=True)

    def make_listing(self, user=None, **extra):
        now = timezone.now()
        data = dict(
            user=user or self.user,
            category=self.category,
            city=self.city,
            neighborhood=self.neighborhood,
            title="Service de plomberie",
            slug="service-de-plomberie-1234",
            description="Dépannage plomberie à Douala et alentours.",
            price=25000,
            price_type=Listing.PriceType.FIXED,
            condition=Listing.Condition.NOT_APPLICABLE,
            status=Listing.Status.PUBLISHED,
            promo_type=Listing.PromoType.STANDARD,
            duration_days=14,
            published_at=now,
            expires_at=now + timedelta(days=14),
        )
        data.update(extra)
        return Listing.objects.create(**data)


class ListingLifetimeTests(MarketplaceBaseTestCase):
    def test_duration_days_accepts_one_to_thirty_days(self):
        form = PublicListingForm(data={
            "category": self.category.pk,
            "city": self.city.pk,
            "neighborhood": self.neighborhood.slug,
            "title": "Location studio Akwa",
            "description": "Studio propre disponible à Akwa.",
            "price": "100000",
            "price_type": "fixed",
            "condition": "na",
            "duration_mode": "days",
            "duration_days": "14",
            "expires_at_input": "",
            "website": "",
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["duration_days"], 14)

    def test_duration_above_thirty_days_is_rejected(self):
        form = PublicListingForm(data={
            "category": self.category.pk,
            "city": self.city.pk,
            "neighborhood": self.neighborhood.slug,
            "title": "Location studio Akwa",
            "description": "Studio propre disponible à Akwa.",
            "price": "100000",
            "price_type": "fixed",
            "condition": "na",
            "duration_mode": "days",
            "duration_days": "31",
            "expires_at_input": "",
            "website": "",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("duration_days", form.errors)

    def test_exact_expiration_cannot_exceed_thirty_days(self):
        exact = timezone.localtime(timezone.now() + timedelta(days=31)).strftime("%Y-%m-%dT%H:%M")
        form = PublicListingForm(data={
            "category": self.category.pk,
            "city": self.city.pk,
            "neighborhood": self.neighborhood.slug,
            "title": "Location studio Akwa",
            "description": "Studio propre disponible à Akwa.",
            "price": "100000",
            "price_type": "fixed",
            "condition": "na",
            "duration_mode": "date",
            "duration_days": "30",
            "expires_at_input": exact,
            "website": "",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("expires_at_input", form.errors)


class AuthenticationTests(MarketplaceBaseTestCase):

    def test_invalid_cameroon_phone_is_rejected(self):
        with self.assertRaises(Exception):
            User.objects.create_user(
                username="badphone",
                phone_number="12345",
                password="StrongPass123!",
            ).full_clean()

    def test_login_with_username(self):
        response = self.client.post(reverse("marketplace:login_htmx"), {
            "identifier": "abdoul",
            "password": "StrongPass123!",
        }, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.client.session.get("_auth_user_id"))

    def test_login_with_phone(self):
        response = self.client.post(reverse("marketplace:login_htmx"), {
            "identifier": "693149222",
            "password": "StrongPass123!",
        }, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.client.session.get("_auth_user_id"))

    def test_login_invalid_password_returns_swappable_form(self):
        response = self.client.post(reverse("marketplace:login_htmx"), {
            "identifier": "abdoul",
            "password": "wrong-password",
        }, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Identifiant ou mot de passe incorrect.")


class PublicInteractionTests(MarketplaceBaseTestCase):
    def test_anonymous_can_open_public_listing(self):
        listing = self.make_listing()
        response = self.client.get(reverse("marketplace:listing_detail", kwargs={"slug": listing.slug}))
        self.assertEqual(response.status_code, 200)

    def test_anonymous_can_report_listing(self):
        listing = self.make_listing()
        response = self.client.post(
            reverse("marketplace:report_listing", kwargs={"slug": listing.slug}),
            {"reason": "spam", "message": "Cette annonce semble répétitive.", "reporter_phone": "690892646"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Report.objects.filter(listing=listing).count(), 1)
        listing.refresh_from_db()
        self.assertEqual(listing.report_count, 1)

    def test_authenticated_user_can_toggle_favorite(self):
        listing = self.make_listing()
        self.client.force_login(self.user)
        response = self.client.post(reverse("marketplace:toggle_favorite", kwargs={"slug": listing.slug}), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Favorite.objects.filter(user=self.user, listing=listing).exists())


class NeighborhoodHTMXTests(MarketplaceBaseTestCase):
    def test_neighborhood_endpoint_returns_option_elements_for_city_pk(self):
        response = self.client.get(
            reverse("marketplace:neighborhoods_htmx"),
            {"city": str(self.city.pk)},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<option value="bonapriso"')
        self.assertNotContains(response, '<section')
        self.assertNotContains(response, '<form')


class OwnerSecurityTests(MarketplaceBaseTestCase):
    def test_owner_page_rejects_other_user(self):
        listing = self.make_listing(user=self.user)
        self.client.force_login(self.other_user)
        response = self.client.get(reverse("marketplace:owner_listing_detail", kwargs={"slug": listing.slug}))
        self.assertEqual(response.status_code, 404)

    def test_owner_can_edit_own_listing(self):
        listing = self.make_listing()
        self.client.force_login(self.user)
        response = self.client.get(reverse("marketplace:edit_listing", kwargs={"slug": listing.slug}))
        self.assertEqual(response.status_code, 200)


class ExpirationTests(MarketplaceBaseTestCase):
    def test_due_listing_becomes_expired_and_notifies_owner(self):
        listing = self.make_listing(expires_at=timezone.now() - timedelta(minutes=5))
        changed = expire_due_listings(create_notifications=True)
        self.assertEqual(changed, 1)
        listing.refresh_from_db()
        self.assertEqual(listing.status, Listing.Status.EXPIRED)
        self.assertTrue(Notification.objects.filter(user=self.user, listing=listing, kind=Notification.Kind.EXPIRED).exists())


class SmokeRouteTests(TestCase):
    def test_health_endpoint_is_json(self):
        response = self.client.get(reverse("marketplace:health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ok"], True)
