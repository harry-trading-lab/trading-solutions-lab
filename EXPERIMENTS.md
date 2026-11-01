# Trading Solutions Lab

**See a working result before commissioning the full integration.**

Six executable demonstrations for market-data audits, trading-system diagnostics,
multi-account bots, repeated order plans, strategy validation and resumable history collection. Each includes source code, sample inputs, an executed report,
and automated tests.

[![Tests](https://github.com/harry-trading-lab/trading-solutions-lab/actions/workflows/tests.yml/badge.svg)](https://github.com/harry-trading-lab/trading-solutions-lab/actions/workflows/tests.yml)

| Your problem | Open the demonstration | Executed result |
|---|---|---|
| Can I trust the data feeding my research? | [Market Data Audit](reports/data-audit/) | Eight seeded issue classes detected; clean control passes |
| Why does paper/live execution differ from the backtest? | [Execution Diagnostic](reports/execution-gap/) | Every dollar of the sample P&L difference reconciles |
| Can one signal run independently across several accounts? | [Multi-Account Bot](reports/multi-account-bot/) | Seven simulated accounts; no duplicate order submissions |
| Can I repeat an entry while keeping each stop attached correctly? | [Order Repeat Preview](reports/order-repeat/) | Four repeats produce five independently linked pairs |
| How do I validate a strategy before building the full engine? | [Strategy Validation Trial](reports/strategy-trial/) | Four frozen-parameter test windows, baseline and cost stress |
| Can history collection recover after a failure? | [Resumable History Collector](reports/history-collector/) | 39,000 synthetic bars; resumed hashes match the clean run |

The six demonstrations above use synthetic prices, signals, fills and broker accounts.
They run locally and are original portfolio examples, not client results.
The demonstrations and sandbox adapters were developed with AI assistance for this
portfolio. They use the open-source dependencies listed in `requirements.txt` and
official API documentation; no client source code or proprietary strategies are included.

**Real API verification:** [Sandbox integration checks](reports/sandbox-api/) now include
executed tastytrade, OANDA and Alpaca sandbox account-query and submit/cancel cycles over HTTPS,
plus OANDA EUR/USD pricing/candles and Alpaca IEX historical daily bars.
The sandbox uses simulated funds. Credentials and account identifiers are not published.

## New: three demand-led reusable solutions

These original solutions address public requests for indicator performance,
restricted calculation APIs and AI analysis review. Each includes runnable code,
adversarial tests, generated reports and explicit integration limits.

| Inspect the solution | What the evidence demonstrates |
|---|---|
| [Anchored VWAP performance](reports/anchored-vwap/) | Range queries match a separate reference; historical corrections invalidate affected aggregates |
| [Calculation service boundary](reports/calculation-boundary/) | Two HTTP processes; allowed/denied routes and upstream failure handling |
| [AI analysis review](reports/analysis-review/) | Clean control plus seeded leakage, split contamination and statistical-claim issues |

[Design, demand references and run instructions](solutions/README.md).
These are public reference implementations, not completed client projects.

## 1. Market Data Audit

[![Data audit preview](reports/data-audit/preview.png)](reports/data-audit/)

Read-only checks cover SHA-256 receipt integrity, page continuity, conflicting duplicates,
missing bars, OHLCV constraints, and expected sessions. The example uses the established
[exchange_calendars](https://github.com/gerrymanoim/exchange_calendars) XNYS calendar,
including daylight-saving transitions, Thanksgiving closure, and early close.
Tests also cover the 2018-12-05 exceptional closure.

**A first milestone:** examine one sanitized acquisition component and sample data,
then deliver findings with evidence and next steps.

[Source](lab/market_audit.py) · [Report](reports/data-audit/) · [Input fixtures](reports/data-audit/fixtures/)

## 2. Backtest-to-Fill Diagnostic

[![Execution diagnostic preview](reports/execution-gap/preview.png)](reports/execution-gap/)

A matched trade ledger is decomposed into theoretical P&L, signal-to-fill timing,
fill-versus-mid execution difference, and fees. Long and short trades use the same
signed accounting identity. A separate check flags future-dated features.

**A first milestone:** map one strategy's backtest and execution logs to a matched ledger,
explain the gap, and identify the next concrete investigation.

[Source](lab/execution_gap.py) · [Report](reports/execution-gap/) · [Sample ledger](reports/execution-gap/input-trades.json)

## 3. Multi-Account Bot

[![Multi-account bot preview](reports/multi-account-bot/preview.png)](reports/multi-account-bot/)

A closed-candle moving-average example produces long/flat targets with close-based
stop/trailing exits. A SQLite-backed router isolates account failures, preserves order
intent through a restart, reconciles an accepted order after a lost acknowledgement,
and deduplicates repeated signals.

The seven accounts are labelled **MT5-SIM-1 through MT5-SIM-5, BINANCE-SIM, and BINGX-SIM**.
They are deliberate in-memory simulations; no broker SDK or live connection is present.

**A first milestone:** adapt a supplied indicator into a causal signal function and validate
one agreed execution path. Real venue adapters, broker-specific behavior, and deployment
are separately scoped integration work.

[Source](lab/paper_router.py) · [Report](reports/multi-account-bot/) · [Event trace](reports/multi-account-bot/results.json)

## 4. Repeated Entry + Stop Order Preview

[![Order repeat preview](reports/order-repeat/preview.png)](reports/order-repeat/)

Generate concurrent original-plus-repeat order pairs with unique preview IDs and correctly
linked stop children. Validate tick alignment, stop direction and aggregate share limits.
This is an offline plan, with no TWS connection or native UI modification.

[Source](lab/order_repeat.py) · [Report](reports/order-repeat/)

## 5. Strategy Validation Trial

[![Strategy validation preview](reports/strategy-trial/preview.png)](reports/strategy-trial/)

A small expanding-window experiment selects from four predefined lookbacks, freezes each
choice, and reports all four out-of-sample windows against a baseline and doubled-cost stress.
Inputs are synthetic; this demonstrates a reproducible validation process, not profitable alpha.

[Source](lab/strategy_trial.py) · [Report](reports/strategy-trial/)

## 6. Resumable Historical Data Collector

[![Collector preview](reports/history-collector/preview.png)](reports/history-collector/)

Collect 100 synthetic symbols, resume from a persisted checkpoint, deduplicate overlapping
pages and compare all final hashes with an uninterrupted run. Conflicts and incomplete pages
roll back without advancing the checkpoint. This is a vendor-neutral offline test, not an IBKR adapter.

[Source](lab/history_collector.py) · [Report](reports/history-collector/)

## Run all six

Python 3.12+:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py
python -m unittest -v
```

Open any `reports/*/report.html` locally for a self-contained visual report.
The GitHub report directories render the same key evidence directly in your browser.
No API keys or market-data subscriptions are required.

Customize the order-plan preview without installing dependencies:

```sh
python repeat_orders.py --repeats 4 --quantity 10 --entry 100 --stop 98
```

For analysis without rendering charts:

```sh
python run.py --no-images --output /tmp/trading-demo-results
```

To inspect your own compatible fixtures:

```sh
python inspect_data.py audit path/to/manifest-directory
python inspect_data.py execution path/to/matched-trades.json
```

The JSON fixture schemas are illustrated by the committed sample inputs.
The audit is read-only; schema adapters for other sources can be added in a scoped engagement.

## Work with me

I have 20 years of trading-systems experience, including complex C++ high-frequency work,
Python, and trading/market-data interfaces. I combine that background with AI-assisted
engineering and validate changes with concrete tests and evidence.

A focused first milestone can start at **$150**, with scope agreed after reviewing
the available materials. It delivers a defined diagnostic or a small module so that you
can evaluate the work before committing to a larger integration.

If you found this repository through an Upwork proposal, reply in that Upwork conversation
with the relevant code/log sample and the result you need. Project communication and
milestones can remain there.

## Scope

- Audit: five-minute, interval-start, regular-session OHLCV for one configured symbol.
  Stored hashes establish consistency with receipts, not independent vendor authenticity.
- Execution: supplied matched trades only; not a complete broker fill-matching engine,
  strategy optimizer, or profitability assessment.
- Bot: one symbol, one worker, long/flat, zero starting inventory. Immediate simulated
  fills at closed prices omit spread, fees, partial fills, and intrabar stop execution.
  Live MT5/crypto adapters and production readiness are not claimed.
- Order repeat: concurrent limit-entry/stop pairs for a synthetic equity; local IDs only.
  A paper-account adapter, broker ID allocation and execution lifecycle remain integration work.
- Strategy trial: synthetic single-asset long/flat returns, simple proportional costs and
  fold-boundary liquidation. No NSE/BSE data adapter or multiple-testing significance claims.
- History collector: one synthetic 390-observation session; simulated errors and retry clock.
  No live broker SDK, real data subscription or validated provider pacing.
- No client source, proprietary strategy, private account data, or credentials are included.

MIT licensed. Libraries retain their own licenses.
