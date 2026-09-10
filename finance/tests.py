"""Regression checks for isolation, money calculations and authenticated flows."""

from datetime import date
from decimal import Decimal
from django.contrib.auth.models import User
from django.test import Client, TestCase
from .models import Transaction, PortfolioItem, Preferences
from .services import dashboard_data


class FinancialFlowsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="owner", password="test-strong-password", first_name="Ana"
        )
        cls.other = User.objects.create_user(username="other", password="another-strong-password")
        cls.income = Transaction.objects.create(
            owner=cls.user,
            description="Salário",
            amount="10000.10",
            kind="income",
            category="Salário",
            date=date(2026, 9, 1),
        )
        cls.expense = Transaction.objects.create(
            owner=cls.user,
            description="Aluguel",
            amount="2500.05",
            kind="expense",
            category="Moradia",
            date=date(2026, 9, 2),
        )
        cls.pending = Transaction.objects.create(
            owner=cls.user,
            description="Internet",
            amount="120",
            kind="expense",
            category="Moradia",
            date=date(2026, 9, 15),
            status="pending",
        )
        cls.private = Transaction.objects.create(
            owner=cls.other,
            description="Privado",
            amount="99999",
            kind="income",
            category="Salário",
            date=date(2026, 9, 1),
        )
        cls.reserve = PortfolioItem.objects.create(
            owner=cls.user, kind="reserves", name="Reserva", amount="2000", target="10000"
        )
        cls.vehicle = PortfolioItem.objects.create(
            owner=cls.user, kind="vehicles", name="Carro", amount="50000"
        )
        cls.card = PortfolioItem.objects.create(
            owner=cls.user, kind="credit_cards", name="Cartão", amount="1000", target="5000"
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_financial_totals_use_decimal_and_exclude_pending_and_other_users(self):
        context = dashboard_data(self.user, "2026-09")
        self.assertEqual(context["income"], Decimal("10000.10"))
        self.assertEqual(context["expense"], Decimal("2500.05"))
        self.assertEqual(context["balance"], Decimal("7500.05"))
        self.assertEqual(context["wealth"], Decimal("58500.05"))
        self.assertEqual(context["pending_count"], 1)
        self.assertEqual(context["chart_data"]["income"][-1], 10000.10)

    def test_all_requested_routes_render(self):
        for route in [
            "/",
            "/transactions/",
            "/credit-cards/",
            "/vehicles/",
            "/trips/",
            "/fixed-expenses/",
            "/fixed-incomes/",
            "/reserves/",
            "/profile/",
            "/design-system/",
            "/landing/",
        ]:
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'lang="pt-BR"')
                self.assertNotContains(response, "Privado")

    def test_unauthenticated_private_routes_redirect(self):
        client = Client()
        self.assertEqual(client.get("/").status_code, 302)
        self.assertEqual(client.get("/login/").status_code, 200)
        self.assertEqual(client.get("/register/").status_code, 200)

    def test_transaction_crud_and_ownership(self):
        data = {
            "description": "Mercado",
            "amount": "140.52",
            "kind": "expense",
            "category": "Alimentação",
            "date": "2026-09-09",
            "status": "paid",
            "account": "Conta pessoal",
        }
        response = self.client.post("/api/transactions/", data)
        self.assertEqual(response.status_code, 200)
        record_id = response.json()["id"]
        self.assertEqual(Transaction.objects.get(pk=record_id).owner, self.user)
        data["amount"] = "159.90"
        self.assertEqual(
            self.client.post(f"/api/transactions/{record_id}/save/", data).status_code, 200
        )
        self.assertEqual(
            self.client.get(f"/api/transactions/{record_id}/").json()["amount"], "159.90"
        )
        for suffix in ["", "save/", "delete/"]:
            response = (
                self.client.get(f"/api/transactions/{self.private.pk}/")
                if not suffix
                else self.client.post(f"/api/transactions/{self.private.pk}/{suffix}", data)
            )
            self.assertEqual(response.status_code, 404)
        self.assertEqual(
            self.client.post(f"/api/transactions/{record_id}/delete/").status_code, 200
        )
        self.assertFalse(Transaction.objects.filter(pk=record_id).exists())

    def test_invalid_transaction_rejected(self):
        for amount in ["0", "-10", "invalid", "9999999999999999", "1.001"]:
            response = self.client.post(
                "/api/transactions/",
                {
                    "description": "Invalid",
                    "amount": amount,
                    "kind": "expense",
                    "category": "Outros",
                    "date": "2026-09-09",
                    "status": "paid",
                    "account": "Conta",
                },
            )
            self.assertEqual(response.status_code, 400)
        self.assertFalse(Transaction.objects.filter(description="Invalid").exists())

    def test_portfolio_crud_validation_and_isolation(self):
        data = {
            "kind": "trips",
            "name": "Viagem",
            "subtitle": "Férias",
            "amount": "100",
            "target": "500",
            "day": "5",
            "color": "blue",
            "due_date": "2027-02-01",
        }
        response = self.client.post("/api/portfolio/", data)
        self.assertEqual(response.status_code, 200)
        pk = response.json()["id"]
        data["amount"] = "250"
        self.assertEqual(self.client.post(f"/api/portfolio/{pk}/save/", data).status_code, 200)
        self.assertEqual(PortfolioItem.objects.get(pk=pk).progress, 50)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(f"/api/portfolio/{pk}/").status_code, 404)
        self.assertEqual(self.client.post(f"/api/portfolio/{pk}/delete/").status_code, 404)
        self.client.force_login(self.user)
        data["amount"] = "-1"
        self.assertEqual(self.client.post("/api/portfolio/", data).status_code, 400)
        self.assertEqual(self.client.post(f"/api/portfolio/{pk}/delete/").status_code, 200)

    def test_csrf_enforced(self):
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.user)
        self.assertEqual(protected.post("/api/transactions/", {}).status_code, 403)
        self.assertEqual(protected.post("/demo/", {}).status_code, 403)

    def test_preferences_persist_and_filter_unknown_keys(self):
        response = self.client.post(
            "/api/preferences/",
            {"widgets": {"cashflow": False, "unknown": False}, "notifications_read": True},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        prefs = Preferences.objects.get(owner=self.user)
        self.assertEqual(prefs.widgets, {"cashflow": False})
        self.assertTrue(prefs.notifications_read)
        self.assertEqual(
            self.client.post("/api/preferences/", [], content_type="application/json").status_code,
            400,
        )

    def test_search_filters_and_csv_formula_safety(self):
        Transaction.objects.create(
            owner=self.user,
            description="=SUM(1+1)",
            amount="1",
            kind="income",
            category="Outros",
            date=date(2026, 9, 1),
        )
        response = self.client.get("/export/transactions/?kind=income&month=2026-09")
        content = response.content.decode("utf-8-sig")
        self.assertIn("'=SUM(1+1)", content)
        self.assertNotIn("Aluguel", content)
        self.assertNotIn("Privado", content)
        response = self.client.get("/transactions/?q=Aluguel")
        self.assertContains(response, "Aluguel")
        self.assertEqual(response.context["count"], 1)
        self.assertEqual(response.context["page_obj"][0].description, "Aluguel")

    def test_demo_accounts_are_isolated_and_passwordless(self):
        first, second = Client(), Client()
        self.assertEqual(first.post("/demo/").status_code, 302)
        self.assertEqual(second.post("/demo/").status_code, 302)
        self.assertNotEqual(first.session["_auth_user_id"], second.session["_auth_user_id"])
        demo_user = User.objects.get(pk=first.session["_auth_user_id"])
        self.assertFalse(demo_user.has_usable_password())
        self.assertTrue(first.session["is_demo"])
        self.assertEqual(first.get("/").status_code, 200)

    def test_registration_profile_login_and_logout(self):
        client = Client()
        response = client.post(
            "/register/",
            {
                "first_name": "Lucas",
                "email": "lucas@example.com",
                "username": "lucas",
                "password1": "A-long-example-pass-93",
                "password2": "A-long-example-pass-93",
            },
        )
        self.assertRedirects(response, "/")
        self.assertRedirects(
            client.post(
                "/profile/", {"first_name": "Lu", "last_name": "Silva", "email": "lu@example.com"}
            ),
            "/profile/",
        )
        self.assertEqual(User.objects.get(username="lucas").first_name, "Lu")
        self.assertRedirects(client.post("/logout/"), "/login/")
        self.assertRedirects(
            client.post("/login/", {"username": "lucas", "password": "A-long-example-pass-93"}), "/"
        )

    def test_month_selection_and_empty_state(self):
        response = self.client.get("/?month=2025-01")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nenhuma movimentação por aqui")
        self.assertEqual(dashboard_data(self.user, "2025-01")["income"], Decimal(0))
        self.assertEqual(self.client.get("/?month=invalid").status_code, 200)
