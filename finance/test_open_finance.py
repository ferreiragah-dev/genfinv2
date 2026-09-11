import io
import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client, SimpleTestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import BankAccount, BankConnection, OpenFinanceIdentity, Transaction
from .open_finance import sync_connection
from .pluggy import PluggyClient, PluggyError


@override_settings(
    PLUGGY_CLIENT_ID="test-client", PLUGGY_CLIENT_SECRET="private-secret", PLUGGY_SANDBOX=True
)
class OpenFinanceTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user("bank-user", password="test-password")
        self.other = User.objects.create_user("another-user", password="test-password")
        self.client.force_login(self.user)
        self.identity = OpenFinanceIdentity.objects.create(owner=self.user)
        self.connection = BankConnection.objects.create(
            owner=self.user, item_id=uuid4(), institution="Pluggy Bank"
        )
        self.account_id = uuid4()
        self.entry_id = uuid4()
        self.item = {
            "id": str(self.connection.item_id),
            "clientUserId": str(self.identity.client_user_id),
            "status": "UPDATED",
            "executionStatus": "SUCCESS",
            "updatedAt": "2026-09-10T12:00:00Z",
            "connector": {
                "id": 2,
                "name": "Pluggy Bank",
                "isSandbox": True,
                "isOpenFinance": False,
            },
        }
        self.account = {
            "id": str(self.account_id),
            "itemId": str(self.connection.item_id),
            "type": "BANK",
            "currencyCode": "BRL",
            "name": "Conta corrente",
            "balance": "1200.25",
        }
        self.entry = {
            "id": str(self.entry_id),
            "accountId": str(self.account_id),
            "currencyCode": "BRL",
            "amount": "-35.29",
            "type": "DEBIT",
            "status": "PENDING",
            "description": "Mercado",
            "date": timezone.now().date().isoformat() + "T01:00:00Z",
        }
        self.remote = MagicMock()
        self.remote.item.return_value = self.item
        self.remote.accounts.return_value = [self.account]
        self.remote.transactions.return_value = [self.entry]

    def run_sync(self):
        lease = timezone.now() + timedelta(minutes=20)
        BankConnection.objects.filter(pk=self.connection.pk).update(locked_until=lease)
        sync_connection(self.connection.pk, lease, self.remote)

    def register(self, item_id=None):
        return self.client.post(
            reverse("pluggy_register"),
            json.dumps({"itemId": str(item_id or self.connection.item_id)}),
            content_type="application/json",
        )

    def test_page_has_sandbox_and_no_secrets(self):
        response = self.client.get(reverse("open_finance"))
        self.assertContains(response, "Ambiente de testes")
        self.assertContains(response, "Conectar instituição")
        self.assertNotContains(response, "private-secret")
        self.assertNotContains(response, "test-client")

    @override_settings(PLUGGY_CLIENT_SECRET="")
    def test_unconfigured_page_explains_setup(self):
        response = self.client.get(reverse("open_finance"))
        self.assertContains(response, "Conexão em preparação")
        self.assertNotContains(response, "data-connect-bank")

    def test_login_csrf_and_post_required(self):
        self.client.logout()
        self.assertEqual(self.client.post(reverse("pluggy_token")).status_code, 302)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post(reverse("pluggy_token")).status_code, 403)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("pluggy_token")).status_code, 405)

    @patch("finance.open_finance_views.PluggyClient")
    def test_demo_cannot_request_token(self, remote):
        session = self.client.session
        session["is_demo"] = True
        session.save()
        self.assertEqual(self.client.post(reverse("pluggy_token")).status_code, 403)
        remote.assert_not_called()

    @patch("finance.open_finance_views.PluggyClient")
    def test_token_is_bound_to_server_identity_and_sandbox_only(self, remote):
        remote.return_value.connectors.return_value = [
            self.item["connector"],
            {"id": 9, "isSandbox": False, "isOpenFinance": True},
        ]
        remote.return_value.connect_token.return_value = "short-lived-token"
        response = self.client.post(reverse("pluggy_token"), {"clientUserId": "attacker"})
        self.assertEqual(response.json()["connectorIds"], [2])
        self.assertEqual(response.json()["accessToken"], "short-lived-token")
        self.assertIn("no-store", response["Cache-Control"])
        remote.return_value.connect_token.assert_called_once_with(
            self.identity.client_user_id, None
        )

    @patch("finance.open_finance_views.PluggyClient")
    def test_reconnect_token_scoped_to_owned_item(self, remote):
        remote.return_value.connectors.return_value = [self.item["connector"]]
        remote.return_value.item.return_value = self.item
        remote.return_value.connect_token.return_value = "token"
        response = self.client.post(reverse("pluggy_token"), {"connection_id": self.connection.pk})
        self.assertEqual(response.json()["updateItem"], str(self.connection.item_id))
        remote.return_value.connect_token.assert_called_once_with(
            self.identity.client_user_id, self.connection.item_id
        )

    @patch("finance.open_finance_views.PluggyClient")
    def test_register_rejects_forged_owner_and_real_bank(self, remote):
        remote.return_value.item.return_value = {**self.item, "clientUserId": "another-owner"}
        self.assertEqual(self.register().status_code, 403)
        remote.return_value.item.return_value = {
            **self.item,
            "connector": {"isSandbox": False, "isOpenFinance": True},
        }
        self.assertEqual(self.register().status_code, 403)

    @patch("finance.open_finance_views.PluggyClient")
    def test_register_is_repeatable(self, remote):
        new_id = uuid4()
        remote.return_value.item.return_value = {**self.item, "id": str(new_id)}
        self.assertEqual(self.register(new_id).status_code, 201)
        self.assertEqual(self.register(new_id).status_code, 200)
        self.assertEqual(BankConnection.objects.filter(item_id=new_id).count(), 1)

    def test_malformed_requests(self):
        for body in ("null", "[]", '{"itemId": "bad"}', "{"):
            self.assertEqual(
                self.client.post(
                    reverse("pluggy_register"), body, content_type="application/json"
                ).status_code,
                400,
            )
        self.assertEqual(
            self.client.post(reverse("pluggy_token"), {"connection_id": "bad"}).status_code, 400
        )

    def test_connection_and_status_isolation(self):
        self.client.force_login(self.other)
        for route in ("pluggy_sync", "pluggy_disconnect"):
            self.assertEqual(
                self.client.post(reverse(route, args=[self.connection.pk])).status_code, 404
            )
        self.assertEqual(
            self.client.post(
                reverse("pluggy_token"), {"connection_id": self.connection.pk}
            ).status_code,
            404,
        )
        self.assertEqual(self.client.get(reverse("pluggy_status")).json(), {"connections": []})

    def test_idempotent_import_updates_amount_status_and_local_date(self):
        self.run_sync()
        row = Transaction.objects.get(pluggy_id=self.entry_id)
        self.assertEqual(row.amount, Decimal("35.29"))
        self.assertEqual(row.kind, "expense")
        self.assertEqual(row.date, timezone.now().date() - timedelta(days=1))
        self.assertEqual(row.status, "pending")
        self.entry.update(amount="40.01", type="CREDIT", status="POSTED")
        self.run_sync()
        row.refresh_from_db()
        self.assertEqual(Transaction.objects.count(), 1)
        self.assertEqual(row.amount, Decimal("40.01"))
        self.assertEqual(row.kind, "income")
        self.assertEqual(row.status, "paid")
        self.assertEqual(BankAccount.objects.get().balance, Decimal("1200.25"))

    def test_removals_preserve_manual_and_old_history(self):
        self.run_sync()
        account = BankAccount.objects.get()
        fields = dict(
            owner=self.user,
            description="Anterior",
            amount=10,
            kind="income",
            category="Outros",
            date=timezone.now().date(),
        )
        manual = Transaction.objects.create(**fields)
        old = Transaction.objects.create(
            **fields,
            bank_account=account,
            pluggy_id=uuid4(),
            pluggy_date=timezone.now().date() - timedelta(days=100),
        )
        self.remote.transactions.return_value = []
        self.run_sync()
        self.assertFalse(Transaction.objects.filter(pluggy_id=self.entry_id).exists())
        self.assertTrue(Transaction.objects.filter(pk=manual.pk).exists())
        self.assertTrue(Transaction.objects.filter(pk=old.pk).exists())

    def test_changed_transaction_id_replaces_previous_record(self):
        self.run_sync()
        self.entry["id"] = str(uuid4())
        self.run_sync()
        self.assertEqual(Transaction.objects.count(), 1)
        self.assertFalse(Transaction.objects.filter(pluggy_id=self.entry_id).exists())

    def test_credit_and_foreign_accounts_do_not_enter_cashflow(self):
        self.remote.accounts.return_value = [
            {**self.account, "type": "CREDIT"},
            {**self.account, "id": str(uuid4()), "currencyCode": "USD"},
        ]
        self.run_sync()
        self.assertEqual(BankAccount.objects.count(), 2)
        self.assertFalse(Transaction.objects.exists())
        self.remote.transactions.assert_not_called()

    def test_corrupt_snapshot_rolls_back_all_changes(self):
        self.run_sync()
        self.remote.transactions.return_value = [
            self.entry,
            {**self.entry, "id": str(uuid4()), "amount": "NaN"},
        ]
        self.account["balance"] = "999"
        with self.assertRaises(PluggyError):
            self.run_sync()
        self.assertEqual(BankAccount.objects.get().balance, Decimal("1200.25"))
        self.assertEqual(Transaction.objects.count(), 1)

    def test_pagination_failure_preserves_previous_snapshot(self):
        self.run_sync()
        self.remote.transactions.side_effect = PluggyError()
        with self.assertRaises(PluggyError):
            self.run_sync()
        self.assertEqual(Transaction.objects.count(), 1)

    def test_partial_success_preserves_history(self):
        self.run_sync()
        self.item["executionStatus"] = "PARTIAL_SUCCESS"
        self.remote.transactions.return_value = []
        with self.assertRaises(PluggyError):
            self.run_sync()
        self.assertEqual(Transaction.objects.count(), 1)

    @patch("finance.management.commands.sync_pluggy.PluggyClient")
    def test_worker_skips_live_lease_and_recovers_expired_lease(self, remote):
        remote.return_value = self.remote
        BankConnection.objects.filter(pk=self.connection.pk).update(
            locked_until=timezone.now() + timedelta(minutes=10)
        )
        call_command("sync_pluggy", stdout=io.StringIO())
        self.remote.item.assert_not_called()
        BankConnection.objects.filter(pk=self.connection.pk).update(
            locked_until=timezone.now() - timedelta(seconds=1)
        )
        call_command("sync_pluggy", stdout=io.StringIO())
        self.assertEqual(Transaction.objects.count(), 1)

    def test_rejects_foreign_account_and_transaction(self):
        self.account["itemId"] = str(uuid4())
        with self.assertRaises(PluggyError):
            self.run_sync()
        self.account["itemId"] = str(self.connection.item_id)
        self.entry["accountId"] = str(uuid4())
        with self.assertRaises(PluggyError):
            self.run_sync()
        self.assertFalse(Transaction.objects.exists())

    def test_changing_provider_snapshot_is_not_committed(self):
        self.remote.item.side_effect = [self.item, {**self.item, "updatedAt": "changed"}]
        with self.assertRaises(PluggyError):
            self.run_sync()
        self.assertFalse(Transaction.objects.exists())

    def test_waiting_item_is_rescheduled(self):
        self.item["status"] = "UPDATING"
        self.run_sync()
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.status, "UPDATING")
        self.assertIsNone(self.connection.last_synced_at)
        self.assertIsNone(self.connection.locked_until)
        self.remote.accounts.assert_not_called()

    def test_imported_records_cannot_be_modified_by_crud(self):
        self.run_sync()
        pk = Transaction.objects.get().pk
        for suffix in ("save", "delete"):
            self.assertEqual(self.client.post(f"/api/transactions/{pk}/{suffix}/").status_code, 409)
        self.assertContains(self.client.get(reverse("transactions")), "Open Finance")

    @patch("finance.open_finance_views.PluggyClient")
    def test_disconnect_preserves_history_and_stops_sync(self, remote):
        self.run_sync()
        self.assertEqual(
            self.client.post(reverse("pluggy_disconnect", args=[self.connection.pk])).status_code,
            200,
        )
        remote.return_value.delete_item.assert_called_once_with(self.connection.item_id)
        self.connection.refresh_from_db()
        self.assertFalse(self.connection.active)
        self.assertEqual(Transaction.objects.count(), 1)
        self.assertEqual(
            self.client.post(reverse("pluggy_sync", args=[self.connection.pk])).status_code, 404
        )

    @patch("finance.open_finance_views.PluggyClient")
    def test_remote_delete_failure_keeps_connection_active(self, remote):
        remote.return_value.delete_item.side_effect = PluggyError()
        self.assertEqual(
            self.client.post(reverse("pluggy_disconnect", args=[self.connection.pk])).status_code,
            502,
        )
        self.connection.refresh_from_db()
        self.assertTrue(self.connection.active)

    def test_disconnect_during_fetch_prevents_commit(self):
        def disconnect(*args):
            BankConnection.objects.filter(pk=self.connection.pk).update(
                active=False, locked_until=None
            )
            return self.item

        self.remote.item.side_effect = disconnect
        self.run_sync()
        self.assertFalse(Transaction.objects.exists())

    @patch("finance.management.commands.sync_pluggy.PluggyClient")
    def test_worker_processes_due_queue_once(self, remote):
        remote.return_value = self.remote
        call_command("sync_pluggy", stdout=io.StringIO())
        self.assertEqual(Transaction.objects.count(), 1)
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.status, "UPDATED")
        self.remote.reset_mock()
        call_command("sync_pluggy", stdout=io.StringIO())
        self.remote.item.assert_not_called()

    @patch("finance.management.commands.sync_pluggy.PluggyClient")
    def test_worker_failure_releases_lease_without_leaking_error(self, remote):
        remote.return_value.item.side_effect = RuntimeError("private-secret")
        output = io.StringIO()
        call_command("sync_pluggy", stderr=output, stdout=output)
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.status, "ERROR")
        self.assertIsNone(self.connection.locked_until)
        self.assertNotIn("private-secret", self.connection.sync_message + output.getvalue())

    @override_settings(PLUGGY_SANDBOX=False)
    @patch("finance.open_finance_views.PluggyClient")
    def test_live_mode_only_lists_regulated_connectors(self, remote):
        remote.return_value.connectors.return_value = [
            self.item["connector"],
            {"id": 9, "isSandbox": False, "isOpenFinance": True},
            {"id": 10, "isSandbox": False, "isOpenFinance": False},
        ]
        remote.return_value.connect_token.return_value = "token"
        response = self.client.post(reverse("pluggy_token"))
        self.assertEqual(response.json()["connectorIds"], [9])
        self.assertFalse(response.json()["includeSandbox"])


@override_settings(PLUGGY_CLIENT_ID="client", PLUGGY_CLIENT_SECRET="secret")
class PluggyClientTests(SimpleTestCase):
    def test_authentication_and_headers_never_return_server_key(self):
        client = PluggyClient()
        auth = MagicMock()
        auth.__enter__.return_value.status = 200
        auth.__enter__.return_value.read.return_value = b'{"apiKey":"server-key"}'
        token = MagicMock()
        token.__enter__.return_value.status = 200
        token.__enter__.return_value.read.return_value = b'{"accessToken":"widget-token"}'
        client.opener.open = MagicMock(side_effect=[auth, token])
        self.assertEqual(client.connect_token(uuid4()), "widget-token")
        requests = client.opener.open.call_args_list
        self.assertEqual(requests[0].args[0].full_url, "https://api.pluggy.ai/auth")
        self.assertEqual(requests[1].args[0].get_header("X-api-key"), "server-key")
        self.assertEqual(requests[0].kwargs["timeout"], 8)

    def test_cursor_pagination_keeps_account_scope_and_filters(self):
        client = PluggyClient()
        client.request = MagicMock(
            side_effect=[
                {"results": [{"id": "first"}], "next": "?accountId=foreign&after=cursor%2Bvalue"},
                {"results": [{"id": "last"}], "next": None},
            ]
        )
        rows = client.transactions("owned-account", "2026-06-01", "2026-09-01")
        self.assertEqual(len(rows), 2)
        params = parse_qs(urlsplit(client.request.call_args.args[1]).query)
        self.assertEqual(params["accountId"], ["owned-account"])
        self.assertEqual(params["dateFrom"], ["2026-06-01"])
        self.assertEqual(params["after"], ["cursor+value"])

    def test_repeated_cursor_and_malformed_results_fail_closed(self):
        client = PluggyClient()
        for data in ({"results": [], "next": "?after=repeated"}, {"wrong": []}):
            client.request = MagicMock(return_value=data)
            with self.assertRaises(PluggyError):
                client.transactions(uuid4(), "2026-06-01", "2026-09-01")

    def test_provider_errors_are_sanitized(self):
        client = PluggyClient()
        for error in (
            URLError("secret body"),
            HTTPError("https://api.pluggy.ai", 429, "secret body", {}, None),
        ):
            client.opener.open = MagicMock(side_effect=error)
            with self.assertRaises(PluggyError) as context:
                client.request("GET", "/accounts")
            self.assertNotIn("secret", str(context.exception))

    def test_delete_missing_item_is_idempotent(self):
        client = PluggyClient()
        client.request = MagicMock(side_effect=PluggyError(status=404))
        client.delete_item(uuid4())
