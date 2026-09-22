from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.urls import reverse
from django.utils import timezone

from marketplace.models import Listing, User
from marketplace.seo import submit_indexnow


class Command(BaseCommand):
    help = "Soumet des URLs publiques de Djoss237 à IndexNow (Bing et moteurs compatibles)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            action="append",
            dest="urls",
            default=[],
            help="URL absolue à soumettre (répétable).",
        )
        parser.add_argument(
            "--all-active",
            action="store_true",
            help="Soumet toutes les annonces actives et les profils publics concernés.",
        )

    def handle(self, *args, **options):
        if not getattr(settings, "INDEXNOW_KEY", "").strip():
            raise CommandError("INDEXNOW_KEY n'est pas configurée.")

        urls = list(options["urls"])

        origin = getattr(settings, "SITE_URL", "").strip().rstrip("/")
        if not origin:
            raise CommandError("DJANGO_SITE_URL doit être configurée en production.")

        if options["all_active"]:
            listings = Listing.objects.filter(
                status=Listing.Status.PUBLISHED,
                expires_at__gt=timezone.now(),
                user__is_active=True,
                user__is_blocked=False,
            ).only("slug", "user_id")

            urls.extend(
                f"{origin}{listing.get_absolute_url()}"
                for listing in listings
            )

            user_ids = listings.values_list("user_id", flat=True).distinct()
            for username in User.objects.filter(
                pk__in=user_ids,
                is_active=True,
                is_blocked=False,
            ).values_list("username", flat=True):
                urls.append(
                    f"{origin}{reverse('marketplace:profile', kwargs={'username': username})}"
                )

        result = submit_indexnow(urls)
        if not result.get("ok"):
            raise CommandError(f"IndexNow n'a pas accepté la soumission: {result}")

        self.stdout.write(
            self.style.SUCCESS(
                f"IndexNow: {len(set(urls))} URL(s) soumise(s). HTTP {result.get('status')}"
            )
        )
