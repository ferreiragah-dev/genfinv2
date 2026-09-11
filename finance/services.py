"""Financial calculations are isolated from HTTP and rendering concerns."""

import calendar
from datetime import date, timedelta
from decimal import Decimal
from django.db.models import Sum
from .models import Transaction, PortfolioItem

ZERO = Decimal("0.00")
COLORS = ["#4F7CFF", "#A78BFA", "#38BDF8", "#F59E0B", "#22C55E", "#FB7185", "#64748B"]
MONTHS = [
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
]


def month_bounds(value=None):
    today = date.today()
    try:
        year, month = map(int, (value or today.strftime("%Y-%m")).split("-"))
        start = date(year, month, 1)
    except (ValueError, TypeError):
        start = today.replace(day=1)
    end = start.replace(day=calendar.monthrange(start.year, start.month)[1])
    return start, end


def total(queryset):
    return queryset.aggregate(value=Sum("amount"))["value"] or ZERO


def category_totals(queryset):
    groups = list(queryset.values("category").annotate(total=Sum("amount")).order_by("-total"))
    full = sum((g["total"] for g in groups), ZERO)
    for index, group in enumerate(groups):
        group["percent"] = round(group["total"] / full * 100) if full else 0
        group["color"] = COLORS[index % len(COLORS)]
    return groups


def dashboard_data(user, month=None):
    start, end = month_bounds(month)
    records = Transaction.objects.for_totals().filter(owner=user).select_related("vehicle")
    selected = records.filter(date__range=(start, end))
    paid = selected.filter(status="paid")
    income, expense = total(paid.filter(kind="income")), total(paid.filter(kind="expense"))
    balance = income - expense
    all_paid = records.filter(status="paid", date__lte=end)
    cash = total(all_paid.filter(kind="income")) - total(all_paid.filter(kind="expense"))
    items = PortfolioItem.objects.filter(owner=user)
    assets = total(items.filter(kind__in=["reserves", "vehicles"]))
    liabilities = total(items.filter(kind="credit_cards"))
    wealth = cash + assets - liabilities
    previous_end = start - timedelta(days=1)
    previous = records.filter(
        date__range=(previous_end.replace(day=1), previous_end), status="paid"
    )
    previous_income = total(previous.filter(kind="income"))
    previous_expense = total(previous.filter(kind="expense"))

    def delta(current, old):
        return round((current - old) / abs(old) * 100, 1) if old else None

    categories = category_totals(paid.filter(kind="expense"))
    income_categories = category_totals(paid.filter(kind="income"))
    daily = {d: {"income": ZERO, "expense": ZERO} for d in range(1, end.day + 1)}
    for row in paid.values("date", "kind").annotate(value=Sum("amount")):
        daily[row["date"].day][row["kind"]] += row["value"]
    cumulative = {"income": [], "expense": []}
    totals = {"income": ZERO, "expense": ZERO}
    for day in daily.values():
        for kind in totals:
            totals[kind] += day[kind]
            cumulative[kind].append(float(totals[kind]))
    saving_rate = max(0, min(100, round(balance / income * 100))) if income else 0
    pending_count = selected.filter(status="pending").count()
    # Transparent heuristic: saving capacity (60%) + completion rate (40%).
    paid_ratio = paid.count() / selected.count() if selected.exists() else 0
    score = min(100, round(min(saving_rate / 30, 1) * 60 + paid_ratio * 40))
    heat_end = end
    heat_start = heat_end - timedelta(days=90)
    activity = {
        r["date"]: r["value"]
        for r in records.filter(date__range=(heat_start, heat_end), kind="expense", status="paid")
        .values("date")
        .annotate(value=Sum("amount"))
    }
    heatmap = []
    for offset in range(91):
        day = heat_start + timedelta(days=offset)
        amount = activity.get(day, ZERO)
        heatmap.append(
            {
                "date": day,
                "amount": amount,
                "level": 0
                if not amount
                else 1
                if amount < 100
                else 2
                if amount < 300
                else 3
                if amount < 800
                else 4,
            }
        )
    return {
        "month": start.strftime("%Y-%m"),
        "month_label": f"{MONTHS[start.month - 1]} {start.year}",
        "income": income,
        "expense": expense,
        "balance": balance,
        "wealth": wealth,
        "income_delta": delta(income, previous_income),
        "expense_delta": delta(expense, previous_expense),
        "saving_rate": saving_rate,
        "score": score,
        "score_offset": round(251.3 * (1 - score / 100), 2),
        "score_label": "Excelente"
        if score >= 80
        else "Em equilíbrio"
        if score >= 50
        else "Precisa de atenção",
        "categories": categories,
        "income_categories": income_categories,
        "recent": selected[:5],
        "timeline": selected[:4],
        "goals": items.filter(kind="reserves")[:3],
        "pending": selected.filter(status="pending")[:3],
        "pending_count": pending_count,
        "heatmap": heatmap,
        "chart_data": {
            "labels": [f"{d:02d}" for d in daily],
            "income": cumulative["income"],
            "expense": cumulative["expense"],
            "dailyIncome": [float(d["income"]) for d in daily.values()],
            "dailyExpense": [float(d["expense"]) for d in daily.values()],
            "categories": [
                {"label": c["category"], "value": float(c["total"]), "color": c["color"]}
                for c in categories
            ],
        },
    }
