# Reusable solutions from public customer problems

Three original, AI-assisted reference implementations answer concrete engineering
questions found in public job descriptions. They are independent portfolio work:
no client engagement, endorsement, confidential attachment or client source is implied.
All examples are MIT licensed under the repository license.

| Customer problem | Reusable implementation | Executed report |
|---|---|---|
| Existing multi-anchor VWAP recalculates too much history | Range weighted-moment tree, point revisions, numeric reference checks | [VWAP](../reports/anchored-vwap/) |
| App developers need an integration contract without live calculation access | Separate HTTP gateway and engine; development fixture; permission matrix | [Calculation boundary](../reports/calculation-boundary/) |
| AI-written analysis may leak data or overstate evidence | Manifest review, temporal/split checks, preprocessing provenance, Holm adjustment | [Analysis review](../reports/analysis-review/) |

## Run

Python 3.12+; the implementations and tests use the standard library. The report
PNG renderer uses matplotlib from the existing pinned requirements file.

```sh
python -m unittest test_demand_solutions -v
python run_demand_solutions.py --no-images --output /tmp/solutions-evidence
# With repository requirements installed, also generate PNG previews:
python run_demand_solutions.py
# Review a manifest you supply, without running any submitted code:
python run_demand_solutions.py --review solutions/analysis_review/examples/broken.json
```

The service tests bind only ephemeral localhost ports, generate ephemeral random
credentials, run two subprocesses and stop those processes after each run. They
make no external API calls and place no trades. The subprocess harness targets
Linux/macOS (`select` on pipes); portable calculation/review modules also work on Windows.

## Design

Each problem has a small independently importable core. Reports are generated from
executed evidence rather than hand-entered outcome numbers. Tests include clean
controls, adversarial inputs and independent arithmetic references. Existing
`lab/` demos remain separate; no new universal trading framework is imposed.

- VWAP: `RangeVWAP.query(start, stop)` uses half-open ranges. Weighted population
  standard deviation is over the provided bar-price series; select the same price
  definition and variance convention as the target indicator before integration.
  The fixed-size tree builds in O(n), uses O(n) memory, queries/revises in O(log n).
  Build one per symbol; rebuild on append/resize. Sorting, session mapping, UI
  events, click anchors, RadarScreen and persistence are adapter responsibilities.
- Analysis review: callers supply row identities, decision/availability/label
  timestamps, preprocessing fit IDs, the complete p-value family and claim design.
  Label overlap at the test boundary is conservatively flagged. A passing control
  means no flags in these declared checks, not a validated trading strategy or
  correct causal analysis. Incomplete provenance cannot be reconstructed here.
- Calculation boundary: the gateway has no import dependency on engine code;
  the engine's formula is a deliberately public, deterministic compound-growth
  placeholder with integer cents and Decimal rounding. The developer credential
  has only a static fixture route; an application credential permits live queries;
  only the gateway service credential works on the engine. Logs omit inputs and
  credentials. Read [deployment boundaries](calculation_boundary/README.md).

## Public demand references

Accessed 2026-10-29. Links explain the originating problem, not completed client work.

- [TradeStation indicator performance](https://www.upwork.com/jobs/~022113675224940119302/):
  repeated multi-anchor calculations and symbol-switch latency. This solution
  benchmarks only a portable Python kernel, not the customer's EasyLanguage code.
- [Financial application architecture](https://www.upwork.com/jobs/~022115694302395273974/):
  a restricted calculation service with a developer integration contract.
- [AI analysis evaluation](https://www.upwork.com/jobs/~022115562969253150405/):
  statistical reasoning, leakage and unsupported analytical claims.

## First paid delivery

These public implementations let a client inspect the method before buying a
bounded integration: map one sanitized dataset/code path, reproduce one issue,
agree on the acceptance checks, and deliver the adapted module and evidence.
Production integration and maintenance are separately scoped. No performance,
profitability, security-certification or hiring outcome is promised.
