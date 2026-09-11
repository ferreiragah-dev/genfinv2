"""Durable database queue: run once from a scheduler, or continuously with --watch."""

import time
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from django.db.models import Q
from django.utils import timezone

from finance.models import BankConnection
from finance.open_finance import sync_connection
from finance.pluggy import PluggyClient, PluggyError, configured


class Command(BaseCommand):
    help = "Import due Pluggy connections; --watch checks the durable queue every 5 seconds."

    def add_arguments(self, parser):
        parser.add_argument("--watch", action="store_true")

    def handle(self, *args, **options):
        if not configured():
            raise CommandError("Configure PLUGGY_CLIENT_ID and PLUGGY_CLIENT_SECRET on the server.")
        client = PluggyClient()
        try:
            while True:
                close_old_connections()
                now = timezone.now()
                due = BankConnection.objects.filter(active=True, next_sync_at__lte=now).filter(
                    Q(locked_until__isnull=True) | Q(locked_until__lte=now)
                )
                for pk in list(due.values_list("pk", flat=True)[:50]):
                    lease = timezone.now() + timedelta(minutes=20)
                    if not due.filter(pk=pk).update(
                        locked_until=lease,
                        status="SYNCING",
                        sync_message="Importando movimentações…",
                    ):
                        continue
                    try:
                        sync_connection(pk, lease, client)
                    except Exception as exc:
                        # Do not include exception tracebacks/provider payloads in financial-data logs.
                        message = (
                            str(exc)
                            if isinstance(exc, PluggyError)
                            else "Não foi possível importar os dados. Tente novamente."
                        )
                        BankConnection.objects.filter(
                            pk=pk, active=True, locked_until=lease
                        ).update(
                            status="ERROR",
                            sync_message=message[:250],
                            locked_until=None,
                            next_sync_at=timezone.now() + timedelta(minutes=30),
                        )
                        self.stderr.write(f"Connection {pk}: import failed ({type(exc).__name__}).")
                    else:
                        self.stdout.write(f"Connection {pk}: queue task completed.")
                if not options["watch"]:
                    break
                time.sleep(5)
        except KeyboardInterrupt:
            self.stdout.write("Pluggy worker stopped.")
