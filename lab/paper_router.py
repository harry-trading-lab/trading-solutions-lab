"""Closed-candle strategy plus durable, isolated execution across simulated accounts."""
from dataclasses import dataclass
from hashlib import sha256
from math import isfinite, sin
from pathlib import Path
import sqlite3
import tempfile


@dataclass(frozen=True)
class Signal:
    key: str
    closed_at: int
    price: float
    target: int
    reason: str = "moving-average rule"


class PaperVenue:
    """Network-free account simulator; label never selects a live API."""
    def __init__(self, name, enabled=True):
        self.name, self.enabled = name, enabled
        self.connected = True
        self.position = 0
        self.cash = 10000.0
        self.orders = {}
        self.submissions = 0
        self.reject_next = False
        self.lose_ack_once = False

    def snapshot(self):
        if not self.connected:
            raise ConnectionError("Simulated account disconnected")
        return self.position

    def lookup(self, key):
        if not self.connected:
            raise ConnectionError("Simulated account disconnected")
        return self.orders.get(key)

    def submit(self, key, delta, price):
        if not self.connected:
            raise ConnectionError("Simulated account disconnected")
        if key in self.orders:
            raise AssertionError("Duplicate reached paper venue")
        self.submissions += 1
        rejected = self.reject_next or self.position + delta < 0
        self.reject_next = False
        status = "REJECTED" if rejected else "FILLED"
        if not rejected:
            self.position += delta
            self.cash -= delta * price
        order = {"status": status, "delta": delta, "position": self.position, "price": price}
        self.orders[key] = order
        if self.lose_ack_once:
            self.lose_ack_once = False
            raise TimeoutError("Filled at venue; acknowledgement lost")
        return order


class Router:
    """One worker, one long-only symbol, stable per-account intent keys."""
    def __init__(self, path, venues, max_position=2, max_age=120):
        self.venues = venues
        self.max_position, self.max_age = max_position, max_age
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("""CREATE TABLE IF NOT EXISTS intents (
            key TEXT PRIMARY KEY, account TEXT, signal_key TEXT, target INTEGER,
            price REAL, delta INTEGER, status TEXT
        )""")
        self.db.commit()
        self.events = []

    def close(self):
        self.db.close()

    def log(self, account, event, signal, **details):
        self.events.append({"account": account, "event": event, "signal": signal, **details})

    def ledger_position(self, account):
        return self.db.execute(
            "SELECT COALESCE(SUM(delta),0) FROM intents WHERE account=? AND status='FILLED'", (account,)
        ).fetchone()[0]

    def recover(self, venue):
        pending = self.db.execute(
            "SELECT * FROM intents WHERE account=? AND status IN ('PENDING','UNKNOWN')", (venue.name,)
        ).fetchall()
        for row in pending:
            found = venue.lookup(row["key"])
            if found is None:
                raise ValueError("Unresolved previous outcome")
            if found["delta"] != row["delta"] or found["status"] not in {"FILLED", "REJECTED"}:
                raise ValueError("Invalid venue reconciliation result")
            with self.db:
                self.db.execute("UPDATE intents SET status=? WHERE key=?", (found["status"], row["key"]))
            self.log(venue.name, "RECOVERED", row["signal_key"], status=found["status"])

    def dispatch(self, signal, now):
        if (not signal.key or type(signal.target) is not int or not 0 <= signal.target <= self.max_position
            or not isfinite(signal.price) or signal.price <= 0
            or not isfinite(now) or not isfinite(signal.closed_at)
            or not 0 <= now - signal.closed_at <= self.max_age):
            raise ValueError("Signal is unclosed, stale, invalid, or exceeds the position limit")
        outcomes = {}
        for venue in self.venues:
            if not venue.enabled:
                outcomes[venue.name] = "DISABLED"
                continue
            key = sha256(f"{venue.name}:{signal.key}".encode()).hexdigest()[:24]
            try:
                old = self.db.execute("SELECT * FROM intents WHERE key=?", (key,)).fetchone()
                if old and (old["target"] != signal.target or old["price"] != signal.price):
                    raise ValueError("Signal ID reused with changed intent")
                self.recover(venue)
                if venue.snapshot() != self.ledger_position(venue.name):
                    raise ValueError("Position differs from fill ledger")
                if old:
                    outcomes[venue.name] = "DEDUPLICATED"
                    self.log(venue.name, "DEDUPLICATED", signal.key)
                    continue
                delta = signal.target - venue.position
                if delta == 0:
                    outcomes[venue.name] = "AT_TARGET"
                    continue
                with self.db:
                    self.db.execute("INSERT INTO intents VALUES (?,?,?,?,?,?,'PENDING')",
                                    (key, venue.name, signal.key, signal.target, signal.price, delta))
                try:
                    order = venue.submit(key, delta, signal.price)
                except (ConnectionError, TimeoutError):
                    with self.db:
                        self.db.execute("UPDATE intents SET status='UNKNOWN' WHERE key=?", (key,))
                    outcomes[venue.name] = "UNKNOWN"
                    self.log(venue.name, "UNKNOWN", signal.key)
                    continue
                with self.db:
                    self.db.execute("UPDATE intents SET status=? WHERE key=?", (order["status"], key))
                outcomes[venue.name] = order["status"]
                self.log(venue.name, order["status"], signal.key, delta=delta, price=signal.price)
            except (ConnectionError, ValueError) as exc:
                outcomes[venue.name] = "HELD"
                self.log(venue.name, "HELD", signal.key, reason=str(exc))
        return outcomes


def candles(count=60):
    return [{"closed_at": 1700000000 + i * 60,
             "close": round(100 + 2.4 * sin(i / 5) + .015 * i, 4)} for i in range(count)]


def signals(bars):
    """Pure causal rule: only current/prior closed bars; long/flat with stop/trailing exit."""
    prices, result, position, peak, entry = [], [], 0, None, None
    for bar in bars:
        price = bar["close"]
        prices.append(price)
        if len(prices) < 8:
            continue
        fast, slow = sum(prices[-3:]) / 3, sum(prices[-8:]) / 8
        target, reason = position, "hold"
        if position:
            peak = max(peak, price)
            if price <= entry * .985:
                target, reason = 0, "1.5% close-based stop"
            elif price <= peak * .99:
                target, reason = 0, "1% close-based trailing stop"
            elif fast < slow:
                target, reason = 0, "moving-average exit"
        elif fast > slow:
            target, reason = 2, "moving-average entry"
            peak = entry = price
        position = target
        result.append(Signal(f"bar-{bar['closed_at']}", bar["closed_at"], price, target, reason))
    return result


def run():
    venues = [PaperVenue(f"MT5-SIM-{i}", enabled=(i != 5)) for i in range(1, 6)]
    venues += [PaperVenue("BINANCE-SIM"), PaperVenue("BINGX-SIM")]
    venues[5].lose_ack_once = True
    venues[6].reject_next = True
    bars, timeline, events = candles(), [], []
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "intents.db"
        router = Router(path, venues)
        try:
            for index, signal in enumerate(signals(bars)):
                venues[2].connected = not 3 <= index < 8
                if index == 15:
                    events.extend(router.events)
                    router.close()
                    router = Router(path, venues)
                outcome = router.dispatch(signal, signal.closed_at)
                replay = router.dispatch(signal, signal.closed_at)
                timeline.append({"signal": signal.key, "price": signal.price, "target": signal.target,
                                 "reason": signal.reason, "outcomes": outcome, "replay": replay})
            events.extend(router.events)
            accounts = [{"account": v.name, "enabled": v.enabled, "position": v.position,
                         "ledger_position": router.ledger_position(v.name),
                         "submissions": v.submissions, "distinct_order_ids": len(v.orders),
                         "paper_equity": round(v.cash + v.position * bars[-1]["close"], 4)}
                        for v in venues]
            assert all(a["submissions"] == a["distinct_order_ids"] for a in accounts)
            assert all(a["position"] == a["ledger_position"] for a in accounts)
        finally:
            router.close()
    from collections import Counter
    return {"input_kind": "synthetic candles + simulated accounts", "accounts": accounts, "timeline": timeline,
            "events": events, "event_counts": dict(Counter(e["event"] for e in events)),
            "signal_count": len(timeline), "account_count": len(accounts),
            "duplicate_submissions": sum(a["submissions"] - a["distinct_order_ids"] for a in accounts),
            "candles": bars, "process_restarts": 1,
            "scope": "Offline one-symbol, single-worker long/flat orchestration demo. MT5/Binance/BingX labels denote simulations, not live adapters. Immediate fills at bar close exclude fees and slippage."}
