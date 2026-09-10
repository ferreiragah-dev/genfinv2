"""Create isolated, explicitly fictional data for each demo session."""

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4
from django.contrib.auth.models import User
from django.db import transaction
from .models import Transaction, PortfolioItem


@transaction.atomic
def create_demo_user():
    user = User.objects.create(
        username=f"demo_{uuid4().hex}",
        first_name="Gabriel",
        last_name="Silva",
        email="gabriel@example.com",
    )
    user.set_unusable_password()
    user.save(update_fields=["password"])
    start = date.today().replace(day=1)
    rows = [
        ("Salário mensal", "income", "Salário", "12500.00", 2, "paid", "Itaú · Conta principal"),
        ("Projeto de identidade visual", "income", "Freelance", "2850.00", 5, "paid", "Nubank"),
        (
            "Rendimento de investimentos",
            "income",
            "Investimentos",
            "420.80",
            7,
            "paid",
            "XP Investimentos",
        ),
        (
            "Aluguel do apartamento",
            "expense",
            "Moradia",
            "2400.00",
            3,
            "paid",
            "Itaú · Conta principal",
        ),
        ("Supermercado Pão de Açúcar", "expense", "Alimentação", "486.90", 4, "paid", "Nubank"),
        ("Restaurante Jardim", "expense", "Alimentação", "148.00", 6, "paid", "Nubank"),
        ("Uber", "expense", "Transporte", "32.90", 7, "paid", "Nubank"),
        ("Spotify Premium", "expense", "Lazer", "21.90", 8, "paid", "Nubank"),
        ("Amazon", "expense", "Compras", "289.90", 8, "paid", "Nubank"),
        ("Plano de saúde", "expense", "Saúde", "580.00", 9, "paid", "Itaú · Conta principal"),
        ("Café e companhia", "expense", "Alimentação", "42.50", 9, "paid", "Nubank"),
        ("Combustível", "expense", "Transporte", "250.00", 5, "paid", "Nubank"),
        (
            "Internet residencial",
            "expense",
            "Moradia",
            "119.90",
            15,
            "pending",
            "Itaú · Conta principal",
        ),
        ("Curso de inglês", "expense", "Educação", "350.00", 18, "pending", "Nubank"),
    ]
    transactions = []
    for months_back in range(3):
        period = start
        for _ in range(months_back):
            period = (period - timedelta(days=1)).replace(day=1)
        for description, kind, category, amount, day, status, account in rows:
            transactions.append(
                Transaction(
                    owner=user,
                    description=description,
                    kind=kind,
                    category=category,
                    amount=Decimal(amount)
                    * (Decimal("1") if months_back == 0 else Decimal("0.94")),
                    date=period.replace(day=day),
                    status=status if months_back == 0 else "paid",
                    account=account,
                )
            )
    Transaction.objects.bulk_create(transactions)
    plans = [
        (
            "reserves",
            "Reserva de emergência",
            "Sua tranquilidade em primeiro lugar",
            "18500",
            "30000",
            "blue",
        ),
        ("reserves", "Eurotrip 2027", "Experiências que ficam", "8200", "20000", "purple"),
        ("reserves", "Meu próximo carro", "Um passo de cada vez", "12000", "45000", "orange"),
        ("credit_cards", "Nubank", "Mastercard · final 4829", "1280.10", "8000", "purple"),
        ("credit_cards", "Itaú Personnalité", "Visa · final 9012", "650.00", "15000", "blue"),
        ("vehicles", "Volkswagen Nivus", "Highline · 2023 · Flex", "108000", "0", "blue"),
        ("trips", "Lisboa & Porto", "Portugal · 12 dias", "8200", "20000", "purple"),
        ("trips", "Um fim de semana na serra", "Campos do Jordão · 3 dias", "650", "2500", "green"),
        ("fixed_expenses", "Aluguel", "Moradia", "2400", "0", "blue"),
        ("fixed_expenses", "Internet residencial", "Moradia", "119.90", "0", "purple"),
        ("fixed_expenses", "Plano de saúde", "Saúde", "580", "0", "green"),
        ("fixed_expenses", "Spotify Premium", "Lazer", "21.90", "0", "green"),
        ("fixed_incomes", "Salário", "Trabalho · Conta principal", "12500", "0", "blue"),
        ("fixed_incomes", "Contrato de design", "Freelance · Nubank", "2850", "0", "purple"),
    ]
    PortfolioItem.objects.bulk_create(
        [
            PortfolioItem(
                owner=user,
                kind=k,
                name=n,
                subtitle=s,
                amount=a,
                target=t,
                color=c,
                day=5 if k == "fixed_incomes" else 15,
                due_date=date(start.year + 1, 6, 15) if k in ["trips", "reserves"] else None,
            )
            for k, n, s, a, t, c in plans
        ]
    )
    return user
