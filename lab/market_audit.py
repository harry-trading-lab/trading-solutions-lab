"""Read-only audit of synthetic paginated OHLCV data using XNYS calendars."""
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import exchange_calendars as xcals

DATES = ("2022-03-11", "2022-03-14", "2022-11-23", "2022-11-24", "2022-11-25")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def schedule(days=DATES):
    calendar = xcals.get_calendar("XNYS", start="2018-01-01", end="2022-12-31")
    result = {}
    for day in days:
        if not calendar.is_session(day):
            result[day] = []
            continue
        start, end = calendar.session_open(day).to_pydatetime(), calendar.session_close(day).to_pydatetime()
        bars = []
        while start < end:
            bars.append(start.isoformat())
            start += timedelta(minutes=5)
        result[day] = bars
    return result


def write_fixture(directory, broken=False):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    sessions = schedule()
    rows = []
    for day, timestamps in sessions.items():
        for index, timestamp in enumerate(timestamps):
            price = round(100 + index / 100, 2)
            rows.append(dict(symbol="DEMO", timestamp=timestamp, open=price,
                             high=price + .2, low=price - .2, close=price + .1, volume=1000))
    if broken:
        rows.pop(12)                         # a missing bar
        duplicate = dict(rows[4], close=rows[4]["close"] + .05)
        rows.append(duplicate)               # conflicting duplicate
        rows.append(dict(rows[0], timestamp="2022-11-24T15:00:00+00:00"))
        rows.append(dict(rows[0], symbol="OTHER"))
        rows[20]["low"] = rows[20]["high"] + 1
    manifest = {"fixture": "synthetic OHLCV; no market-data vendor", "symbol": "DEMO",
                "bar_interval_minutes": 5, "bar_timestamp": "interval start",
                "dates": list(DATES), "pages": []}
    for index, offset in enumerate(range(0, len(rows), 60)):
        name = f"page-{index:02d}.json"
        request = None if index == 0 else f"cursor-{index}"
        next_cursor = f"cursor-{index + 1}" if offset + 60 < len(rows) else None
        if broken and index == 2:
            request = "broken-chain"
        body = {"request_cursor": request, "next_cursor": next_cursor, "bars": rows[offset:offset + 60]}
        path = directory / name
        path.write_text(json.dumps(body, indent=2) + "\n")
        manifest["pages"].append({"file": name, "sha256": digest(path)})
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if broken:
        # An edit after receipt creation must be detected independently of data validation.
        path = directory / "page-00.json"
        altered = json.loads(path.read_text())
        altered["bars"][0]["volume"] += 1
        path.write_text(json.dumps(altered, indent=2) + "\n")
    return directory


def audit(directory):
    directory = Path(directory).resolve()
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest["bar_interval_minutes"] != 5 or manifest["bar_timestamp"] != "interval start":
        raise ValueError("This demonstration expects five-minute interval-start bars")
    sessions = schedule(manifest["dates"])
    expected = {t for times in sessions.values() for t in times}
    findings, observed, records, sources = [], [], defaultdict(list), []
    previous_cursor = None
    seen_files, seen_cursors = set(), set()

    def flag(code, source, detail):
        findings.append({"code": code, "source": source, "detail": detail})

    for index, entry in enumerate(manifest["pages"]):
        path = (directory / entry["file"]).resolve()
        if not path.is_relative_to(directory) or path == manifest_path:
            raise ValueError("Manifest page path escapes the fixture or targets manifest")
        if str(path) in seen_files:
            flag("DUPLICATE_PAGE", entry["file"], "Page occurs more than once in manifest")
        seen_files.add(str(path))
        actual = digest(path)
        sources.append({"file": entry["file"], "sha256": actual, "receipt_sha256": entry["sha256"]})
        if actual != entry["sha256"]:
            flag("HASH_MISMATCH", entry["file"], "Raw bytes differ from the stored SHA-256 receipt")
        body = json.loads(path.read_text())
        if body["request_cursor"] != previous_cursor:
            flag("PAGINATION_GAP", entry["file"], "Request cursor does not continue preceding response")
        if index > 0 and body["request_cursor"] is None:
            flag("PAGINATION_GAP", entry["file"], "Page follows a terminated cursor chain")
        next_cursor = body["next_cursor"]
        if next_cursor is not None:
            if next_cursor in seen_cursors:
                flag("CURSOR_CYCLE", entry["file"], "Repeated next cursor")
            seen_cursors.add(next_cursor)
        previous_cursor = next_cursor
        for row_index, row in enumerate(body["bars"]):
            source = f"{entry['file']}#/bars/{row_index}"
            if row["symbol"] != manifest["symbol"]:
                flag("UNEXPECTED_SYMBOL", source, row["symbol"])
                continue
            ts = datetime.fromisoformat(row["timestamp"])
            if ts.tzinfo is None:
                flag("NAIVE_TIMESTAMP", source, row["timestamp"])
                continue
            # Normalize equivalent offsets to UTC so duplicate checks are representation-independent.
            from datetime import timezone
            timestamp = ts.astimezone(timezone.utc).isoformat()
            if timestamp not in expected:
                flag("OUT_OF_SESSION", source, timestamp)
            observed.append(timestamp)
            values = tuple(row[k] for k in ("open", "high", "low", "close", "volume"))
            import math
            if (not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in values)
                or not 0 < row["low"] <= min(row["open"], row["close"]) <= max(row["open"], row["close"]) <= row["high"]
                or row["volume"] < 0):
                flag("INVALID_OHLCV", source, "Non-finite, negative, or inconsistent OHLCV")
            records[timestamp].append((source, values))
    if previous_cursor is not None:
        flag("INCOMPLETE_PAGINATION", "manifest.json", "Final page advertises an unfetched next page")
    for timestamp, entries in records.items():
        if len(entries) > 1:
            flag("DUPLICATE_BAR", entries[1][0], timestamp)
            if len({values for _, values in entries}) > 1:
                flag("CONFLICTING_DUPLICATE", entries[1][0], "Duplicate key has different OHLCV values")
    missing = sorted(expected - set(observed))
    for timestamp in missing:
        flag("MISSING_BAR", "expected XNYS schedule", timestamp)
    counts = dict(sorted(Counter(f["code"] for f in findings).items()))
    return {"decision": "HOLD" if findings else "PASS", "input_kind": "synthetic",
            "expected_bars": len(expected), "observed_symbol_rows": len(observed),
            "missing_bars": len(missing), "finding_count": len(findings), "finding_counts": counts,
            "sessions": {day: {"bars": len(times), "open_utc": times[0] if times else None,
                              "last_bar_utc": times[-1] if times else None} for day, times in sessions.items()},
            "manifest_sha256": digest(manifest_path), "sources": sources, "findings": findings,
            "scope": "Fixture byte integrity, cursor continuity, XNYS schedule and OHLCV checks. Not a client audit or source-authenticity certification."}


def run(output):
    output = Path(output)
    clean, broken = output / "fixtures" / "clean", output / "fixtures" / "broken"
    write_fixture(clean)
    write_fixture(broken, broken=True)
    before = {str(p): digest(p) for p in broken.glob("*.json")}
    result = {"clean": audit(clean), "broken": audit(broken)}
    assert result["clean"]["decision"] == "PASS"
    assert result["broken"]["decision"] == "HOLD"
    assert before == {str(p): digest(p) for p in broken.glob("*.json")}
    return result
