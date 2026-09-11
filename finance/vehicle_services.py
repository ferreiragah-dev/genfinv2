"""Vehicle costs reuse ledger entries, avoiding a second source of monetary truth."""

from django.db.models import Sum
from .constants import VEHICLE_CATEGORIES, VEHICLE_COST_TYPES
from .models import Transaction
from .services import ZERO, MONTHS, month_bounds


def vehicle_month_data(user, month, vehicles):
    start, end = month_bounds(month)
    items = list(vehicles)
    history = (
        Transaction.objects.for_totals()
        .filter(
            owner=user,
            vehicle__owner=user,
            vehicle__kind="vehicles",
            kind="expense",
            category__in=VEHICLE_CATEGORIES,
            date__range=(start, end),
        )
        .select_related("vehicle")
    )
    grouped = (
        history.filter(status="paid")
        .values("vehicle_id", "category")
        .annotate(total=Sum("amount"))
        .order_by()
    )
    costs = {(row["vehicle_id"], row["category"]): row["total"] for row in grouped}
    for vehicle in items:
        vehicle.monthly_costs = [
            {
                "category": category,
                "label": label,
                "icon": icon,
                "amount": costs.get((vehicle.pk, category), ZERO),
            }
            for category, label, icon in VEHICLE_COST_TYPES
        ]
        vehicle.monthly_total = sum((entry["amount"] for entry in vehicle.monthly_costs), ZERO)
    return {
        "items": items,
        "vehicle_month_total": sum((vehicle.monthly_total for vehicle in items), ZERO),
        "month": start.strftime("%Y-%m"),
        "month_label": f"{MONTHS[start.month - 1]} {start.year}",
        "history": history,
    }
