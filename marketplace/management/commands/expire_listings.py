from django.core.management.base import BaseCommand
from marketplace.services import create_renewal_notifications, expire_due_listings


class Command(BaseCommand):
    help = "Expire les annonces arrivées à échéance et crée les notifications de renouvellement."

    def handle(self, *args, **options):
        expired = expire_due_listings(create_notifications=True)
        reminders = create_renewal_notifications()
        self.stdout.write(self.style.SUCCESS(f"Annonces expirées: {expired}. Rappels créés: {reminders}."))
