"""Authenticated Open Finance endpoints. Browser data never establishes item ownership."""

import json
from functools import wraps

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .models import BankConnection, OpenFinanceIdentity
from .open_finance import allowed_connector, identifier, verify_item
from .pluggy import PluggyClient, PluggyError, configured


def is_demo(request):
    return request.session.get("is_demo", False) or not request.user.has_usable_password()


def finance_api(view):
    @never_cache
    @login_required
    @require_POST
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if is_demo(request):
            return JsonResponse(
                {"message": "Crie uma conta pessoal para conectar uma instituição de teste."},
                status=403,
            )
        try:
            return view(request, *args, **kwargs)
        except PluggyError as exc:
            return JsonResponse({"message": str(exc)}, status=403 if exc.status == 403 else 502)

    return wrapped


@never_cache
@login_required
def index(request):
    return render(
        request,
        "open_finance.html",
        {
            "page": "open_finance",
            "title": "Open Finance",
            "connections": BankConnection.objects.filter(owner=request.user).prefetch_related(
                "accounts"
            ),
            "pluggy_ready": configured(),
            "sandbox": settings.PLUGGY_SANDBOX,
            "connection_allowed": configured() and not is_demo(request),
        },
    )


@finance_api
def connect_token(request):
    connection = None
    if request.POST.get("connection_id"):
        try:
            pk = int(request.POST["connection_id"])
        except ValueError:
            return JsonResponse({"message": "Conexão inválida."}, status=400)
        connection = get_object_or_404(BankConnection, pk=pk, owner=request.user, active=True)
    identity, _ = OpenFinanceIdentity.objects.get_or_create(owner=request.user)
    client = PluggyClient()
    connectors = [c["id"] for c in client.connectors() if allowed_connector(c)]
    if not connectors:
        raise PluggyError("Nenhuma instituição está disponível para este ambiente.")
    if connection:
        verify_item(client.item(connection.item_id), identity, connection.item_id)
    return JsonResponse(
        {
            "accessToken": client.connect_token(
                identity.client_user_id, connection.item_id if connection else None
            ),
            "connectorIds": connectors,
            "includeSandbox": settings.PLUGGY_SANDBOX,
            "updateItem": str(connection.item_id) if connection else None,
        }
    )


@finance_api
def register_item(request):
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict):
            raise ValueError()
        item_id = identifier(data.get("itemId"))
    except (ValueError, PluggyError):
        return JsonResponse({"message": "Conexão inválida."}, status=400)
    identity = get_object_or_404(OpenFinanceIdentity, owner=request.user)
    item = PluggyClient().item(item_id)
    verify_item(item, identity, item_id)
    with transaction.atomic():
        connection, created = BankConnection.objects.select_for_update().get_or_create(
            item_id=item_id,
            defaults={
                "owner": request.user,
                "institution": str(item["connector"].get("name") or "Instituição")[:120],
                "sandbox": settings.PLUGGY_SANDBOX,
            },
        )
        if connection.owner_id != request.user.pk or not connection.active:
            return JsonResponse({"message": "Esta conexão não está disponível."}, status=403)
        if not connection.locked_until or connection.locked_until <= timezone.now():
            connection.next_sync_at = timezone.now()
            connection.status = "QUEUED"
            connection.sync_message = "Aguardando importação."
            connection.save()
    return JsonResponse(
        {"message": "Conexão salva. A importação será iniciada em instantes.", "id": connection.pk},
        status=201 if created else 200,
    )


@finance_api
def sync(request, pk):
    with transaction.atomic():
        connection = get_object_or_404(
            BankConnection.objects.select_for_update(), pk=pk, owner=request.user, active=True
        )
        if not connection.locked_until or connection.locked_until <= timezone.now():
            connection.next_sync_at = timezone.now()
            connection.status = "QUEUED"
            connection.sync_message = "Aguardando importação."
            connection.save()
    return JsonResponse({"message": "Importação solicitada."}, status=202)


@finance_api
def disconnect(request, pk):
    with transaction.atomic():
        connection = get_object_or_404(
            BankConnection.objects.select_for_update(), pk=pk, owner=request.user
        )
        if connection.active:
            PluggyClient().delete_item(connection.item_id)
            connection.active = False
            connection.status = "DISCONNECTED"
            connection.locked_until = None
            connection.sync_message = "Conexão removida da Pluggy. Histórico importado preservado."
            connection.save()
    return JsonResponse({"message": "Instituição desconectada. Seu histórico foi preservado."})


@never_cache
@login_required
def status(request):
    return JsonResponse(
        {
            "connections": list(
                BankConnection.objects.filter(owner=request.user).values(
                    "id", "status", "sync_message", "last_synced_at", "active"
                )
            )
        }
    )
