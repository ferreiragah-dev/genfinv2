"""Password-confirmed financial reset; retain the login and personal profile."""

from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.views.decorators.debug import sensitive_variables

from .models import (
    BankConnection,
    OpenFinanceIdentity,
    PortfolioItem,
    Preferences,
    Transaction,
    CategoryRule,
)
from .pluggy import PluggyClient


@sensitive_variables("password")
@transaction.atomic
def reset_account(user_id, password):
    # Registration of new bank connections takes this same lock. In-flight widget
    # callbacks must validate the identity again after a reset rotates it.
    user = get_user_model().objects.select_for_update().get(pk=user_id)
    if not user.has_usable_password() or not user.check_password(password):
        raise ValidationError("Senha incorreta. Nenhum dado foi apagado.", code="invalid_password")

    connections = list(BankConnection.objects.select_for_update().filter(owner=user).order_by("pk"))
    active_connections = [connection for connection in connections if connection.active]
    if active_connections:
        client = PluggyClient()
        for connection in active_connections:
            # A missing remote item counts as already removed, so a retry after
            # partial provider failure is safe. Financial deletion happens last.
            client.delete_item(connection.item_id)

    Transaction.objects.filter(owner=user).delete()
    CategoryRule.objects.filter(owner=user).delete()
    PortfolioItem.objects.filter(owner=user).delete()
    BankConnection.objects.filter(owner=user).delete()  # Cascades to bank accounts.
    Preferences.objects.filter(owner=user).delete()
    OpenFinanceIdentity.objects.filter(owner=user).update(client_user_id=uuid4())
