"""User-approved reconciliation and local categorization; no changes sent to the bank."""

from datetime import timedelta
import unicodedata

from django.core.exceptions import ValidationError
from django.utils import timezone

from .constants import VEHICLE_CATEGORIES
from .forms import CATEGORIES
from .models import CategoryRule, PortfolioItem, ReviewDismissal, ReviewPair, Transaction


def normalize(text):
    return " ".join(
        "".join(
            c
            for c in unicodedata.normalize("NFKD", text.casefold())
            if not unicodedata.combining(c)
        ).split()
    )


def validate_category(user, kind, category, vehicle_id=None):
    if category not in CATEGORIES:
        raise ValidationError("Selecione uma categoria válida.")
    if category not in VEHICLE_CATEGORIES:
        return None
    vehicle = PortfolioItem.objects.filter(pk=vehicle_id, owner=user, kind="vehicles").first()
    if kind != "expense" or not vehicle:
        raise ValidationError(
            "Para IPVA, seguro ou combustível, selecione uma despesa e um veículo seu."
        )
    return vehicle.pk


def import_category(values, existing, rules):
    """Explicit choices win. Newest matching rule wins among automatic choices."""
    valid_existing = existing and not (
        existing.category in VEHICLE_CATEGORIES and values["kind"] != "expense"
    )
    if valid_existing and existing.category_locked:
        return {"category": existing.category, "vehicle_id": existing.vehicle_id}
    for rule in rules:
        if rule.kind == values["kind"] and rule.match_text in normalize(values["description"]):
            return {
                "category": rule.category,
                "vehicle_id": rule.vehicle_id,
                "category_locked": False,
                "reviewed_at": existing.reviewed_at
                if existing and existing.reviewed_at
                else timezone.now(),
            }
    if valid_existing:
        return {"category": existing.category, "vehicle_id": existing.vehicle_id}
    return {"category": "Outros", "vehicle_id": None, "category_locked": False, "reviewed_at": None}


def save_rule(user, pattern, kind, category, vehicle_id=None, rule_id=None):
    pattern = normalize(pattern)
    if not 2 <= len(pattern) <= 120 or kind not in ("income", "expense"):
        raise ValidationError("Informe um texto de 2 a 120 caracteres e o tipo da movimentação.")
    vehicle_id = validate_category(user, kind, category, vehicle_id)
    if rule_id:
        rule = CategoryRule.objects.get(pk=rule_id, owner=user)
        if (
            CategoryRule.objects.filter(owner=user, match_text=pattern, kind=kind)
            .exclude(pk=rule.pk)
            .exists()
        ):
            raise ValidationError("Já existe uma regra com esse texto e tipo.")
        rule.match_text, rule.kind, rule.category, rule.vehicle_id = (
            pattern,
            kind,
            category,
            vehicle_id,
        )
        rule.save()
    else:
        rule, _ = CategoryRule.objects.update_or_create(
            owner=user,
            match_text=pattern,
            kind=kind,
            defaults={"category": category, "vehicle_id": vehicle_id},
        )
    rules = list(CategoryRule.objects.filter(owner=user))
    count = 0
    for row in Transaction.objects.filter(
        owner=user, category_locked=False, review_role="normal"
    ).iterator():
        if row.kind != kind or pattern not in normalize(row.description):
            continue
        values = import_category({"kind": row.kind, "description": row.description}, row, rules)
        for name, value in values.items():
            setattr(row, name, value)
        row.save()
        count += 1
    return count


def available_rows(user):
    return Transaction.objects.filter(owner=user, review_role="normal")


def validate_pair(first, second, kind):
    if first.pk == second.pk or first.owner_id != second.owner_id:
        raise ValidationError("Selecione duas movimentações diferentes da sua conta.")
    if first.amount != second.amount or abs((first.date - second.date).days) > 3:
        raise ValidationError(
            "Os valores ou as datas mudaram. Atualize as sugestões antes de confirmar."
        )
    if kind == "duplicate":
        if first.pluggy_id or not second.pluggy_id or first.kind != second.kind:
            raise ValidationError(
                "Uma duplicata deve relacionar um lançamento manual a um importado do mesmo tipo."
            )
    elif kind == "transfer":
        if (
            first.kind != "expense"
            or second.kind != "income"
            or first.status != "paid"
            or second.status != "paid"
            or not first.bank_account_id
            or not second.bank_account_id
            or first.bank_account_id == second.bank_account_id
        ):
            raise ValidationError(
                "Confirme uma saída e uma entrada concluídas em duas contas bancárias diferentes."
            )
    else:
        raise ValidationError("Tipo de conciliação inválido.")
    if (
        first.review_role != "normal"
        or second.review_role == "duplicate"
        or (kind == "transfer" and second.review_role != "normal")
    ):
        raise ValidationError(
            "Uma dessas movimentações já foi conciliada. Desfaça a decisão anterior primeiro."
        )


def confirm_pair(first, second, kind):
    validate_pair(first, second, kind)
    if kind == "duplicate" and first.category_locked and not second.category_locked:
        second.category, second.vehicle_id = first.category, first.vehicle_id
        second.category_locked = True
        second.save()
    pair = ReviewPair.objects.create(owner_id=first.owner_id, first=first, second=second, kind=kind)
    Transaction.objects.filter(pk=first.pk).update(review_role=kind, reviewed_at=timezone.now())
    Transaction.objects.filter(pk=second.pk).update(
        review_role="transfer" if kind == "transfer" else second.review_role,
        reviewed_at=timezone.now(),
    )
    ReviewDismissal.objects.filter(first=first, second=second, kind=kind).delete()
    return pair


def suggestions(user, anchors):
    result = []
    for first in anchors:
        kind = "duplicate" if not first.pluggy_id else "transfer"
        candidates = available_rows(user).filter(
            amount=first.amount,
            date__range=(first.date - timedelta(days=3), first.date + timedelta(days=3)),
        )
        if kind == "duplicate":
            candidates = Transaction.objects.filter(
                owner=user,
                amount=first.amount,
                date__range=(first.date - timedelta(days=3), first.date + timedelta(days=3)),
                pluggy_id__isnull=False,
                kind=first.kind,
            ).exclude(review_role="duplicate")
        else:
            candidates = candidates.filter(
                kind="income", status="paid", bank_account__isnull=False
            ).exclude(bank_account_id=first.bank_account_id)
        dismissed = ReviewDismissal.objects.filter(owner=user, first=first, kind=kind).values_list(
            "second_id", flat=True
        )
        for second in candidates.exclude(pk__in=dismissed).order_by("date", "pk")[:5]:
            result.append({"first": first, "second": second, "kind": kind})
    return result
