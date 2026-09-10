"""Vehicle costs must track the existing ledger without double counting."""

from datetime import date
from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase
from .models import PortfolioItem, Transaction
from .vehicle_services import vehicle_month_data
from .services import dashboard_data


class VehicleCostsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="driver")
        cls.other = User.objects.create_user(username="other_driver")
        cls.car = PortfolioItem.objects.create(owner=cls.user, kind="vehicles", name="Nivus")
        cls.second = PortfolioItem.objects.create(owner=cls.user, kind="vehicles", name="Civic")
        cls.foreign = PortfolioItem.objects.create(owner=cls.other, kind="vehicles", name="Privado")
        cls.reserve = PortfolioItem.objects.create(owner=cls.user, kind="reserves", name="Reserva")

    def setUp(self):
        self.client.force_login(self.user)

    def payload(self, **changes):
        return {
            "description": "Abastecimento",
            "amount": "100.05",
            "kind": "expense",
            "category": "Combustível",
            "date": "2026-09-09",
            "status": "paid",
            "account": "Conta principal",
            "vehicle": self.car.pk,
            **changes,
        }

    def costs(self, month="2026-09"):
        return vehicle_month_data(
            self.user, month, PortfolioItem.objects.filter(owner=self.user, kind="vehicles")
        )

    def test_monthly_breakdown_and_ledger_total(self):
        for category, amount in [
            ("IPVA", "1000"),
            ("Seguro veicular", "250"),
            ("Combustível", "100.05"),
            ("Combustível", "50.10"),
        ]:
            self.assertEqual(
                self.client.post(
                    "/api/transactions/", self.payload(category=category, amount=amount)
                ).status_code,
                200,
            )
        self.client.post("/api/transactions/", self.payload(status="pending", amount="90"))
        self.client.post("/api/transactions/", self.payload(date="2026-08-31", amount="60"))
        self.client.post("/api/transactions/", self.payload(vehicle=self.second.pk, amount="300"))
        Transaction.objects.create(
            owner=self.other,
            vehicle=self.foreign,
            kind="expense",
            category="Combustível",
            amount="999",
            date=date(2026, 9, 9),
            description="Privado",
        )
        context = self.costs()
        self.assertEqual(context["vehicle_month_total"], Decimal("1700.15"))
        car = next(item for item in context["items"] if item.pk == self.car.pk)
        self.assertEqual(car.monthly_total, Decimal("1400.15"))
        self.assertEqual(
            [cost["amount"] for cost in car.monthly_costs],
            [Decimal("1000"), Decimal("250"), Decimal("150.15")],
        )
        self.assertEqual(context["history"].count(), 6)
        self.assertEqual(dashboard_data(self.user, "2026-09")["expense"], Decimal("1700.15"))
        response = self.client.get("/vehicles/?month=2026-09")
        self.assertContains(response, "1.400,15")
        self.assertContains(response, "Registrar abastecimento")
        self.assertNotContains(response, "Privado")
        self.assertEqual(self.costs("2026-07")["vehicle_month_total"], 0)

    def test_vehicle_required_owned_and_correct_type(self):
        for vehicle in ["", self.foreign.pk, self.reserve.pk, 999999]:
            with self.subTest(vehicle=vehicle):
                response = self.client.post("/api/transactions/", self.payload(vehicle=vehicle))
                self.assertEqual(response.status_code, 400)
                self.assertIn("vehicle", response.json()["errors"])
        for category in ["IPVA", "Seguro veicular", "Combustível"]:
            self.assertEqual(
                self.client.post(
                    "/api/transactions/", self.payload(category=category, kind="income")
                ).status_code,
                400,
            )
        self.assertEqual(Transaction.objects.count(), 0)

    def test_edit_reassign_status_and_delete_recalculate(self):
        pk = self.client.post("/api/transactions/", self.payload(status="pending")).json()["id"]
        self.assertEqual(self.costs()["vehicle_month_total"], 0)
        self.assertEqual(self.client.get(f"/api/transactions/{pk}/").json()["vehicle"], self.car.pk)
        self.client.post(
            f"/api/transactions/{pk}/save/", self.payload(vehicle=self.second.pk, amount="200")
        )
        self.assertEqual(Transaction.objects.count(), 1)
        context = self.costs()
        self.assertEqual(context["items"][0].monthly_total, 0)
        self.assertEqual(context["items"][1].monthly_total, Decimal("200"))
        self.client.post(f"/api/transactions/{pk}/delete/")
        self.assertEqual(self.costs()["vehicle_month_total"], 0)

    def test_changing_category_removes_vehicle_association(self):
        pk = self.client.post("/api/transactions/", self.payload()).json()["id"]
        response = self.client.post(
            f"/api/transactions/{pk}/save/", self.payload(category="Outros", vehicle="")
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(Transaction.objects.get(pk=pk).vehicle_id)
        self.assertEqual(self.costs()["vehicle_month_total"], 0)
        self.assertEqual(dashboard_data(self.user, "2026-09")["expense"], Decimal("100.05"))

    def test_deleting_vehicle_preserves_financial_history(self):
        pk = self.client.post("/api/transactions/", self.payload()).json()["id"]
        self.assertEqual(self.client.post(f"/api/portfolio/{self.car.pk}/delete/").status_code, 200)
        self.assertIsNone(Transaction.objects.get(pk=pk).vehicle_id)
        self.assertEqual(Transaction.objects.get(pk=pk).amount, Decimal("100.05"))

    def test_vehicle_type_is_immutable_and_export_names_vehicle(self):
        self.client.post("/api/transactions/", self.payload())
        response = self.client.post(
            f"/api/portfolio/{self.car.pk}/save/",
            {
                "kind": "reserves",
                "name": "Nivus",
                "amount": "0",
                "target": "0",
                "day": 5,
                "color": "blue",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.car.refresh_from_db()
        self.assertEqual(self.car.kind, "vehicles")
        csv = self.client.get("/export/transactions/").content.decode("utf-8-sig")
        self.assertIn("Veículo", csv)
        self.assertIn("Nivus", csv)
