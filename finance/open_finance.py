"""Import bank cash movements atomically, with owner checks and repeatable reconciliation."""

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from time import monotonic
from uuid import UUID

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import BankAccount, BankConnection, OpenFinanceIdentity, Transaction
from .pluggy import PluggyClient, PluggyError


def allowed_connector(connector):
    if settings.PLUGGY_SANDBOX:
        return connector.get("isSandbox") is True
    return connector.get("isSandbox") is False and connector.get("isOpenFinance") is True


def verify_item(item, identity, item_id):
    if item.get("clientUserId") != str(identity.client_user_id) or item.get("id") != str(item_id):
        raise PluggyError("Esta conexão não pertence à sua conta.", status=403)
    if not allowed_connector(item.get("connector") or {}):
        raise PluggyError("Esta instituição não está habilitada no ambiente atual.", status=403)


def money(value, max_digits=14):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or abs(amount) >= Decimal(10) ** (max_digits - 2):
            raise ValueError()
        return amount.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        raise PluggyError(
            "A instituição retornou um valor inválido. Nenhum dado foi importado."
        ) from None


def identifier(value):
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise PluggyError("A instituição retornou um identificador inválido.") from None


def transaction_values(row, account, connection, start, end):
    if identifier(row.get("accountId")) != account.external_id:
        raise PluggyError("A instituição retornou dados de outra conta.")
    # Only BRL bank cash movements enter the existing BRL dashboard.
    if row.get("currencyCode") != "BRL":
        return None
    amount = money(row.get("amount"))
    if not amount:
        return None
    if row.get("status") not in ("POSTED", "PENDING") or row.get("type") not in ("CREDIT", "DEBIT"):
        raise PluggyError("A instituição retornou uma movimentação com status desconhecido.")
    try:
        raw_date = row["date"]
        if len(raw_date) == 10:
            source_date = local_date = date.fromisoformat(raw_date)
        else:
            posted = parse_datetime(raw_date)
            if posted is None or timezone.is_naive(posted):
                raise ValueError()
            source_date = posted.date()
            local_date = timezone.localtime(posted).date()
        if not start <= source_date <= end:
            raise ValueError()
    except (ValueError, TypeError, KeyError):
        raise PluggyError("A instituição retornou uma data inválida.") from None
    return {
        "owner_id": connection.owner_id,
        "bank_account": account,
        "pluggy_date": source_date,
        "description": str(row.get("description") or "Movimentação bancária")[:120],
        "amount": abs(amount),
        "kind": "income" if row["type"] == "CREDIT" else "expense",
        "category": "Outros",
        "date": local_date,
        "status": "paid" if row["status"] == "POSTED" else "pending",
        "account": f"{connection.institution} · {account.name}"[:60],
    }


def sync_connection(connection_id, lease, client=None):
    """Fetch outside the DB transaction, then commit only a complete, stable snapshot."""
    connection = BankConnection.objects.filter(pk=connection_id).first()
    if not connection or not connection.active or connection.locked_until != lease:
        return
    client = client or PluggyClient()
    identity = OpenFinanceIdentity.objects.get(owner_id=connection.owner_id)
    item = client.item(connection.item_id)
    verify_item(item, identity, connection.item_id)
    if item.get("status") != "UPDATED":
        status = str(item.get("status") or "ERROR")[:40]
        waiting = status in ("UPDATING", "LOGIN_IN_PROGRESS")
        BankConnection.objects.filter(pk=connection_id, active=True, locked_until=lease).update(
            status=status,
            sync_message=(
                "A instituição ainda está preparando os dados."
                if waiting
                else "A conexão precisa de atenção. Use Renovar conexão."
            ),
            next_sync_at=timezone.now() + timedelta(minutes=1 if waiting else 30),
            locked_until=None,
        )
        return
    if item.get("executionStatus") != "SUCCESS":
        raise PluggyError(
            "A instituição retornou dados parciais. O histórico anterior foi preservado; use Renovar conexão."
        )
    end = timezone.now().date()
    start = end - timedelta(days=90)
    snapshot = []
    started = monotonic()
    accounts = client.accounts(connection.item_id)
    for row in accounts:
        if identifier(row.get("itemId")) != connection.item_id:
            raise PluggyError("A instituição retornou uma conta de outra conexão.")
        external_id = identifier(row.get("id"))
        entries = []
        if row.get("type") == "BANK" and row.get("currencyCode") == "BRL":
            entries = client.transactions(external_id, start, end)
        snapshot.append((row, external_id, entries))
        if monotonic() - started > 600:
            raise PluggyError("A importação demorou demais. Tente novamente mais tarde.")
    latest = client.item(connection.item_id)
    verify_item(latest, identity, connection.item_id)
    if (
        latest.get("status") != "UPDATED"
        or latest.get("executionStatus") != "SUCCESS"
        or latest.get("updatedAt") != item.get("updatedAt")
    ):
        raise PluggyError("Os dados estão sendo atualizados pela instituição. Tente novamente.")
    with transaction.atomic():
        # Same lock order as reset and item registration prevents a completed
        # import from recreating data after the account has been cleared.
        get_user_model().objects.select_for_update().get(pk=connection.owner_id)
        connection = BankConnection.objects.select_for_update().filter(pk=connection_id).first()
        if (
            not connection
            or not connection.active
            or connection.locked_until != lease
            or lease <= timezone.now()
        ):
            return
        for row, external_id, entries in snapshot:
            account, _ = BankAccount.objects.get_or_create(
                external_id=external_id,
                defaults={"connection": connection, "name": "", "kind": "", "currency": ""},
            )
            if account.connection_id != connection.pk:
                raise PluggyError("Esta conta já pertence a outra conexão.")
            account.name = str(row.get("name") or "Conta bancária")[:120]
            account.kind = str(row.get("type") or "UNKNOWN")[:20]
            account.currency = str(row.get("currencyCode") or "")[:3]
            account.balance = money(row["balance"], 18) if row.get("balance") is not None else None
            account.save()
            if account.kind != "BANK" or account.currency != "BRL":
                continue
            seen = set()
            for entry in entries:
                remote_id = identifier(entry.get("id"))
                values = transaction_values(entry, account, connection, start, end)
                if values is None:
                    continue
                existing = Transaction.objects.filter(pluggy_id=remote_id).first()
                if existing and (
                    existing.owner_id != connection.owner_id
                    or existing.bank_account_id != account.pk
                ):
                    raise PluggyError("Esta movimentação já pertence a outra conta.")
                Transaction.objects.update_or_create(pluggy_id=remote_id, defaults=values)
                seen.add(remote_id)
            # Reconcile removals/changed IDs only inside the fully fetched date window.
            # Older history and manually entered transactions are preserved.
            Transaction.objects.filter(
                bank_account=account, pluggy_date__range=(start, end), pluggy_id__isnull=False
            ).exclude(pluggy_id__in=seen).delete()
        connection.status = "UPDATED"
        connection.last_synced_at = timezone.now()
        connection.next_sync_at = timezone.now() + timedelta(hours=6)
        connection.locked_until = None
        connection.sync_message = "Dados disponíveis na Pluggy importados com sucesso."
        connection.save()
