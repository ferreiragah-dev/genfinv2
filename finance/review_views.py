from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .models import CategoryRule, ReviewDismissal, ReviewPair, Transaction
from .review_services import (
    available_rows,
    confirm_pair,
    save_rule,
    suggestions,
    validate_category,
    validate_pair,
)
from .services import month_bounds


def page_response(request, error=None):
    tab = request.GET.get("tab", "categories")
    if tab not in ("categories", "matches", "decisions", "rules"):
        tab = "categories"
    rows = Transaction.objects.filter(owner=request.user).select_related("vehicle")
    if request.GET.get("q"):
        rows = rows.filter(description__icontains=request.GET["q"][:120])
    if request.GET.get("month"):
        rows = rows.filter(date__range=month_bounds(request.GET["month"]))
    context = {
        "title": "Revisar movimentações",
        "page": "review",
        "tab": tab,
        "review_error": error,
        "pending_review_count": Transaction.objects.filter(
            owner=request.user, reviewed_at__isnull=True, review_role="normal"
        ).count(),
    }
    if tab == "categories":
        if request.GET.get("state") != "all":
            rows = rows.filter(reviewed_at__isnull=True, review_role="normal")
        context["page_obj"] = Paginator(rows, 15).get_page(request.GET.get("page"))
    elif tab == "matches":
        anchors = (
            available_rows(request.user)
            .filter(pk__in=rows.values("pk"))
            .filter(
                Q(pluggy_id__isnull=True)
                | Q(
                    pluggy_id__isnull=False,
                    kind="expense",
                    status="paid",
                    bank_account__isnull=False,
                )
            )
        )
        context["page_obj"] = Paginator(anchors, 15).get_page(request.GET.get("page"))
        context["suggestions"] = suggestions(request.user, context["page_obj"])
        context["dismissed_count"] = ReviewDismissal.objects.filter(owner=request.user).count()
    elif tab == "decisions":
        context["page_obj"] = Paginator(
            ReviewPair.objects.filter(owner=request.user).select_related("first", "second"), 15
        ).get_page(request.GET.get("page"))
    else:
        context["page_obj"] = Paginator(
            CategoryRule.objects.filter(owner=request.user).select_related("vehicle"), 15
        ).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    context["query_params"] = params.urlencode()
    return render(request, "review.html", context, status=400 if error else 200)


@never_cache
@login_required
def index(request):
    return page_response(request)


def record(model, request, key):
    try:
        pk = int(request.POST.get(key, ""))
        if not 0 < pk < 2**63:
            raise ValueError()
    except ValueError:
        raise ValidationError("Selecione um registro válido.") from None
    return get_object_or_404(model, pk=pk, owner=request.user)


def vehicle_id(request):
    try:
        value = int(request.POST["vehicle"]) if request.POST.get("vehicle") else None
        if value is not None and not 0 < value < 2**63:
            raise ValueError()
        return value
    except ValueError:
        raise ValidationError("Selecione um veículo válido.") from None


@never_cache
@login_required
@require_POST
def action(request):
    tab = "categories"
    try:
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            operation = request.POST.get("action")
            if operation == "category":
                row = record(Transaction, request, "transaction_id")
                if request.POST.get("version") != row.review_version:
                    raise ValidationError(
                        "A movimentação mudou. Confira os dados atualizados e tente novamente."
                    )
                category = request.POST.get("category", "")
                vehicle = validate_category(request.user, row.kind, category, vehicle_id(request))
                row.category, row.vehicle_id = category, vehicle
                row.category_locked, row.reviewed_at = True, timezone.now()
                row.save()
                count = 0
                if request.POST.get("create_rule"):
                    count = save_rule(
                        request.user, request.POST.get("pattern", ""), row.kind, category, vehicle
                    )
                message = (
                    f"Categoria salva. Regra aplicada a {count} outras movimentações."
                    if request.POST.get("create_rule")
                    else "Categoria salva e movimentação revisada."
                )
            elif operation == "rule":
                tab = "rules"
                rule = (
                    record(CategoryRule, request, "rule_id")
                    if request.POST.get("rule_id")
                    else None
                )
                count = save_rule(
                    request.user,
                    request.POST.get("pattern", ""),
                    request.POST.get("kind"),
                    request.POST.get("category"),
                    vehicle_id(request),
                    rule.pk if rule else None,
                )
                message = (
                    f"Regra salva e aplicada a {count} movimentações sem categoria personalizada."
                )
            elif operation in ("confirm", "dismiss"):
                tab = "matches"
                first = record(Transaction, request, "first_id")
                second = record(Transaction, request, "second_id")
                if (
                    request.POST.get("first_version") != first.review_version
                    or request.POST.get("second_version") != second.review_version
                ):
                    raise ValidationError(
                        "As movimentações mudaram. Confira as sugestões atualizadas antes de confirmar."
                    )
                kind = request.POST.get("kind")
                validate_pair(first, second, kind)
                if operation == "confirm":
                    confirm_pair(first, second, kind)
                    message = "Conciliação confirmada. Os totais foram atualizados. Você pode desfazer em Decisões."
                else:
                    ReviewDismissal.objects.get_or_create(
                        owner=request.user, first=first, second=second, kind=kind
                    )
                    message = "Sugestão descartada. Os lançamentos continuam nos totais."
            elif operation == "undo":
                tab = "decisions"
                record(ReviewPair, request, "pair_id").delete()
                message = "Conciliação desfeita. Os lançamentos voltaram aos totais."
            elif operation == "delete_rule":
                tab = "rules"
                record(CategoryRule, request, "rule_id").delete()
                message = "Regra removida. As categorias já atribuídas foram preservadas."
            elif operation == "restore_suggestions":
                tab = "matches"
                ReviewDismissal.objects.filter(owner=request.user).delete()
                message = "As sugestões descartadas podem aparecer novamente."
            else:
                raise ValidationError("Ação inválida.")
    except ValidationError as exc:
        return page_response(request, " ".join(exc.messages))
    messages.success(request, message)
    return redirect(reverse_review(tab))


def reverse_review(tab):
    from django.urls import reverse

    return reverse("review") + "?tab=" + tab
