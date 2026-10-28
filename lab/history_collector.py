"""Vendor-neutral synthetic history collector; no IBKR SDK or network access."""
import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path
from collections import Counter


class TransientError(Exception):
    def __init__(self, code, retry_after=0):
        self.code, self.retry_after = code, retry_after
        super().__init__(str(code))


class Interrupted(Exception):
    pass


class SyntheticProvider:
    """390 synthetic minute offsets, 100-row pages, overlapping boundaries.

    HTTP-like errors exercise a generic adapter contract, not TWS protocol semantics.
    """
    def __init__(self):
        self.failed, self.calls, self.errors = set(), [], Counter()
        self.received_rows = 0

    def fetch(self, symbol, cursor):
        self.calls.append((symbol, cursor))
        number = int(symbol.removeprefix("SIM"))
        code = 429 if cursor == 0 and number % 17 == 0 else (
            503 if cursor == 100 and number % 23 == 0 else None)
        if code and (symbol, cursor) not in self.failed:
            self.failed.add((symbol, cursor))
            self.errors[code] += 1
            raise TransientError(code, retry_after=2 if code == 429 else 0)
        end = min(cursor+100, 390)
        rows = []
        for minute in range(max(0, cursor-1), end):
            price = 10000 + number*10 + minute
            rows.append({"minute": minute, "open_cents": price,
                         "high_cents": price+3, "low_cents": price-2,
                         "close_cents": price+1, "volume": 1000+minute})
        self.received_rows += len(rows)
        return rows, end


def connect(path):
    db = sqlite3.connect(path)
    db.executescript("""
      CREATE TABLE IF NOT EXISTS progress(symbol TEXT PRIMARY KEY, cursor INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS bars(symbol TEXT, minute INTEGER, payload TEXT NOT NULL,
                                     PRIMARY KEY(symbol, minute));
    """)
    return db


def current(db, symbol):
    row = db.execute("SELECT cursor FROM progress WHERE symbol=?", (symbol,)).fetchone()
    return row[0] if row else 0


def commit_page(db, symbol, cursor, rows, next_cursor):
    if type(next_cursor) is not int or not cursor < next_cursor <= 390:
        raise ValueError("Non-advancing or out-of-range cursor")
    duplicates = 0
    with db:
        if current(db, symbol) != cursor:
            raise ValueError("Checkpoint changed")
        for row in rows:
            minute = row["minute"]
            if type(minute) is not int or not 0 <= minute < next_cursor:
                raise ValueError("Invalid synthetic minute")
            values = [row[k] for k in ("open_cents", "high_cents", "low_cents", "close_cents", "volume")]
            if any(type(v) is not int for v in values):
                raise ValueError("Expected integer cents and volume")
            o, h, l, c, v = values
            if not 0 < l <= min(o,c) <= max(o,c) <= h or v < 0:
                raise ValueError("Invalid OHLCV")
            payload = json.dumps(row, sort_keys=True, separators=(",", ":"))
            old = db.execute("SELECT payload FROM bars WHERE symbol=? AND minute=?", (symbol, minute)).fetchone()
            if old:
                if old[0] != payload:
                    raise ValueError("Conflicting duplicate; page and checkpoint rolled back")
                duplicates += 1
            else:
                db.execute("INSERT INTO bars VALUES(?,?,?)", (symbol, minute, payload))
        # A provider must not advance a checkpoint past missing history.
        count = db.execute("SELECT COUNT(*) FROM bars WHERE symbol=? AND minute<?", (symbol,next_cursor)).fetchone()[0]
        if count != next_cursor:
            raise ValueError("Page leaves missing bars before checkpoint")
        db.execute("INSERT INTO progress VALUES(?,?) ON CONFLICT(symbol) DO UPDATE SET cursor=excluded.cursor",
                   (symbol,next_cursor))
    return duplicates


def collect(db, provider, symbols, wait, stop_after_pages=None):
    pages, duplicates, retries = 0, 0, 0
    for symbol in symbols:
        cursor = current(db,symbol)
        while cursor < 390:
            for attempt in range(4):
                try:
                    rows, next_cursor = provider.fetch(symbol,cursor)
                    break
                except TransientError as exc:
                    if attempt == 3 or exc.code not in (429,503):
                        raise
                    delay = max(exc.retry_after, 2**attempt)
                    wait(delay)
                    retries += 1
            duplicates += commit_page(db,symbol,cursor,rows,next_cursor)
            pages += 1
            cursor = next_cursor
            if stop_after_pages is not None and pages == stop_after_pages:
                raise Interrupted("Injected restart after a committed page")
    return {"pages":pages, "duplicates":duplicates, "retries":retries}


def manifest(db, symbols):
    result=[]
    for symbol in symbols:
        payloads=[r[0] for r in db.execute("SELECT payload FROM bars WHERE symbol=? ORDER BY minute", (symbol,))]
        result.append({"symbol":symbol,"bars":len(payloads),"checkpoint":current(db,symbol),
                       "sha256":hashlib.sha256(("\n".join(payloads)+"\n").encode()).hexdigest()})
    return result


def run():
    symbols=[f"SIM{i:03}" for i in range(100)]
    provider, delays = SyntheticProvider(), []
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/"history.db"
        db=connect(path)
        try:
            collect(db,provider,symbols,delays.append,stop_after_pages=23)
        except Interrupted:
            pass
        before=manifest(db,symbols)
        db.close()
        db=connect(path)
        resumed=collect(db,provider,symbols,delays.append)
        after=manifest(db,symbols)
        calls_before=len(provider.calls)
        repeat=collect(db,provider,symbols,delays.append)
        no_op_calls=len(provider.calls)-calls_before
        # Independent clean replay must match every final persisted dataset hash.
        clean=connect(Path(tmp)/"clean.db")
        collect(clean,SyntheticProvider(),symbols,lambda seconds: None)
        identical=after==manifest(clean,symbols)
        sample=[json.loads(r[0]) for r in db.execute("SELECT payload FROM bars WHERE symbol='SIM000' ORDER BY minute LIMIT 5")]
        db.close()
        clean.close()
    return {"mode":"SYNTHETIC_PROVIDER_ONLY", "symbol_count":len(symbols),
            "bars_per_symbol":390, "unique_bars":sum(m["bars"] for m in after),
            "pages_before_restart":23,"pages_after_restart":resumed["pages"],
            "bars_before_restart":sum(m["bars"] for m in before),
            "retry_errors":{str(k):v for k,v in sorted(provider.errors.items())},
            "simulated_wait_seconds":sum(delays),
            "overlap_rows_deduplicated":provider.received_rows-sum(m["bars"] for m in after),
            "completed_rerun_requests":no_op_calls,
            "matches_uninterrupted_run":identical,
            "manifest":after,"sample":sample,
            "scope":"One synthetic 390-minute session, 100 synthetic symbols, one worker. "
                    "A SQLite connection is closed/reopened after an injected interruption. "
                    "Retry delays use a recording clock, not wall-clock sleeping. HTTP-like "
                    "429/503 events are generic test fixtures, not an IBKR protocol emulation. "
                    "No broker SDK, live market data, real pacing validation or vendor authentication."}
