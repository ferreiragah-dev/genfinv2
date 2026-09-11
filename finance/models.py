"""User-owned financial records. Monetary values never use floats."""

from decimal import Decimal
from uuid import uuid4
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
from .constants import VEHICLE_CATEGORIES


class OwnedModel(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class Transaction(OwnedModel):
    TYPES = [("income", "Receita"), ("expense", "Despesa")]
    STATUS = [("paid", "Concluído"), ("pending", "Pendente")]
    description = models.CharField(max_length=120)
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    kind = models.CharField(max_length=7, choices=TYPES)
    category = models.CharField(max_length=40)
    date = models.DateField()
    status = models.CharField(max_length=7, choices=STATUS, default="paid")
    account = models.CharField(max_length=60, default="Conta principal")
    pluggy_id = models.UUIDField(null=True, blank=True, unique=True, editable=False)
    pluggy_date = models.DateField(null=True, blank=True, editable=False)
    bank_account = models.ForeignKey(
        "BankAccount", null=True, blank=True, on_delete=models.CASCADE, editable=False
    )
    vehicle = models.ForeignKey(
        "PortfolioItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vehicle_expenses",
        limit_choices_to={"kind": "vehicles"},
    )

    class Meta:
        ordering = ["-date", "-id"]
        indexes = [models.Index(fields=["owner", "date"])]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="transaction_positive_amount"),
            models.CheckConstraint(
                condition=Q(vehicle__isnull=True)
                | (Q(kind="expense") & Q(category__in=VEHICLE_CATEGORIES)),
                name="vehicle_link_requires_vehicle_expense",
            ),
        ]

    def __str__(self):
        return self.description


class PortfolioItem(OwnedModel):
    """Shared planning entity; metadata stays explicit instead of opaque JSON."""

    KINDS = [
        ("credit_cards", "Cartão"),
        ("vehicles", "Veículo"),
        ("trips", "Viagem"),
        ("fixed_expenses", "Despesa fixa"),
        ("fixed_incomes", "Receita fixa"),
        ("reserves", "Reserva"),
    ]
    kind = models.CharField(max_length=20, choices=KINDS)
    name = models.CharField(max_length=100)
    subtitle = models.CharField(max_length=120, blank=True)
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    target = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    due_date = models.DateField(null=True, blank=True)
    day = models.PositiveSmallIntegerField(
        default=5, validators=[MinValueValidator(1), MaxValueValidator(31)]
    )
    color = models.CharField(
        max_length=12,
        choices=[("blue", "Azul"), ("purple", "Roxo"), ("green", "Verde"), ("orange", "Laranja")],
        default="blue",
    )

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["owner", "kind"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gte=0) & Q(target__gte=0), name="portfolio_nonnegative_amounts"
            )
        ]

    @property
    def progress(self):
        return min(100, round(self.amount / self.target * 100)) if self.target else 0


class Preferences(OwnedModel):
    """One preferences row per account."""

    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    widgets = models.JSONField(default=dict)
    notifications_read = models.BooleanField(default=False)


class OpenFinanceIdentity(models.Model):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    # Opaque identifier: no email, CPF or predictable user id is sent to Pluggy.
    client_user_id = models.UUIDField(default=uuid4, unique=True, editable=False)


class BankConnection(OwnedModel):
    item_id = models.UUIDField(unique=True)
    institution = models.CharField(max_length=120)
    sandbox = models.BooleanField(default=True)
    active = models.BooleanField(default=True)
    status = models.CharField(max_length=40, default="QUEUED")
    last_synced_at = models.DateTimeField(null=True, blank=True)
    next_sync_at = models.DateTimeField(default=timezone.now, db_index=True)
    locked_until = models.DateTimeField(null=True, blank=True)
    sync_message = models.CharField(max_length=250, blank=True)

    class Meta:
        ordering = ["-created_at"]


class BankAccount(models.Model):
    connection = models.ForeignKey(
        BankConnection, on_delete=models.CASCADE, related_name="accounts"
    )
    external_id = models.UUIDField(unique=True)
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=20)
    currency = models.CharField(max_length=3)
    balance = models.DecimalField(max_digits=18, decimal_places=2, null=True)
