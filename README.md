# Python data pipelines, API integrations and workflow repair

I help with a failing data job, an API that needs connecting, or records that do not reconcile. Start with one defined problem and agree the output and acceptance checks.

## Start with the evidence

| Your problem | Evidence to inspect | What it establishes |
|---|---|---|
| A pipeline leaves raw files out of its output | [NBA cache recovery](reports/nba-data-check/) | 126 absent games investigated; separate replay accepts 714 of 721 games and routes 7 to review, recovering 119 into the accepted set |
| A broker API needs an order workflow | [Sandbox order evidence](reports/sandbox-api/) | Recorded submit, query, cancel and final-state checks against three vendor sandbox APIs |
| Missing or conflicting records need locating | [Market data audit](reports/data-audit/) | Eight deliberately seeded issue classes located; clean synthetic control passes |

[![Tests](https://github.com/harry-trading-lab/trading-solutions-lab/actions/workflows/tests.yml/badge.svg)](https://github.com/harry-trading-lab/trading-solutions-lab/actions/workflows/tests.yml)

The NBA replay uses an existing personal cache and writes a separate score-state output. Seven games still need review; the historical omission of 118 games remains unexplained. The broker checks use simulated funds on real sandbox endpoints. The data-audit fixtures are synthetic. Each case states its scope and limitations.

## Work I take on

- Diagnose and repair Python scripts and data pipelines.
- Connect one data feed or API to a database, file output or existing application.
- Run an agreed periodic refresh with data checks and exception reporting.
- Implement or debug a defined broker interface or C++ component.

I bring 20 years of trading-technology experience with Python and C++, plus data engineering, machine learning and a PhD in condensed matter physics. I use AI development tools with engineering review and testing. Public code and demos are not presented as confidential client deliveries.

## A useful first milestone

Send the failing step, expected output and a sanitized log or sample through our Upwork conversation. I will propose a bounded deliverable and acceptance checks.

A diagnostic can start at **$150** after reviewing the materials: one supplied script or dataset, a reproducible finding where possible, an evidence summary and recommended next steps. It does not include an open-ended fix, deployment or ongoing support. Implementation and recurring operation are scoped separately.

## Run the public demonstrations

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py
python -m unittest -v
```

For the standalone NBA output audit, see its [run instructions](reports/nba-data-check/). Supply your own Parquet files; the private data and collection code are not redistributed.

## Additional engineering experiments

[Demo catalog, technical detail and limits](EXPERIMENTS.md) · [Additional reference solutions](solutions/README.md)

Those experiments include synthetic execution diagnostics, restart handling and research-method demonstrations. They are supporting technical work, not an offer to develop profitable trading strategies. No investment-return guarantee is offered.

MIT licensed for the public source. Dependencies retain their own licenses.
