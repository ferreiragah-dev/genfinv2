from datetime import date, timedelta
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
    OpenFinanceIdentity,
    PortfolioItem,
    Preferences,
    Transaction,
)
from .open_finance import sync_connection
from .pluggy import PluggyError


class AccountResetTests(TestCase):
    password = "test-reset-password"

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            "reset-owner", password=cls.password, first_name="Ana", email="ana@example.com"
        )
        cls.other = User.objects.create_user("other-owner", password="other-password")
        for user in (cls.user, cls.other):
            identity = OpenFinanceIdentity.objects.create(owner=user)
            connection = BankConnection.objects.create(
                owner=user, item_id=uuid4(), institution="Pluggy Bank"
            )
            account = BankAccount.objects.create(
                connection=connection,
                external_id=uuid4(),
                name="Conta teste",
                kind="BANK",
                currency="BRL",
                balance=100,
            )
            for imported in (True, False):
                Transaction.objects.create(
                    owner=user,
                    description="Importada" if imported else "Manual",
                    amount=100,
                    kind="income",
                    category="Outros",
                    date=date.today(),
                    pluggy_id=uuid4() if imported else None,
                    bank_account=account if imported else None,
                )
            for kind, _ in PortfolioItem.KINDS:
                PortfolioItem.objects.create(owner=user, kind=kind, name=kind, amount=100)
            Preferences.objects.create(
                owner=user, widgets={"balance": False}, notifications_read=True
            )
            if user == cls.user:
                cls.identity_id = identity.client_user_id
                cls.connection_id = connection.pk
                cls.item_id = connection.item_id
        cls.endpoint = reverse("account_reset")

    def setUp(self):
        self.client.force_login(self.user)

    def assert_financial_data_present(self, user):
        self.assertEqual(Transaction.objects.filter(owner=user).count(), 2)
        self.assertEqual(PortfolioItem.objects.filter(owner=user).count(), 6)
        self.assertEqual(BankConnection.objects.filter(owner=user).count(), 1)
        self.assertEqual(BankAccount.objects.filter(connection__owner=user).count(), 1)
        self.assertTrue(Preferences.objects.filter(owner=user).exists())

    def test_profile_has_confirmation_and_password_form(self):
        response = self.client.get(reverse("profile"))
        self.assertContains(response, "Resetar conta")
        self.assertContains(response, 'type="password"')
        self.assertContains(response, 'autocomplete="current-password"')
        self.assertContains(response, f'action="{self.endpoint}"')
        self.assertContains(response, "Confirmar reset e apagar dados")
        self.assertContains(response, "não pode ser desfeita")

    @patch("finance.account_reset.PluggyClient")
    def test_wrong_missing_or_other_users_password_changes_nothing(self, remote):
        for password in ("", "wrong-password", "other-password"):
            response = self.client.post(self.endpoint, {"password": password})
            self.assertEqual(response.status_code, 400)
            self.assertContains(response, "data-show-reset", status_code=400)
            if password:
                self.assertContains(response, "Senha incorreta", status_code=400)
                self.assertNotContains(response, f'value="{password}"', status_code=400)
            self.assert_financial_data_present(self.user)
        remote.assert_not_called()

    @patch("finance.account_reset.PluggyClient")
    def test_success_clears_all_owned_financial_data_and_keeps_login(self, remote):
        password_hash = self.user.password
        response = self.client.post(
            self.endpoint, {"password": self.password, "owner": self.other.pk}
        )
        self.assertRedirects(response, reverse("profile"))
        for model in (Transaction, PortfolioItem, BankConnection, Preferences):
            self.assertFalse(model.objects.filter(owner=self.user).exists())
        self.assertFalse(BankAccount.objects.filter(connection__owner=self.user).exists())
        self.assert_financial_data_present(self.other)
        remote.return_value.delete_item.assert_called_once_with(self.item_id)
        self.user.refresh_from_db()
        self.assertEqual(self.user.password, password_hash)
        self.assertEqual(self.user.first_name, "Ana")
        self.assertEqual(self.user.email, "ana@example.com")
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)
        self.assertNotEqual(
            OpenFinanceIdentity.objects.get(owner=self.user).client_user_id, self.identity_id
        )
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_login_post_and_csrf_are_required(self):
        self.assertEqual(self.client.get(self.endpoint).status_code, 405)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(
            csrf_client.post(self.endpoint, {"password": self.password}).status_code, 403
        )
        self.client.logout()
        self.assertEqual(
            self.client.post(self.endpoint, {"password": self.password}).status_code, 302
        )
        self.assert_financial_data_present(self.user)

    @patch("finance.account_reset.PluggyClient")
    def test_unusable_password_account_cannot_reset(self, remote):
        self.user.set_unusable_password()
        self.user.save()
        self.client.force_login(self.user)
        self.assertEqual(
            self.client.post(self.endpoint, {"password": self.password}).status_code, 400
        )
        remote.assert_not_called()
        self.assert_financial_data_present(self.user)

    @patch("finance.account_reset.PluggyClient")
    def test_remote_failure_preserves_local_data_and_hides_provider_error(self, remote):
        remote.return_value.delete_item.side_effect = PluggyError("secret provider response")
        response = self.client.post(self.endpoint, {"password": self.password})
        self.assertEqual(response.status_code, 502)
        self.assertContains(response, "Seus dados locais foram preservados", status_code=502)
        self.assertNotContains(response, "secret provider response", status_code=502)
        self.assert_financial_data_present(self.user)
        self.assertEqual(
            OpenFinanceIdentity.objects.get(owner=self.user).client_user_id, self.identity_id
        )

    @patch("finance.account_reset.PluggyClient")
    def test_partial_remote_failure_can_be_retried_without_partial_local_reset(self, remote):
        second = BankConnection.objects.create(
            owner=self.user, item_id=uuid4(), institution="Outro banco"
        )
        remote.return_value.delete_item.side_effect = [None, PluggyError()]
        self.assertEqual(
            self.client.post(self.endpoint, {"password": self.password}).status_code, 502
        )
        self.assertEqual(Transaction.objects.filter(owner=self.user).count(), 2)
        self.assertEqual(BankConnection.objects.filter(owner=self.user).count(), 2)
        remote.return_value.delete_item.side_effect = None
        self.assertEqual(
            self.client.post(self.endpoint, {"password": self.password}).status_code, 302
        )
        self.assertFalse(BankConnection.objects.filter(pk=second.pk).exists())

    @patch("finance.account_reset.PluggyClient")
    def test_without_active_connections_does_not_require_pluggy_credentials(self, remote):
        BankConnection.objects.filter(owner=self.user).update(active=False)
        self.assertEqual(
            self.client.post(self.endpoint, {"password": self.password}).status_code, 302
        )
        remote.assert_not_called()
        self.assertFalse(Transaction.objects.filter(owner=self.user).exists())

    @patch("finance.account_reset.PluggyClient")
    def test_repeated_reset_is_safe(self, remote):
        for _ in range(2):
            self.assertEqual(
                self.client.post(self.endpoint, {"password": self.password}).status_code, 302
            )
        remote.return_value.delete_item.assert_called_once()
        self.assert_financial_data_present(self.other)

    @patch("finance.account_reset.PluggyClient")
    @patch("finance.account_reset.Preferences.objects.filter")
    def test_local_failure_rolls_back_financial_deletions(self, preferences, remote):
        preferences.return_value.delete.side_effect = RuntimeError("storage failure")
        with self.assertRaises(RuntimeError):
            reset_account(self.user.pk, self.password)
        self.assertEqual(Transaction.objects.filter(owner=self.user).count(), 2)
        self.assertEqual(PortfolioItem.objects.filter(owner=self.user).count(), 6)
        self.assertTrue(BankConnection.objects.filter(pk=self.connection_id).exists())
        self.assertTrue(BankAccount.objects.filter(connection_id=self.connection_id).exists())

    @patch("finance.account_reset.PluggyClient")
    @patch("finance.open_finance_views.PluggyClient")
    def test_inflight_widget_callback_cannot_restore_pre_reset_connection(
        self, widget_client, reset_client
    ):
        item = {
            "id": str(self.item_id),
            "clientUserId": str(self.identity_id),
            "connector": {"isSandbox": True},
        }

        def fetch_item(*args):
            reset_account(self.user.pk, self.password)
            return item

        widget_client.return_value.item.side_effect = fetch_item
        response = self.client.post(
            reverse("pluggy_register"),
            {"itemId": str(self.item_id)},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(BankConnection.objects.filter(owner=self.user).exists())

    @patch("finance.account_reset.PluggyClient")
    def test_running_import_cannot_restore_data_after_reset(self, reset_client):
        lease = timezone.now() + timedelta(minutes=20)
        BankConnection.objects.filter(pk=self.connection_id).update(locked_until=lease)
        item = {
            "id": str(self.item_id),
            "clientUserId": str(self.identity_id),
            "connector": {"isSandbox": True},
            "status": "UPDATED",
            "executionStatus": "SUCCESS",
            "updatedAt": "same",
        }
        account = BankAccount.objects.get(connection_id=self.connection_id)
        remote = MagicMock()
        remote.accounts.return_value = [
            {
                "id": str(account.external_id),
                "itemId": str(self.item_id),
                "type": "BANK",
                "currencyCode": "BRL",
                "name": "Conta teste",
                "balance": "100",
            }
        ]
        remote.transactions.return_value = []
        calls = 0

        def fetch_item(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                reset_account(self.user.pk, self.password)
            return item

        remote.item.side_effect = fetch_item
        sync_connection(self.connection_id, lease, remote)
        self.assertFalse(BankConnection.objects.filter(owner=self.user).exists())
        self.assertFalse(Transaction.objects.filter(owner=self.user).exists())
        sync_connection(self.connection_id, lease, remote)  # A stale queued task is also harmless.
