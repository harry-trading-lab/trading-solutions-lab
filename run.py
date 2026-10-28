"""Generate six executable portfolio demos and their reports."""
import argparse
import json
from pathlib import Path
from lab import market_audit, execution_gap, paper_router, order_repeat, strategy_trial, history_collector


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("reports"))
    parser.add_argument("--no-images", action="store_true", help="Run evidence generation without rendering")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    audit = market_audit.run(args.output / "data-audit")
    trades = execution_gap.fixture()
    execution = execution_gap.analyze(trades)
    bot = paper_router.run()
    (args.output / "execution-gap").mkdir(exist_ok=True)
    (args.output / "execution-gap" / "input-trades.json").write_text(json.dumps(trades, indent=2) + "\n")
    orders, trial = order_repeat.plan(), strategy_trial.run()
    history = history_collector.run()
    (args.output / "strategy-trial").mkdir(exist_ok=True)
    (args.output / "strategy-trial" / "input-bars.json").write_text(json.dumps(strategy_trial.fixture(), indent=2) + "\n")
    datasets = {"data-audit": audit, "execution-gap": execution, "multi-account-bot": bot,
                "order-repeat": orders, "strategy-trial": trial, "history-collector": history}
    for name, data in datasets.items():
        directory = args.output / name
        directory.mkdir(exist_ok=True)
        (directory / "results.json").write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    if not args.no_images:
        from lab.render import all_reports
        all_reports(args.output, audit, execution, bot)
        from lab.render_extensions import reports
        reports(args.output, orders, trial)
        from lab.render_history import report
        report(args.output, history)
    print("DATA AUDIT:", audit["clean"]["decision"], "/", audit["broken"]["decision"],
          "-", audit["broken"]["finding_count"], "findings")
    print("EXECUTION GAP:", execution["totals"])
    print("MULTI-ACCOUNT:", bot["account_count"], "simulated accounts;",
          bot["duplicate_submissions"], "duplicate submissions")
    print("ORDER REPEAT:", orders["groups"], "independent pairs; offline preview only")
    print("STRATEGY TRIAL:", trial["fold_count"], "OOS windows; synthetic data")
    print("HISTORY COLLECTOR:", history["unique_bars"], "synthetic bars; restart matches clean run:", history["matches_uninterrupted_run"])
    print("Reports:", args.output.resolve())


if __name__ == "__main__":
    main()
