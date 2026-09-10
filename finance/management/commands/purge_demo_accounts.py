"""Remove inactive disposable demo accounts through an explicit command."""

from datetime import timedelta
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Remove demonstration users inactive for more than seven days."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=7)
        candidates = User.objects.filter(
            username__startswith="demo_", last_login__lt=cutoff, password__startswith="!"
        )
        count = candidates.count()
        if options["dry_run"]:
            self.stdout.write(f"{count} inactive demonstration accounts would be removed.")
        else:
            candidates.delete()
            self.stdout.write(
                self.style.SUCCESS(f"Removed {count} inactive demonstration accounts.")
            )
