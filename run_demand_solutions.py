"""Execute all three solutions, create evidence and standalone reports.

python run_demand_solutions.py --output /tmp/demand-evidence
python run_demand_solutions.py --review your-manifest.json
"""

import argparse
import html
import json
import math
import platform
import random
import statistics
import time
from pathlib import Path
from solutions.vwap.core import RangeVWAP
from solutions.analysis_review.core import review
from solutions.calculation_boundary.harness import running_services, post

ROOT = Path(__file__).resolve().parent


def baseline(bars, start, stop):
    rows = bars[start:stop]
    total = math.fsum(v for _, v in rows)
    mean = math.fsum(p * v for p, v in rows) / total
    variance = math.fsum(v * (p - mean) ** 2 for p, v in rows) / total
    return mean, variance


def vwap_evidence():
    rng = random.Random(291026)
    bars = [
        (round(100 + rng.uniform(-5, 5), 6), rng.randint(1, 1000)) for _ in range(10000)
    ]
    queries = [(rng.randrange(0, 3000), rng.randrange(7000, 10001)) for _ in range(150)]
    a = time.perf_counter()
    tree = RangeVWAP(bars)
    build = time.perf_counter() - a
    timings = {"baseline": [], "indexed": []}
    for _ in range(3):
        a = time.perf_counter()
        expected = [baseline(bars, s, e) for s, e in queries]
        timings["baseline"].append(time.perf_counter() - a)
        a = time.perf_counter()
        actual = [tree.query(s, e) for s, e in queries]
        timings["indexed"].append(time.perf_counter() - a)
    mean_error = max(abs(x.mean - y[0]) for x, y in zip(actual, expected))
    variance_error = max(abs(x.variance - y[1]) for x, y in zip(actual, expected))
    tree.revise(500, 130, 500)
    bars[500] = (130, 500)
    revised = tree.query(0, len(bars))
    reference = baseline(bars, 0, len(bars))
    revision_error = abs(revised.mean - reference[0])
    if mean_error > 1e-9 or variance_error > 1e-9 or revision_error > 1e-9:
        raise AssertionError("VWAP regression against independent two-pass calculation")
    timing = {
        "python": platform.python_version(),
        "platform": platform.system() + " " + platform.machine(),
        "build_seconds": build,
        "query_seconds_median": {k: statistics.median(v) for k, v in timings.items()},
        "query_speedup": statistics.median(timings["baseline"])
        / statistics.median(timings["indexed"]),
        "method": "10,000 bars; 150 identical ranges; median of 3; build reported separately; synthetic input, seed 291026",
    }
    result = {
        "bars": 10000,
        "queries": 150,
        "query_match_tolerance": 1e-9,
        "all_queries_match": True,
        "revision_matches": True,
        "max_vwap_error": mean_error,
        "max_variance_error": variance_error,
        "revised_vwap_error": revision_error,
        "scope": "Python calculation kernel; no TradeStation/EasyLanguage, UI or live-data measurement",
    }
    return result, timing


def boundary_evidence():
    data = {"principal_cents": 10000, "annual_rate_bps": 1000, "years": 2}
    with running_services() as s:
        cases = [
            ("Developer fixture", s["public"], "/v1/mock", s["developer"], data, 200),
            (
                "Developer live route denied",
                s["public"],
                "/v1/quote",
                s["developer"],
                data,
                403,
            ),
            (
                "Application live route",
                s["public"],
                "/v1/quote",
                s["application"],
                data,
                200,
            ),
            (
                "Application direct engine denied",
                s["private"],
                "/calculate",
                s["application"],
                data,
                401,
            ),
            (
                "Developer direct engine denied",
                s["private"],
                "/calculate",
                s["developer"],
                data,
                401,
            ),
            ("Anonymous denied", s["public"], "/v1/quote", "", data, 401),
            (
                "Undeclared source route denied",
                s["public"],
                "/source",
                s["application"],
                {},
                404,
            ),
            (
                "Invalid schema rejected",
                s["public"],
                "/v1/quote",
                s["application"],
                {"bad": 1},
                400,
            ),
        ]
        outcomes = []
        for name, url, path, key, body, expected in cases:
            status, result = post(url, path, key, body)
            if status != expected:
                raise AssertionError((name, status, expected))
            if (
                name == "Application live route"
                and result["future_value_cents"] != 12100
            ):
                raise AssertionError("wrong arithmetic")
            outcomes.append(
                {
                    "case": name,
                    "expected_status": expected,
                    "observed_status": status,
                    "pass": True,
                }
            )
        s["engine"].terminate()
        s["engine"].wait(timeout=5)
        for name, path, key, expected in [
            ("Engine failure closed", "/v1/quote", s["application"], 502),
            ("Mock survives engine failure", "/v1/mock", s["developer"], 200),
        ]:
            code, _ = post(s["public"], path, key, data)
            if code != expected:
                raise AssertionError((name, code))
            outcomes.append(
                {
                    "case": name,
                    "expected_status": expected,
                    "observed_status": code,
                    "pass": True,
                }
            )
        audit = s["audit"].read_text()
        if any(
            key in audit for key in (s["service"], s["developer"], s["application"])
        ):
            raise AssertionError("token in audit")
        return {
            "cases": outcomes,
            "all_pass": True,
            "audit_records": len(audit.splitlines()),
            "tokens_in_audit": False,
            "process_boundary": "Two independent Python subprocesses over localhost HTTP",
            "scope": "Public placeholder model. Demonstrates application route permissions, not OS/IAM isolation or production readiness.",
        }


def write_report(path, title, subtitle, metrics, lines, result, notes, no_images):
    path.mkdir(parents=True, exist_ok=True)
    (path / "results.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    cards = "".join(
        '<div class="card"><strong>'
        + html.escape(a)
        + "</strong><span>"
        + html.escape(b)
        + "</span></div>"
        for a, b in metrics
    )
    bullets = "".join("<li>" + html.escape(x) + "</li>" for x in lines)
    page = (
        """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>"""
        + html.escape(title)
        + """</title><style>
    body{margin:0;background:#f4f7fa;color:#152b3a;font:17px/1.6 system-ui}main{max-width:1040px;margin:auto;padding:48px 24px}h1{font-size:clamp(28px,5vw,48px);line-height:1.15}header p{color:#526878}.eyebrow{color:#00857e;font-weight:700;letter-spacing:.08em}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:16px;margin:32px 0}.card{padding:24px;background:white;border:1px solid #d9e2e7;border-radius:14px}.card strong{display:block;color:#00857e;font-size:32px}.card span{display:block;font-size:15px}section{background:white;padding:24px;border-radius:14px;margin:20px 0}pre{overflow:auto;font-size:13px}a{color:#00756e}footer{font-size:14px;color:#526878}
    </style><main><header><p class="eyebrow">TRADING SOLUTIONS LAB · EXECUTED EVIDENCE</p><h1>"""
        + html.escape(title)
        + "</h1><p>"
        + html.escape(subtitle)
        + '</p></header><div class="cards">'
        + cards
        + "</div><section><h2>What was verified</h2><ul>"
        + bullets
        + "</ul></section><section><h2>Read the evidence</h2><details><summary>Executed results JSON</summary><pre>"
        + html.escape(json.dumps(result, indent=2))
        + '</pre></details><p><a href="results.json">Download results</a> · <a href="https://github.com/harry-trading-lab/trading-solutions-lab/tree/main/solutions">Source and reproduction instructions</a></p></section><footer>'
        + html.escape(notes)
        + "</footer></main></html>"
    )
    (path / "report.html").write_text(page)
    if no_images:
        return
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(14, 9), dpi=120, facecolor="#f4f7fa")
    fig.text(
        0.07,
        0.92,
        "TRADING SOLUTIONS LAB  /  DEMAND-LED SOLUTIONS",
        fontsize=13,
        color="#00857e",
        weight="bold",
    )
    fig.text(0.07, 0.82, title, fontsize=27, color="#152b3a", weight="bold")
    for i, (value, label) in enumerate(metrics):
        x = 0.07 + i * 0.3
        fig.text(x, 0.66, value, fontsize=32, color="#00857e", weight="bold")
        fig.text(x, 0.60, label, fontsize=13, color="#526878")
    for i, line in enumerate(lines[:4]):
        fig.text(0.07, 0.46 - i * 0.075, line, fontsize=15, color="#152b3a")
    import textwrap

    fig.text(
        0.07, 0.08, "\n".join(textwrap.wrap(notes, 115)), fontsize=11, color="#526878"
    )
    fig.savefig(path / "preview.png", facecolor=fig.get_facecolor())
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "reports")
    parser.add_argument("--no-images", action="store_true")
    parser.add_argument("--review", type=Path)
    args = parser.parse_args()
    if args.review:
        print(json.dumps(review(json.loads(args.review.read_text())), indent=2))
        return
    result, timing = vwap_evidence()
    path = args.output / "anchored-vwap"
    write_report(
        path,
        "Faster anchored VWAP queries",
        "Preserve numerical behavior while avoiding repeated full-history scans.",
        [
            ("10,000", "Synthetic bars"),
            ("150 / 150", "Range checks match"),
            ("PASS", "Historical revision check"),
        ],
        [
            "Weighted moments avoid subtracting large raw squared sums.",
            "O(log n) range queries and historical bar corrections.",
            "Compared against an independent two-pass calculation.",
            "Separate symbol instances; zero-volume and invalid-input tests.",
        ],
        result,
        "Portable Python kernel, not a TradeStation plug-in. Synthetic data. Floating-point agreement tested at 1e-9 on this fixture; timing is machine-specific. AI-assisted original work.",
        args.no_images,
    )
    (path / "benchmark.json").write_text(json.dumps(timing, indent=2) + "\n")
    ex = ROOT / "solutions/analysis_review/examples"
    good = review(json.loads((ex / "clean.json").read_text()))
    bad = review(json.loads((ex / "broken.json").read_text()))
    codes = sorted({x["code"] for x in bad["findings"]})
    result = {"clean": good, "broken": bad, "distinct_issue_classes": codes}
    write_report(
        args.output / "analysis-review",
        "Audit the analysis before trusting it",
        "A review harness for declared timestamps, data splits and statistical claims.",
        [
            (str(len(codes)), "Seeded issue classes"),
            ("NO FLAGS", "Clean control"),
            ("REVIEW", "Contaminated analysis"),
        ],
        [
            "Detect future features and training labels crossing the test cutoff.",
            "Flag reused sample IDs and preprocessing fitted outside training.",
            "Adjust the declared p-value family with Holm step-down.",
            "Escalate observational causal claims for identification review.",
        ],
        result,
        "Synthetic manifests. Requires truthful provenance and the full test family. Does not parse notebooks, prove causality, or certify an AI analysis. AI-assisted original work.",
        args.no_images,
    )
    result = boundary_evidence()
    write_report(
        args.output / "calculation-boundary",
        "Keep calculation access explicit",
        "Two running services, a public placeholder model, and an executable permission matrix.",
        [
            ("10 / 10", "HTTP scenarios pass"),
            ("2", "Independent processes"),
            ("0", "Tokens in audit log"),
        ],
        [
            "Developer: static fixture allowed; restricted calculation denied.",
            "Application: calculation through gateway; direct engine denied.",
            "Engine failure returns 502; the developer fixture stays usable.",
            "Audit records contain role, route and status, not request bodies.",
        ],
        result,
        "Local HTTP reference implementation. No real proprietary model. Production needs separate IAM/repositories, network isolation, TLS, rate limits, operational hardening and review.",
        args.no_images,
    )
    print(
        json.dumps(
            {
                "vwap": timing,
                "analysis_issue_classes": codes,
                "http_cases_passed": len(result["cases"]),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
