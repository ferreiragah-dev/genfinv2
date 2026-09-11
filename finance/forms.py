"""Validation shared by server-rendered forms and JSON endpoints."""

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Transaction, PortfolioItem
from .constants import VEHICLE_CATEGORIES

CATEGORIES = [
    "Salário",
    "Freelance",
    "Investimentos",
    "Moradia",
    "Alimentação",
    "Transporte",
    *VEHICLE_CATEGORIES,
    "Compras",
    "Saúde",
    "Lazer",
    "Educação",
    "Outros",
]


class TransactionForm(forms.ModelForm):
    category = forms.ChoiceField(choices=[(c, c) for c in CATEGORIES])

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vehicle"].queryset = (
            PortfolioItem.objects.filter(owner=user, kind="vehicles")
            if user is not None
            else PortfolioItem.objects.none()
        )

    def clean(self):
        data = super().clean()
        vehicle_category = data.get("category") in VEHICLE_CATEGORIES
        if vehicle_category:
            if data.get("kind") != "expense":
                self.add_error("kind", "IPVA, seguro veicular e combustível devem ser despesas.")
            if not data.get("vehicle") and "vehicle" not in self.errors:
                self.add_error("vehicle", "Selecione o veículo desta despesa.")
        else:
            # Changing the category must remove the former vehicle association.
            data["vehicle"] = None
        return data

    class Meta:
        model = Transaction
        fields = [
            "description",
            "amount",
            "kind",
            "category",
            "date",
            "status",
            "account",
            "vehicle",
        ]


class PortfolioForm(forms.ModelForm):
    def clean_kind(self):
        kind = self.cleaned_data["kind"]
        if self.instance.pk and self.instance.kind != kind:
            raise forms.ValidationError("O tipo de um registro existente não pode ser alterado.")
        return kind

    class Meta:
        model = PortfolioItem
        fields = ["kind", "name", "subtitle", "amount", "target", "due_date", "day", "color"]


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=150, required=True)

    class Meta:
        model = User
        fields = ["first_name", "email", "username", "password1", "password2"]


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]


class AccountResetForm(forms.Form):
    password = forms.CharField(
        label="Sua senha atual",
        strip=False,
        max_length=128,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
        error_messages={"required": "Digite sua senha para confirmar o reset."},
    )
