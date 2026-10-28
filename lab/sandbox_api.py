"""Small real HTTP smoke-test clients; trading hosts are sandbox-only."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from uuid import uuid4


class APIError(RuntimeError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise APIError("HTTP redirect refused; credentials were not forwarded")


class SandboxHTTP:
    HOSTS = {
        "tastytrade": "https://api.cert.tastyworks.com",
        "alpaca": "https://paper-api.alpaca.markets",
        "alpaca_data": "https://data.alpaca.markets",
        "oanda": "https://api-fxpractice.oanda.com",
    }

    def __init__(self, venue, headers=None):
        self.venue = venue
        self.base = self.HOSTS[venue]
        self.headers = {"User-Agent": "trading-solutions-lab/0.1", "Accept": "application/json", **(headers or {})}
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, method, path, payload=None):
        # No caller-supplied hosts, redirects, or implicit retries of order POSTs.
        parsed = urllib.parse.urlsplit(path)
        if not path.startswith("/") or path.startswith("//") or parsed.scheme or parsed.netloc:
            raise ValueError("A relative API path is required")
        if self.venue == "alpaca_data" and method != "GET":
            raise ValueError("Market data access is read-only")
        data = None if payload is None else json.dumps(payload).encode()
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={**self.headers, "Content-Type": "application/json"})
        try:
            with self.opener.open(req, timeout=25) as response:
                raw = response.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            # Do not print response bodies: they can contain account identifiers.
            raise APIError(f"HTTP {exc.code}; no automatic retry") from None
        except (urllib.error.URLError, TimeoutError):
            raise APIError("Network failure; outcome may be unknown, no automatic retry") from None


class TastytradeSandbox:
    def __init__(self, credentials):
        if credentials.get("environment") != "sandbox":
            raise ValueError("Sandbox credentials required")
        self.http = SandboxHTTP("tastytrade")
        token = self.http.request("POST", "/oauth/token", {
            "grant_type": "refresh_token", "refresh_token": credentials["refresh_token"],
            "client_secret": credentials["client_secret"], "client_id": credentials["client_id"],
        })
        self.http.headers["Authorization"] = "Bearer " + token["access_token"]
        accounts = self.http.request("GET", "/customers/me/accounts")["data"]["items"]
        target = credentials.get("account_number")
        eligible = [x["account"] for x in accounts if not target or x["account"]["account-number"] == target]
        if len(eligible) != 1:
            raise ValueError("Select exactly one sandbox account in the private credentials file")
        self.account = eligible[0]["account-number"]
        self.path = "/accounts/" + urllib.parse.quote(self.account, safe="")

    def check(self, exercise=False):
        self.http.request("GET", self.path + "/balances")
        self.http.request("GET", self.path + "/positions")
        result = {"venue": "tastytrade", "environment": "sandbox", "oauth": "PASS",
                  "account_query": "PASS", "balances": "PASS", "positions": "PASS"}
        if not exercise:
            return result
        # Sandbox documentation: limit >= $3 remains Live, allowing cancel testing.
        order = {"time-in-force": "Day", "order-type": "Limit", "price": "10.00",
                 "price-effect": "Debit", "source": "trading-solutions-lab",
                 "external-identifier": "lab-" + uuid4().hex,
                 "legs": [{"instrument-type": "Equity", "symbol": "AAPL", "quantity": 1,
                           "action": "Buy to Open"}]}
        self.http.request("POST", self.path + "/orders/dry-run", order)
        result["order_dry_run"] = "PASS"
        created = self.http.request("POST", self.path + "/orders", order)["data"]["order"]
        oid = str(created["id"])
        path = self.path + "/orders/" + urllib.parse.quote(oid, safe="")
        states = [created["status"]]
        try:
            current = self.http.request("GET", path)["data"]
            states.append(current["status"])
        finally:
            self.http.request("DELETE", path)
        for _ in range(10):
            current = self.http.request("GET", path)["data"]
            states.append(current["status"])
            if current["status"] in {"Cancelled", "Canceled", "Filled", "Rejected", "Expired"}:
                break
            time.sleep(0.5)
        result.update(order_submit="PASS", order_query="PASS", order_states=states,
                      cancel_confirmed=current["status"] in {"Cancelled", "Canceled"})
        if not result["cancel_confirmed"]:
            raise APIError("Test order did not reach confirmed canceled state; inspect sandbox dashboard")
        return result


class AlpacaPaper:
    def __init__(self, credentials):
        if credentials.get("environment") != "paper":
            raise ValueError("Paper credentials required")
        headers = {"APCA-API-KEY-ID": credentials["api_key"], "APCA-API-SECRET-KEY": credentials["api_secret"]}
        self.http = SandboxHTTP("alpaca", headers)
        self.data = SandboxHTTP("alpaca_data", headers)

    def check(self, exercise=False):
        account = self.http.request("GET", "/v2/account")
        clock = self.http.request("GET", "/v2/clock")
        bars = self.data.request("GET", "/v2/stocks/AAPL/bars?timeframe=1Day&start=2025-01-02T00%3A00%3A00Z&end=2025-01-10T00%3A00%3A00Z&feed=iex&limit=20")
        result = {"venue": "alpaca", "environment": "paper", "account_query": "PASS",
                  "account_status": account["status"], "market_open": clock["is_open"],
                  "historical_feed": "iex", "historical_bar_count": len(bars.get("bars") or [])}
        if not result["historical_bar_count"]:
            raise APIError("No historical bars returned")
        if not exercise:
            return result
        created = self.http.request("POST", "/v2/orders", {
            "symbol": "AAPL", "qty": "1", "side": "buy", "type": "limit", "limit_price": "1.00",
            "time_in_force": "day", "client_order_id": "lab-" + uuid4().hex,
        })
        path = "/v2/orders/" + urllib.parse.quote(created["id"], safe="")
        states = [created["status"]]
        try:
            states.append(self.http.request("GET", path)["status"])
        finally:
            self.http.request("DELETE", path)
        for _ in range(10):
            current = self.http.request("GET", path)
            states.append(current["status"])
            if current["status"] in {"canceled", "filled", "rejected", "expired"}:
                break
            time.sleep(0.5)
        if current["status"] != "canceled":
            raise APIError("Paper order cancellation not confirmed; inspect dashboard")
        result.update(order_submit="PASS", order_query="PASS", order_states=states, cancel_confirmed=True)
        return result


class OandaPractice:
    def __init__(self, credentials):
        if credentials.get("environment") != "practice":
            raise ValueError("Practice credentials required")
        self.http = SandboxHTTP("oanda", {"Authorization": "Bearer " + credentials["api_token"]})
        accounts = self.http.request("GET", "/v3/accounts")["accounts"]
        target = credentials.get("account_number")
        eligible = [x for x in accounts if not target or x["id"] == target]
        if len(eligible) != 1:
            raise ValueError("Select exactly one practice account in the private credentials file")
        self.path = "/v3/accounts/" + urllib.parse.quote(eligible[0]["id"], safe="")

    def check(self, exercise=False):
        self.http.request("GET", self.path + "/summary")
        self.http.request("GET", self.path + "/openPositions")
        instrument = self.http.request("GET", self.path + "/instruments?instruments=EUR_USD")["instruments"][0]
        pricing = self.http.request("GET", self.path + "/pricing?instruments=EUR_USD")["prices"][0]
        bars = self.http.request("GET", self.path + "/instruments/EUR_USD/candles?granularity=M1&price=M&count=20")["candles"]
        if not bars or not pricing.get("bids") or not pricing.get("asks"):
            raise APIError("Missing practice market data")
        result = {"venue": "oanda", "environment": "practice", "account_query": "PASS",
                  "account_summary": "PASS", "positions": "PASS", "pricing_snapshot": "PASS",
                  "instrument": "EUR_USD", "historical_granularity": "M1", "historical_bar_count": len(bars),
                  "complete_bar_count": sum(bool(b["complete"]) for b in bars)}
        if not exercise:
            return result
        tick = Decimal(1).scaleb(-instrument["displayPrecision"])
        price = (Decimal(pricing["bids"][0]["price"]) * Decimal("0.90")).quantize(tick, rounding=ROUND_DOWN)
        units = Decimal(instrument["minimumTradeSize"])
        if not (Decimal(0) < units <= Decimal(100)) or price <= 0:
            raise APIError("Unexpected instrument minimum size or price; order exercise refused")
        created = self.http.request("POST", self.path + "/orders", {"order": {
            "type": "LIMIT", "instrument": "EUR_USD", "units": str(units), "price": str(price),
            "timeInForce": "GTC", "positionFill": "DEFAULT",
            "clientExtensions": {"id": "lab-" + uuid4().hex, "tag": "sandbox-smoke-test"},
        }})
        oid = created["orderCreateTransaction"]["id"]
        path = self.path + "/orders/" + urllib.parse.quote(oid, safe="")
        try:
            before = self.http.request("GET", path)["order"]["state"]
        finally:
            self.http.request("PUT", path + "/cancel")
        after = self.http.request("GET", path)["order"]["state"]
        if after != "CANCELLED":
            raise APIError("Practice order cancellation not confirmed; inspect dashboard")
        result.update(order_submit="PASS", order_query="PASS", order_states=[before, after], cancel_confirmed=True)
        return result


def timestamp():
    return datetime.now(timezone.utc).isoformat()
