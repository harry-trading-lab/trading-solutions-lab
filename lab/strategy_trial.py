"""Small expanding-window research trial on synthetic daily OHLC observations.

Signals use prior closes. A fully invested long/flat return proxy uses next opens.
Fixed proportional turnover costs; no broker fill simulation or profitability claim.
"""
import math
import random


def fixture():
    rng = random.Random(7421)
    bars = []
    previous = 100.0
    for day in range(481):
        drift = (0.0008, -0.0006, 0.0001)[(day // 80) % 3]
        opening = previous * (1 + rng.uniform(-0.004, 0.004))
        close = opening * (1 + drift + rng.uniform(-0.015, 0.015))
        bars.append({"day": day, "open": round(opening, 6), "close": round(close, 6)})
        previous = close
    return bars


def validate(bars):
    for index, bar in enumerate(bars):
        if bar["day"] != index:
            raise ValueError("Expected consecutive synthetic observation indices")
        for field in ("open", "close"):
            value = bar[field]
            if not math.isfinite(value) or value <= 0:
                raise ValueError("Prices must be finite and positive")


def signal(bars, index, lookback):
    if type(lookback) is not int or lookback < 2 or index < lookback:
        raise ValueError("Insufficient warmup or invalid lookback")
    closes = [b["close"] for b in bars[index-lookback:index]]
    return int(closes[-1] > sum(closes)/lookback)


def evaluate(bars, start, end, lookback, cost_bps=5, buy_hold=False):
    """Trade at open[start..end-1], mark at next open, liquidate at open[end].

    Costs are an additive approximation in daily portfolio-return units, including
    final liquidation. Each evaluated window starts flat. No exposure leverage.
    """
    validate(bars)
    if not math.isfinite(cost_bps) or not 0 <= cost_bps <= 100:
        raise ValueError("Cost must be finite, between 0 and 100 bps")
    if not 0 <= start < end < len(bars) or (not buy_hold and start < lookback):
        raise ValueError("Invalid evaluation window")
    equity, peak, drawdown, previous = 1.0, 1.0, 0.0, 0
    trace = []
    for i in range(start, end):
        position = 1 if buy_hold else signal(bars, i, lookback)
        turnover = abs(position-previous)
        if i == end-1:
            turnover += position  # Final liquidation, included exactly once.
        gross = position * (bars[i+1]["open"]/bars[i]["open"]-1)
        cost = turnover * cost_bps / 10000
        net = gross - cost
        equity *= 1 + net
        peak = max(peak, equity)
        drawdown = min(drawdown, equity/peak-1)
        trace.append({"day": i, "feature_last_day": i-1, "position": position,
                      "gross": gross, "cost": cost, "net": net,
                      "turnover": turnover, "equity": equity})
        previous = position
    return {"net_return": equity-1, "max_drawdown": drawdown,
            "turnover": sum(t["turnover"] for t in trace), "trace": trace}


def choose(bars, cutoff, candidates=(5, 10, 20, 40), cost_bps=5):
    if not candidates or len(set(candidates)) != len(candidates):
        raise ValueError("Distinct candidate lookbacks are required")
    if any(type(c) is not int or c < 2 for c in candidates):
        raise ValueError("Invalid candidate lookback")
    # One complete observation separates the final training mark and test entry.
    training = [{"lookback": c, "net_return": evaluate(
        bars[:cutoff], max(candidates), cutoff-1, c, cost_bps)["net_return"]}
        for c in candidates]
    winner = max(training, key=lambda r: (r["net_return"], -r["lookback"]))
    return winner["lookback"], training


def run(bars=None):
    bars = fixture() if bars is None else bars
    validate(bars)
    if len(bars) < 481:
        raise ValueError("Trial needs 481 observations")
    folds, curve, baseline = [], [1.0], [1.0]
    candidates = (5, 10, 20, 40)
    for start in (240, 300, 360, 420):
        chosen, scores = choose(bars, start, candidates)
        test = evaluate(bars, start, start+60, chosen)
        benchmark = evaluate(bars, start, start+60, chosen, buy_hold=True)
        stress = evaluate(bars, start, start+60, chosen, cost_bps=10)
        folds.append({"test_start": start, "test_end_exclusive": start+60,
                      "last_training_mark": start-1, "selected_lookback": chosen,
                      "training_candidates": scores,
                      "test": test, "benchmark": benchmark,
                      "double_cost_net_return": stress["net_return"]})
        for row, ref in zip(test["trace"], benchmark["trace"]):
            curve.append(curve[-1]*(1+row["net"]))
            baseline.append(baseline[-1]*(1+ref["net"]))
    return {"mode": "SYNTHETIC_RESEARCH_TRIAL", "candidates": list(candidates),
            "fold_count": len(folds), "out_of_sample_observations": len(curve)-1,
            "net_return": curve[-1]-1, "benchmark_return": baseline[-1]-1,
            "curve": curve, "benchmark_curve": baseline, "folds": folds,
            "scope": "Synthetic one-asset long/flat SMA trial; 4 predeclared lookbacks. "
                     "Expanding training windows, 4 non-overlapping test windows, 5 bps per "
                     "unit turnover and 10 bps cost stress. Separate windows start and end flat, "
                     "including the buy-and-hold comparator. Costs approximate daily returns. "
                     "No market-specific taxes, dividends, universe selection, realistic fills, "
                     "statistical-significance test or NSE/BSE integration. This is not evidence of alpha."}
