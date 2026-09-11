from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .account_reset import reset_account
from .models import (
    BankAccount,
    BankConnection,
    CategoryRule,
    OpenFinanceIdentity,
    PortfolioItem,
    ReviewPair,
    Transaction,
)
from .open_finance import sync_connection
from .review_services import suggestions
from .services import dashboard_data
from .vehicle_services import vehicle_month_data


class ReviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("review-owner", password="review-password")
        cls.other = User.objects.create_user("review-other", password="other-password")
        cls.identity = OpenFinanceIdentity.objects.create(owner=cls.user)
        cls.connection = BankConnection.objects.create(
            owner=cls.user, item_id=uuid4(), institution="Pluggy Bank"
        )
        cls.bank = BankAccount.objects.create(
            connection=cls.connection,
            external_id=uuid4(),
            name="Banco A",
            kind="BANK",
            currency="BRL",
            balance=100,
        )
        cls.bank_two = BankAccount.objects.create(
            connection=cls.connection,
            external_id=uuid4(),
            name="Banco B",
            kind="BANK",
            currency="BRL",
            balance=100,
        )
        cls.vehicle = PortfolioItem.objects.create(owner=cls.user, kind="vehicles", name="Carro")

    def setUp(self):
        self.client.force_login(self.user)

    def row(self, imported=False, **values):
        data = dict(
            owner=self.user,
            description="Pagamento",
            amount=Decimal("50.00"),
            kind="expense",
            category="Outros",
            date=date.today(),
            category_locked=not imported,
        )
        if imported:
            data.update(pluggy_id=uuid4(), bank_account=self.bank, pluggy_date=date.today())
        data.update(values)
        obj = Transaction.objects.create(**data)
        obj.refresh_from_db()
        return obj

    def post(self, **values):
        return self.client.post(reverse("review_action"), values)

    def category(self, row, **values):
        row.refresh_from_db()
        return self.post(
            action="category", transaction_id=row.pk, version=row.review_version, **values
        )

    def pair(self, first, second, kind="duplicate", action="confirm"):
        first.refresh_from_db()
        second.refresh_from_db()
        return self.post(
            action=action,
            first_id=first.pk,
            second_id=second.pk,
            kind=kind,
            first_version=first.review_version,
            second_version=second.review_version,
        )

    def remote(self, row):
        client = MagicMock()
        client.item.return_value = {
            "id": str(self.connection.item_id),
            "clientUserId": str(self.identity.client_user_id),
            "connector": {"isSandbox": True},
            "status": "UPDATED",
            "executionStatus": "SUCCESS",
            "updatedAt": "same",
        }
        client.accounts.return_value = [
            {
                "id": str(self.bank.external_id),
                "itemId": str(self.connection.item_id),
                "type": "BANK",
                "currencyCode": "BRL",
                "name": "Banco A",
                "balance": "100",
            }
        ]
        client.transactions.return_value = [
            {
                "id": str(row.pluggy_id),
                "accountId": str(self.bank.external_id),
                "amount": "-50",
                "currencyCode": "BRL",
                "type": "DEBIT",
                "status": "POSTED",
                "date": date.today().isoformat(),
                "description": row.description,
            }
        ]
        return client

    def sync(self, remote):
        lease = timezone.now() + timedelta(minutes=20)
        BankConnection.objects.filter(pk=self.connection.pk).update(locked_until=lease)
        sync_connection(self.connection.pk, lease, remote)

    def test_all_tabs_and_empty_states_render(self):
        for tab in ("categories", "matches", "decisions", "rules"):
            response = self.client.get(reverse("review"), {"tab": tab})
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Revisar movimentações")

    def test_category_change_preserves_bank_fields_and_becomes_personal(self):
        row = self.row(imported=True)
        response = self.category(row, category="Alimentação", amount="1", owner=self.other.pk)
        self.assertEqual(response.status_code, 302)
        row.refresh_from_db()
        self.assertEqual(row.category, "Alimentação")
        self.assertEqual(row.amount, Decimal("50.00"))
        self.assertTrue(row.category_locked)
        self.assertIsNotNone(row.reviewed_at)
        self.assertEqual(row.owner_id, self.user.pk)

    def test_category_and_rule_validation_are_atomic(self):
        row = self.row(imported=True)
        self.assertEqual(self.category(row, category="Unknown").status_code, 400)
        self.assertEqual(
            self.category(row, category="Lazer", create_rule="1", pattern="x").status_code, 400
        )
        row.refresh_from_db()
        self.assertEqual(row.category, "Outros")
        self.assertFalse(row.category_locked)
        self.assertFalse(CategoryRule.objects.exists())

    def test_vehicle_category_requires_owned_vehicle_and_expense(self):
        row = self.row(imported=True)
        other_vehicle = PortfolioItem.objects.create(
            owner=self.other, kind="vehicles", name="Privado"
        )
        self.assertEqual(self.category(row, category="Combustível").status_code, 400)
        self.assertEqual(
            self.category(row, category="Combustível", vehicle=other_vehicle.pk).status_code, 400
        )
        self.assertEqual(
            self.category(row, category="Combustível", vehicle=self.vehicle.pk).status_code, 302
        )
        self.assertEqual(
            vehicle_month_data(self.user, None, [self.vehicle])["vehicle_month_total"],
            Decimal("50.00"),
        )
        income = self.row(imported=True, kind="income")
        self.assertEqual(
            self.category(income, category="Combustível", vehicle=self.vehicle.pk).status_code, 400
        )

    def test_rules_normalize_accents_apply_only_to_same_owner_kind_and_unlocked_rows(self):
        bank = self.row(imported=True, description="CAFÉ DO BAIRRO")
        manual = self.row(description="CAFÉ DO BAIRRO", category="Lazer")
        other = self.row(imported=True, owner=self.other, description="cafe do bairro")
        income = self.row(imported=True, kind="income", description="cafe do bairro")
        self.assertEqual(
            self.post(
                action="rule", pattern="  Café  ", kind="expense", category="Alimentação"
            ).status_code,
            302,
        )
        bank.refresh_from_db()
        manual.refresh_from_db()
        other.refresh_from_db()
        income.refresh_from_db()
        self.assertEqual(bank.category, "Alimentação")
        self.assertFalse(bank.category_locked)
        self.assertIsNotNone(bank.reviewed_at)
        self.assertEqual(manual.category, "Lazer")
        self.assertEqual(other.category, "Outros")
        self.assertEqual(income.category, "Outros")
        self.assertEqual(CategoryRule.objects.get().match_text, "cafe")

    def test_newest_rule_wins_and_explicit_choice_survives_rule_edits(self):
        row = self.row(imported=True, description="Netflix mensal")
        self.post(action="rule", pattern="netflix", kind="expense", category="Lazer")
        self.post(action="rule", pattern="mensal", kind="expense", category="Compras")
        row.refresh_from_db()
        self.assertEqual(row.category, "Compras")
        self.category(row, category="Educação")
        rule = CategoryRule.objects.get(match_text="mensal")
        self.post(
            action="rule", rule_id=rule.pk, pattern="mensal", kind="expense", category="Saúde"
        )
        row.refresh_from_db()
        self.assertEqual(row.category, "Educação")

    def test_duplicate_suggestion_confirmation_and_undo_change_totals_without_deleting(self):
        manual = self.row(category="Alimentação")
        bank = self.row(imported=True)
        pairs = suggestions(self.user, [manual])
        self.assertEqual([(p["first"].pk, p["second"].pk) for p in pairs], [(manual.pk, bank.pk)])
        self.assertEqual(dashboard_data(self.user)["expense"], Decimal("100.00"))
        self.assertEqual(self.pair(manual, bank).status_code, 302)
        self.assertEqual(Transaction.objects.count(), 2)
        self.assertEqual(dashboard_data(self.user)["expense"], Decimal("50.00"))
        bank.refresh_from_db()
        self.assertEqual(bank.category, "Alimentação")
        self.assertEqual(
            self.post(action="undo", pair_id=ReviewPair.objects.get().pk).status_code, 302
        )
        self.assertEqual(dashboard_data(self.user)["expense"], Decimal("100.00"))

    def test_transfer_removes_both_legs_from_dashboard_and_transaction_totals(self):
        outgoing = self.row(imported=True)
        incoming = self.row(imported=True, bank_account=self.bank_two, kind="income")
        self.assertEqual(self.pair(outgoing, incoming, "transfer").status_code, 302)
        data = dashboard_data(self.user)
        self.assertEqual(data["income"], 0)
        self.assertEqual(data["expense"], 0)
        self.assertEqual(data["balance"], 0)
        self.assertEqual(self.client.get(reverse("transactions")).context["expense"], 0)
        self.assertContains(self.client.get(reverse("transactions")), "Transferência interna")
        reviewed = self.client.get(reverse("review"), {"state": "all"})
        self.assertEqual(len(reviewed.context["page_obj"]), 2)
        self.assertIn(
            "Transferência interna",
            self.client.get(reverse("export_transactions")).content.decode(),
        )

    def test_duplicate_and_transfer_can_coexist_on_same_bank_record(self):
        manual = self.row()
        outgoing = self.row(imported=True)
        incoming = self.row(imported=True, bank_account=self.bank_two, kind="income")
        self.pair(manual, outgoing)
        self.assertEqual(self.pair(outgoing, incoming, "transfer").status_code, 302)
        self.assertEqual(dashboard_data(self.user)["expense"], 0)
        duplicate = ReviewPair.objects.get(kind="duplicate")
        self.post(action="undo", pair_id=duplicate.pk)
        outgoing.refresh_from_db()
        self.assertEqual(outgoing.review_role, "transfer")
        self.assertEqual(dashboard_data(self.user)["expense"], Decimal("50.00"))

    def test_can_reconcile_manual_duplicate_after_transfer_confirmation(self):
        manual = self.row()
        outgoing = self.row(imported=True)
        incoming = self.row(imported=True, bank_account=self.bank_two, kind="income")
        self.pair(outgoing, incoming, "transfer")
        self.assertEqual(self.pair(manual, outgoing).status_code, 302)
        self.assertEqual(dashboard_data(self.user)["expense"], 0)

    def test_discard_and_restore_suggestions_do_not_change_totals(self):
        manual = self.row()
        bank = self.row(imported=True)
        self.assertEqual(self.pair(manual, bank, action="dismiss").status_code, 302)
        self.assertFalse(suggestions(self.user, [manual]))
        self.assertEqual(dashboard_data(self.user)["expense"], Decimal("100.00"))
        self.post(action="restore_suggestions")
        self.assertEqual(len(suggestions(self.user, [manual])), 1)

    def test_rejects_false_pairs_same_bank_pending_transfer_and_repeated_confirm(self):
        manual = self.row()
        bank = self.row(imported=True, amount=Decimal("60.00"))
        self.assertEqual(self.pair(manual, bank).status_code, 400)
        bank.amount = manual.amount
        bank.save()
        self.assertEqual(self.pair(manual, bank).status_code, 302)
        self.assertEqual(self.pair(manual, bank).status_code, 400)
        outgoing = self.row(imported=True)
        incoming = self.row(imported=True, kind="income")
        self.assertEqual(self.pair(outgoing, incoming, "transfer").status_code, 400)
        incoming.bank_account = self.bank_two
        incoming.status = "pending"
        incoming.save()
        self.assertEqual(self.pair(outgoing, incoming, "transfer").status_code, 400)

    def test_changed_source_or_deleted_source_reopens_partner(self):
        manual = self.row()
        bank = self.row(imported=True)
        self.pair(manual, bank)
        bank.amount = Decimal("55.00")
        bank.save(update_fields=["amount"])
        manual.refresh_from_db()
        self.assertEqual(manual.review_role, "normal")
        self.assertIsNone(manual.reviewed_at)
        self.assertFalse(ReviewPair.objects.exists())
        bank.amount = manual.amount
        bank.save()
        self.pair(manual, bank)
        bank.delete()
        manual.refresh_from_db()
        self.assertEqual(manual.review_role, "normal")

    def test_stale_review_form_is_rejected(self):
        row = self.row(imported=True)
        version = row.review_version
        row.amount = Decimal("70.00")
        row.save()
        self.assertEqual(
            self.post(
                action="category", transaction_id=row.pk, version=version, category="Lazer"
            ).status_code,
            400,
        )

    def test_sync_preserves_override_and_vehicle(self):
        row = self.row(imported=True, account="Pluggy Bank · Banco A")
        self.category(row, category="Combustível", vehicle=self.vehicle.pk)
        self.sync(self.remote(row))
        row.refresh_from_db()
        self.assertEqual(row.category, "Combustível")
        self.assertEqual(row.vehicle_id, self.vehicle.pk)
        self.assertTrue(row.category_locked)

    def test_sync_uses_rules_on_new_rows_and_clears_invalid_vehicle_on_type_change(self):
        row = self.row(
            imported=True,
            description="Posto teste",
            category="Combustível",
            vehicle=self.vehicle,
            category_locked=True,
        )
        remote = self.remote(row)
        remote.transactions.return_value[0].update(type="CREDIT", amount="50")
        self.sync(remote)
        row.refresh_from_db()
        self.assertIsNone(row.vehicle_id)
        self.assertEqual(row.category, "Outros")
        self.post(action="rule", pattern="netflix", kind="expense", category="Lazer")
        new_id = uuid4()
        remote.transactions.return_value = [
            {
                **remote.transactions.return_value[0],
                "id": str(new_id),
                "type": "DEBIT",
                "amount": "-50",
                "description": "NETFLIX mensal",
            }
        ]
        self.sync(remote)
        self.assertEqual(Transaction.objects.get(pluggy_id=new_id).category, "Lazer")

    def test_identical_sync_preserves_confirmed_pair(self):
        manual = self.row()
        bank = self.row(imported=True, account="Pluggy Bank · Banco A")
        self.pair(manual, bank)
        self.sync(self.remote(bank))
        self.assertEqual(ReviewPair.objects.count(), 1)
        self.assertEqual(dashboard_data(self.user)["expense"], Decimal("50.00"))

    def test_vehicle_totals_and_notifications_exclude_duplicate(self):
        manual = self.row(category="Combustível", vehicle=self.vehicle, status="pending")
        bank = self.row(imported=True, category="Combustível", vehicle=self.vehicle)
        self.pair(manual, bank)
        self.assertEqual(
            vehicle_month_data(self.user, None, [self.vehicle])["vehicle_month_total"],
            Decimal("50.00"),
        )
        self.assertEqual(self.client.get(reverse("profile")).context["pending_count"], 0)

    def test_user_isolation_login_csrf_and_post_only(self):
        row = self.row(owner=self.other)
        self.assertEqual(self.category(row, category="Lazer").status_code, 404)
        rule = CategoryRule.objects.create(
            owner=self.other, match_text="test", kind="expense", category="Lazer"
        )
        self.assertEqual(self.post(action="delete_rule", rule_id=rule.pk).status_code, 404)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(
            csrf_client.post(
                reverse("review_action"), {"action": "restore_suggestions"}
            ).status_code,
            403,
        )
        self.assertEqual(self.client.get(reverse("review_action")).status_code, 405)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("review")).status_code, 302)

    def test_rules_removed_by_account_reset_and_other_users_rules_survive(self):
        self.post(action="rule", pattern="test", kind="expense", category="Lazer")
        CategoryRule.objects.create(
            owner=self.other, match_text="other", kind="expense", category="Lazer"
        )
        manual = self.row()
        bank = self.row(imported=True)
        self.pair(manual, bank)
        with patch("finance.account_reset.PluggyClient"):
            reset_account(self.user.pk, "review-password")
        self.assertFalse(CategoryRule.objects.filter(owner=self.user).exists())
        self.assertFalse(ReviewPair.objects.exists())
        self.assertTrue(CategoryRule.objects.filter(owner=self.other).exists())

    def test_render_populated_tabs_filters_and_pagination(self):
        manual = self.row(description="Teste visível")
        bank = self.row(imported=True, description="Teste visível")
        self.assertContains(
            self.client.get(reverse("review"), {"tab": "matches"}), "Confirmar duplicata"
        )
        response = self.client.get(reverse("review"), {"q": "Teste", "state": "all"})
        self.assertContains(response, "Salvar e marcar como revisada")
        self.assertContains(response, 'name="version"')
        self.post(action="rule", pattern="Teste", kind="expense", category="Lazer")
        self.assertContains(self.client.get(reverse("review"), {"tab": "rules"}), "Editar regra")
        self.pair(manual, bank)
        self.assertContains(
            self.client.get(reverse("review"), {"tab": "decisions"}), "Desfazer conciliação"
        )
        for _ in range(16):
            self.row(imported=True)
        self.assertContains(self.client.get(reverse("review")), "Próxima")
