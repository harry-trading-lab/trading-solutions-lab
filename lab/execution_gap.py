"""Exactly reconcile theoretical P&L to fill P&L for a supplied trade ledger."""
from decimal import Decimal
from datetime import datetime

D = lambda value: Decimal(str(value))


def reconcile_trade(trade):
    side = {"LONG": Decimal(1), "SHORT": Decimal(-1)}[trade["side"]]
    quantity = D(trade["quantity"])
    prices = [D(trade[key]) for key in (
        "entry_signal_mid", "exit_signal_mid", "entry_fill_mid", "exit_fill_mid", "entry_fill", "exit_fill")]
    if not quantity.is_finite() or quantity <= 0 or not all(p.is_finite() and p > 0 for p in prices):
        raise ValueError("Quantity and prices must be positive finite numbers")
    entry_signal, exit_signal, entry_mid, exit_mid, entry_fill, exit_fill = prices
    fees = D(trade["fees"])
    if not fees.is_finite() or fees < 0:
        raise ValueError("Fees must be non-negative and finite")
    theoretical = side * quantity * (exit_signal - entry_signal)
    timing = side * quantity * ((exit_mid - exit_signal) - (entry_mid - entry_signal))
    execution = side * quantity * ((exit_fill - exit_mid) - (entry_fill - entry_mid))
    net = side * quantity * (exit_fill - entry_fill) - fees
    residual = net - (theoretical + timing + execution - fees)
    findings = []
    times = {key: datetime.fromisoformat(trade[key]) for key in
             ("feature_asof", "signal_at", "entry_filled_at", "exit_signal_at", "exit_filled_at")}
    if any(t.tzinfo is None for t in times.values()):
        raise ValueError("Every timestamp must include a timezone")
    if times["feature_asof"] > times["signal_at"]:
        findings.append("FEATURE_AFTER_SIGNAL")
    if not times["signal_at"] <= times["entry_filled_at"] <= times["exit_signal_at"] <= times["exit_filled_at"]:
        findings.append("NON_CAUSAL_FILL_TIMELINE")
    return {"trade_id": trade["trade_id"], "side": trade["side"],
            "theoretical": float(theoretical), "timing": float(timing), "execution": float(execution),
            "fees": float(fees), "net": float(net), "residual": float(residual), "findings": findings,
            "entry_latency_ms": (times["entry_filled_at"] - times["signal_at"]).total_seconds() * 1000}


def fixture():
    rows = []
    for i in range(8):
        side = 1 if i % 2 == 0 else -1
        entry = D(100 + i * 2)
        exit_price = entry + D(side) * D([1.2, .8, -.4, 1.5][i % 4])
        rows.append({
            "trade_id": f"T{i + 1:02d}", "side": "LONG" if side == 1 else "SHORT", "quantity": 100,
            "entry_signal_mid": str(entry), "exit_signal_mid": str(exit_price),
            "entry_fill_mid": str(entry + D(side) * D(".12")),
            "exit_fill_mid": str(exit_price - D(side) * D(".08")),
            "entry_fill": str(entry + D(side) * D(".15")),
            "exit_fill": str(exit_price - D(side) * D(".11")),
            "fees": "4.00", "feature_asof": f"2022-11-23T14:{30+i:02d}:00+00:00",
            "signal_at": f"2022-11-23T14:{30+i:02d}:00+00:00",
            "entry_filled_at": f"2022-11-23T14:{30+i:02d}:00.250+00:00",
            "exit_signal_at": f"2022-11-23T15:{30+i:02d}:00+00:00",
            "exit_filled_at": f"2022-11-23T15:{30+i:02d}:00.400+00:00"})
    rows[2]["feature_asof"] = "2022-11-23T14:33:00+00:00"
    return rows


def analyze(rows):
    ids = [r["trade_id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate trade IDs: reconcile the ledger before aggregating")
    trades = [reconcile_trade(r) for r in rows]
    totals = {key: float(sum(D(t[key]) for t in trades)) for key in
              ("theoretical", "timing", "execution", "fees", "net", "residual")}
    curves = {"theoretical": [0.0], "net": [0.0]}
    for trade in trades:
        for key in curves:
            curves[key].append(round(curves[key][-1] + trade[key], 8))
    return {"input_kind": "synthetic matched trade ledger", "trade_count": len(trades), "totals": totals,
            "curves": curves, "trades": trades,
            "causality_flags": sum(bool(t["findings"]) for t in trades),
            "scope": "Arithmetic attribution for supplied matched trades. No profitability claim, strategy optimization, or inference about an unseen live system."}
