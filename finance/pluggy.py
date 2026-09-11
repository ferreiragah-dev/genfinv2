"""Server-only Pluggy REST client. Never log provider bodies, credentials or tokens."""

import json
from decimal import Decimal
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings


class PluggyError(Exception):
    def __init__(
        self, message="A Pluggy está indisponível. Tente novamente em alguns minutos.", status=None
    ):
        super().__init__(message)
        self.status = status


def configured():
    return bool(settings.PLUGGY_CLIENT_ID and settings.PLUGGY_CLIENT_SECRET)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class PluggyClient:
    def __init__(self):
        if not configured():
            raise PluggyError("A conexão bancária ainda não foi configurada no servidor.")
        self.api_key = None
        self.expires_at = 0
        self.opener = build_opener(NoRedirect())

    def _send(self, method, path, payload=None, authenticated=True):
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if authenticated:
            headers["X-API-KEY"] = self.api_key
        request = Request(
            "https://api.pluggy.ai" + path,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers=headers,
            method=method,
        )
        try:
            with self.opener.open(request, timeout=8) as response:
                if response.status == 204:
                    return {}
                result = json.loads(response.read(), parse_float=Decimal)
                if not isinstance(result, dict):
                    raise ValueError("Expected object")
                return result
        except HTTPError as exc:
            exc.close()
            raise PluggyError(status=exc.code) from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise PluggyError() from None

    def request(self, method, path, payload=None):
        if not self.api_key or monotonic() >= self.expires_at:
            auth = self._send(
                "POST",
                "/auth",
                {
                    "clientId": settings.PLUGGY_CLIENT_ID,
                    "clientSecret": settings.PLUGGY_CLIENT_SECRET,
                },
                authenticated=False,
            )
            self.api_key = auth.get("apiKey")
            if not isinstance(self.api_key, str) or not self.api_key:
                raise PluggyError()
            self.expires_at = monotonic() + 3600
        try:
            return self._send(method, path, payload)
        except PluggyError as exc:
            if exc.status == 401:
                self.api_key = None
            raise

    def connectors(self):
        data = self.request("GET", "/connectors?sandbox=true&countries=BR")
        return results(data)

    def connect_token(self, client_user_id, item_id=None):
        body = {"options": {"clientUserId": str(client_user_id), "avoidDuplicates": True}}
        if item_id:
            body["itemId"] = str(item_id)
        token = self.request("POST", "/connect_token", body).get("accessToken")
        if not isinstance(token, str) or not token:
            raise PluggyError()
        return token

    def item(self, item_id):
        return self.request("GET", f"/items/{item_id}")

    def accounts(self, item_id):
        return results(self.request("GET", f"/accounts?itemId={item_id}"))

    def transactions(self, account_id, date_from, date_to):
        params = {"accountId": str(account_id), "dateFrom": str(date_from), "dateTo": str(date_to)}
        seen = set()
        rows = []
        started = monotonic()
        for _ in range(100):
            data = self.request("GET", "/v2/transactions?" + urlencode(params))
            rows.extend(results(data))
            next_page = data.get("next")
            if not next_page:
                return rows
            # Only reuse the cursor. Provider URLs never control the host or account scope.
            if not isinstance(next_page, str):
                raise PluggyError()
            after = parse_qs(urlsplit(next_page).query).get("after", [None])[0]
            if not after or after in seen or monotonic() - started > 240:
                raise PluggyError("A importação excedeu o limite. Tente novamente mais tarde.")
            seen.add(after)
            params["after"] = after
        raise PluggyError("A importação excedeu o limite de páginas.")

    def delete_item(self, item_id):
        try:
            self.request("DELETE", f"/items/{item_id}")
        except PluggyError as exc:
            if exc.status != 404:
                raise


def results(data):
    rows = data.get("results")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise PluggyError("A Pluggy retornou dados incompletos. Tente novamente.")
    return rows
