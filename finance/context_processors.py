NAVIGATION = [
    ("dashboard", "Visão geral", "layer-group", "/"),
    ("transactions", "Transações", "arrow-right-arrow-left", "/transactions/"),
    ("credit_cards", "Cartões de crédito", "credit-card", "/credit-cards/"),
    ("fixed_expenses", "Despesas fixas", "receipt", "/fixed-expenses/"),
    ("fixed_incomes", "Receitas fixas", "wallet", "/fixed-incomes/"),
    ("reserves", "Reservas e metas", "bullseye", "/reserves/"),
    ("vehicles", "Veículos", "car-side", "/vehicles/"),
    ("trips", "Viagens", "plane", "/trips/"),
]


def navigation(request):
    context = {"navigation": NAVIGATION, "is_demo": request.session.get("is_demo", False)}
    if request.user.is_authenticated:
        from .models import Preferences, Transaction, PortfolioItem
        from .constants import VEHICLE_CATEGORIES
        from .forms import CATEGORIES

        prefs = Preferences.objects.filter(owner=request.user).first()
        pending = Transaction.objects.filter(owner=request.user, status="pending").order_by("date")
        context.update(
            vehicles_options=PortfolioItem.objects.filter(owner=request.user, kind="vehicles"),
            vehicle_categories=VEHICLE_CATEGORIES,
            categories_options=CATEGORIES,
            notifications_read=prefs.notifications_read if prefs else False,
            pending=pending[:3],
            pending_count=pending.count(),
        )
    return context
