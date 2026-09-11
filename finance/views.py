"""Thin HTTP adapters. All queries are explicitly scoped to the signed-in user."""

import csv
import json
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .demo import create_demo_user
from .forms import TransactionForm, PortfolioForm, ProfileForm, RegistrationForm, CATEGORIES
from .models import Transaction, PortfolioItem, Preferences
from .services import dashboard_data, month_bounds, total
from .vehicle_services import vehicle_month_data

PAGE_CONFIG = {
    "credit_cards": (
        "Cartões de crédito",
        "Limites, faturas e mais controle sobre suas compras.",
        "Novo cartão",
        "credit-card",
        "Fatura atual",
        "Limite total",
    ),
    "vehicles": (
        "Veículos",
        "Seu patrimônio sobre rodas, em um só lugar.",
        "Novo veículo",
        "car-side",
        "Valor estimado",
        "Meta de troca",
    ),
    "trips": (
        "Viagens",
        "Planeje a próxima experiência. Cuide de cada detalhe.",
        "Nova viagem",
        "plane",
        "Valor reservado",
        "Orçamento",
    ),
    "fixed_expenses": (
        "Despesas fixas",
        "Previsibilidade para organizar melhor o seu mês.",
        "Nova despesa fixa",
        "receipt",
        "Valor mensal",
        "Meta",
    ),
    "fixed_incomes": (
        "Receitas fixas",
        "Uma visão clara do dinheiro que chega todo mês.",
        "Nova receita fixa",
        "wallet",
        "Valor mensal",
        "Meta",
    ),
    "reserves": (
        "Reservas e metas",
        "Transforme seus planos em conquistas, um passo de cada vez.",
        "Nova reserva",
        "bullseye",
        "Valor guardado",
        "Objetivo",
    ),
}


class GenFinLoginView(LoginView):
    template_name = "login.html"
    redirect_authenticated_user = True


def landing(request):
    return render(request, "landing.html")


def register(request):
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        request.session.pop("is_demo", None)
        login(request, user)
        return redirect("dashboard")
    return render(request, "login.html", {"form": form, "registration": True})


@require_POST
def demo(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    user = create_demo_user()
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session["is_demo"] = True
    request.session.set_expiry(86400)
    return redirect("dashboard")


@login_required
def dashboard(request):
    context = dashboard_data(request.user, request.GET.get("month"))
    prefs, _ = Preferences.objects.get_or_create(owner=request.user)
    context.update(
        page="dashboard",
        title="Visão geral",
        categories_options=CATEGORIES,
        preferences=prefs.widgets,
        notifications_read=prefs.notifications_read,
    )
    return render(request, "dashboard.html", context)


def filtered_transactions(request):
    rows = Transaction.objects.filter(owner=request.user).select_related("vehicle")
    if request.GET.get("q"):
        rows = rows.filter(description__icontains=request.GET["q"][:120])
    if request.GET.get("kind") in ["income", "expense"]:
        rows = rows.filter(kind=request.GET["kind"])
    if request.GET.get("status") in ["paid", "pending"]:
        rows = rows.filter(status=request.GET["status"])
    if request.GET.get("month"):
        rows = rows.filter(date__range=month_bounds(request.GET["month"]))
    return rows


@login_required
def transactions(request):
    rows = filtered_transactions(request)
    page_obj = Paginator(rows, 12).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return render(
        request,
        "transactions.html",
        {
            "page": "transactions",
            "title": "Transações",
            "page_obj": page_obj,
            "recent": page_obj,
            "count": rows.count(),
            "income": total(rows.filter(kind="income", status="paid")),
            "expense": total(rows.filter(kind="expense", status="paid")),
            "pending_total": total(rows.filter(status="pending")),
            "categories_options": CATEGORIES,
            "query_params": params.urlencode(),
            "editable": True,
        },
    )


@login_required
def portfolio(request, kind):
    if kind not in PAGE_CONFIG:
        return HttpResponse(status=404)
    title, subtitle, action, icon, amount_label, target_label = PAGE_CONFIG[kind]
    items = PortfolioItem.objects.filter(owner=request.user, kind=kind)
    vehicle_context = {}
    if kind == "vehicles":
        vehicle_context = vehicle_month_data(request.user, request.GET.get("month"), items)
        items = vehicle_context.pop("items")
        vehicle_context["vehicle_page"] = Paginator(vehicle_context.pop("history"), 12).get_page(
            request.GET.get("page")
        )
    return render(
        request,
        f"{kind}.html",
        {
            "page": kind,
            "title": title,
            "subtitle": subtitle,
            "action_label": action,
            "icon": icon,
            "items": items,
            "total": sum((i.amount for i in items), Decimal(0)),
            "target_total": sum((i.target for i in items), Decimal(0)),
            "amount_label": amount_label,
            "target_label": target_label,
            "recurring": kind in ["fixed_expenses", "fixed_incomes"],
            "categories_options": CATEGORIES,
            **vehicle_context,
        },
    )


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Perfil atualizado com sucesso.")
        return redirect("profile")
    return render(request, "profile.html", {"page": "profile", "title": "Meu perfil", "form": form})


@login_required
def design_system(request):
    return render(
        request, "design_system.html", {"page": "design_system", "title": "Design System"}
    )


def serialize_transaction(obj):
    return {
        "id": obj.id,
        "description": obj.description,
        "amount": str(obj.amount),
        "kind": obj.kind,
        "category": obj.category,
        "date": obj.date.isoformat(),
        "status": obj.status,
        "account": obj.account,
        "vehicle": obj.vehicle_id,
    }


@login_required
def transaction_detail(request, pk):
    return JsonResponse(
        serialize_transaction(get_object_or_404(Transaction, pk=pk, owner=request.user))
    )


@login_required
@require_POST
def transaction_save(request, pk=None):
    instance = get_object_or_404(Transaction, pk=pk, owner=request.user) if pk else None
    if instance and instance.pluggy_id:
        return JsonResponse(
            {"message": "Movimentações bancárias são atualizadas pela sincronização."}, status=409
        )
    form = TransactionForm(request.POST, instance=instance, user=request.user)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors.get_json_data()}, status=400)
    obj = form.save(commit=False)
    obj.owner = request.user
    obj.save()
    return JsonResponse(
        {"message": "Transação atualizada." if pk else "Transação adicionada.", "id": obj.id}
    )


@login_required
@require_POST
def transaction_delete(request, pk):
    instance = get_object_or_404(Transaction, pk=pk, owner=request.user)
    if instance.pluggy_id:
        return JsonResponse(
            {"message": "Movimentações bancárias são atualizadas pela sincronização."}, status=409
        )
    instance.delete()
    return JsonResponse({"message": "Transação excluída."})


@login_required
def portfolio_detail(request, pk):
    obj = get_object_or_404(PortfolioItem, pk=pk, owner=request.user)
    return JsonResponse(
        {
            "id": obj.id,
            "kind": obj.kind,
            "name": obj.name,
            "subtitle": obj.subtitle,
            "amount": str(obj.amount),
            "target": str(obj.target),
            "day": obj.day,
            "color": obj.color,
            "due_date": obj.due_date.isoformat() if obj.due_date else "",
        }
    )


@login_required
@require_POST
def portfolio_save(request, pk=None):
    instance = get_object_or_404(PortfolioItem, pk=pk, owner=request.user) if pk else None
    form = PortfolioForm(request.POST, instance=instance)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors.get_json_data()}, status=400)
    obj = form.save(commit=False)
    obj.owner = request.user
    obj.save()
    return JsonResponse({"message": "Registro salvo.", "id": obj.id})


@login_required
@require_POST
def portfolio_delete(request, pk):
    get_object_or_404(PortfolioItem, pk=pk, owner=request.user).delete()
    return JsonResponse({"message": "Registro excluído."})


@login_required
@require_POST
def preferences(request):
    try:
        data = json.loads(request.body)
    except (ValueError, TypeError):
        return JsonResponse({"message": "Dados inválidos."}, status=400)
    if not isinstance(data, dict):
        return JsonResponse({"message": "Dados inválidos."}, status=400)
    prefs, _ = Preferences.objects.get_or_create(owner=request.user)
    if isinstance(data.get("widgets"), dict):
        allowed = {
            "cashflow",
            "categories",
            "heatmap",
            "rankings",
            "timeline",
            "recent",
            "score",
            "goals",
            "alerts",
        }
        prefs.widgets = {
            key: bool(value) for key, value in data["widgets"].items() if key in allowed
        }
    if data.get("notifications_read") is True:
        prefs.notifications_read = True
    prefs.save()
    return JsonResponse({"message": "Preferências atualizadas."})


@login_required
def export_transactions(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="genfin-transacoes.csv"'
    response.write("\ufeff")
    writer = csv.writer(response, delimiter=";")
    writer.writerow(
        ["Descrição", "Tipo", "Categoria", "Valor (BRL)", "Data", "Status", "Conta", "Veículo"]
    )

    def safe(value):
        value = str(value)
        return "'" + value if value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else value

    for row in filtered_transactions(request).iterator():
        writer.writerow(
            [
                safe(row.description),
                row.get_kind_display(),
                safe(row.category),
                str(row.amount).replace(".", ","),
                row.date.isoformat(),
                row.get_status_display(),
                safe(row.account),
                safe(row.vehicle.name) if row.vehicle else "",
            ]
        )
    return response
