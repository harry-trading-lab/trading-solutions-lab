"""Create reviewable reports and GitHub preview images from actual demo output."""
import base64
from html import escape
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

INK, MUTED, TEAL, ORANGE, BG = "#142636", "#5d6e7b", "#007d73", "#c27428", "#f5f7fa"


def figure(title, kicker, metrics):
    fig = plt.figure(figsize=(14, 8), facecolor=BG)
    fig.text(.065, .935, "TRADING SOLUTIONS LAB  /  " + kicker, fontsize=11, color=TEAL, weight="bold")
    fig.text(.065, .855, title, fontsize=28, color=INK, weight="bold")
    for index, (value, label) in enumerate(metrics):
        x = .065 + index * .235
        fig.text(x, .735, str(value), fontsize=29, color=TEAL, weight="bold")
        fig.text(x, .69, label, fontsize=11, color=MUTED)
    fig.text(.065, .045, "SYNTHETIC INPUTS  •  Executed Python demo  •  Source + tests included",
             fontsize=10, color=MUTED)
    return fig


def finish(fig, ax, path):
    ax.set_facecolor(BG)
    ax.tick_params(colors=MUTED, labelsize=10, length=0, pad=8)
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.savefig(path, dpi=150, facecolor=BG)
    plt.close(fig)


def audit_image(result, path):
    data = result["broken"]
    fig = figure("Can your market data be trusted?", "01  DATA AUDIT", [
        (data["expected_bars"], "Expected five-minute bars"),
        (len(data["finding_counts"]), "Seeded issue classes detected"),
        ("PASS", "Clean control dataset"),
        ("HOLD", "Corrupted dataset")])
    ax = fig.add_axes([.24, .155, .65, .43])
    labels = [key.replace("_", " ").title() for key in data["finding_counts"]]
    ax.barh(labels[::-1], list(data["finding_counts"].values())[::-1], color=ORANGE, height=.56)
    ax.set_xlim(0, 1.4)
    ax.set_xticks([0, 1], ["0", "1 finding"])
    ax.grid(axis="x", alpha=.12)
    finish(fig, ax, path)


def execution_image(result, path):
    totals = result["totals"]
    fig = figure("Where did the backtest P&L go?", "02  EXECUTION DIAGNOSTIC", [
        (f"${totals['theoretical']:,.0f}", "Theoretical P&L"),
        (f"${totals['net']:,.0f}", "Fill-based net P&L"),
        (f"${totals['residual']:,.0f}", "Unexplained arithmetic residual"),
        (result["causality_flags"], "Future-feature flag")])
    ax = fig.add_axes([.075, .16, .86, .43])
    values = [totals["theoretical"], totals["timing"], totals["execution"], -totals["fees"], totals["net"]]
    labels = ["Theoretical", "Timing", "Execution", "Fees", "Fill-based net"]
    level = 0
    for index, value in enumerate(values):
        if index in (0, 4):
            bottom, height = 0, value
        else:
            bottom, height = level + value, -value
        ax.bar(index, height, bottom=bottom, width=.62, color=TEAL if index in (0, 4) else ORANGE)
        ax.text(index, bottom + height + 17, f"${value:,.0f}", ha="center", color=INK, fontsize=12)
        level = value if index in (0, 4) else level + value
    ax.set_xticks(range(5), labels)
    ax.set_ylim(0, max(values) * 1.18)
    ax.set_ylabel("USD · synthetic matched trades", color=MUTED)
    ax.grid(axis="y", alpha=.12)
    finish(fig, ax, path)


def bot_image(result, path):
    fig = figure("One signal. Independent account execution.", "03  MULTI-ACCOUNT BOT", [
        (result["account_count"], "Configured simulated accounts"),
        (result["duplicate_submissions"], "Duplicate order submissions"),
        (result["event_counts"].get("RECOVERED", 0), "Lost-ack recovery"),
        (result["process_restarts"], "Router restart")])
    ax = fig.add_axes([.20, .155, .68, .43])
    accounts = result["accounts"][::-1]
    ax.barh([a["account"] for a in accounts], [a["submissions"] for a in accounts],
            color=[TEAL if a["enabled"] else MUTED for a in accounts], height=.55)
    for index, account in enumerate(accounts):
        label = str(account["submissions"]) + " submits" if account["enabled"] else "Disabled"
        ax.text(account["submissions"] + .15, index, label, va="center", color=INK, fontsize=11)
    ax.set_xlim(0, max(a["submissions"] for a in accounts) + 2)
    ax.set_xlabel("Simulated orders; every account reconciles to its durable ledger", color=MUTED, labelpad=12)
    ax.grid(axis="x", alpha=.12)
    finish(fig, ax, path)


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |",
                       "| " + " | ".join("---" for _ in headers) + " |"] +
                      ["| " + " | ".join(str(v).replace("|", "/") for v in row) + " |" for row in rows])


def write_bundle(root, key, title, intro, result, details, renderer):
    folder = root / key
    folder.mkdir(parents=True, exist_ok=True)
    json_path = folder / "results.json"
    json_path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    png = folder / "preview.png"
    renderer(result, png)
    markdown = f"# {title}\n\n{intro}\n\n![Executed demo preview](preview.png)\n\n{details}\n\n"
    markdown += "[Machine-readable results](results.json) · [Source and run instructions](../../README.md)\n"
    (folder / "README.md").write_text(markdown)
    # Standalone report, with the executed plot embedded for easy local sharing.
    image = base64.b64encode(png.read_bytes()).decode()
    html = f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title>
<style>body{{margin:0;background:#f5f7fa;color:#142636;font:16px/1.6 system-ui,sans-serif}}
main{{max-width:1100px;margin:40px auto;padding:0 24px}}h1{{font-size:36px;line-height:1.2}}
p{{max-width:850px}}img{{width:100%;border:1px solid #dbe3e8;border-radius:18px}}
pre{{white-space:pre-wrap;background:white;padding:24px;border-radius:16px;font:13px/1.7 monospace;overflow-wrap:anywhere}}
a{{color:#007d73}}</style><main><p>TRADING SOLUTIONS LAB · EXECUTED DEMONSTRATION</p>
<h1>{escape(title)}</h1><p>{escape(intro)}</p><img alt="Executed results" src="data:image/png;base64,{image}">
<h2>Evidence and interpretation</h2><pre>{escape(details)}</pre>
<p>Synthetic inputs; scope and limitations are stated in the repository.
<a href="https://github.com/harry-trading-lab/trading-solutions-lab">View source, tests and engagement options</a></p></main></html>"""
    (folder / "report.html").write_text(html)


def all_reports(root, audit, execution, bot):
    audit_details = "## Findings on the intentionally corrupted fixture\n\n"
    audit_details += table(["Finding", "Source", "Evidence"], [
        [f["code"], f["source"], f["detail"]] for f in audit["broken"]["findings"]])
    audit_details += "\n\n## Calendar cross-check\n\n" + table(["Date", "Expected bars", "Open UTC"], [
        [day, values["bars"], values["open_utc"] or "Closed"] for day, values in audit["clean"]["sessions"].items()])
    audit_details += "\n\n## Scope\n\n" + audit["broken"]["scope"]
    audit_details += "\n\nBoth input fixtures and their receipt manifests are in fixtures/. Original input bytes remain unchanged during audit."
    write_bundle(root, "data-audit", "Market Data Integrity Audit",
                 "A read-only audit detects eight seeded defect classes and preserves the original data. The clean control passes.",
                 audit, audit_details, audit_image)
    execution_details = "## Exact P&L decomposition\n\n" + table(
        ["Trade", "Side", "Theoretical", "Timing", "Execution", "Fees", "Net", "Residual"],
        [[t[k] for k in ["trade_id", "side", "theoretical", "timing", "execution", "fees", "net", "residual"]]
         for t in execution["trades"]])
    execution_details += "\n\n## Causality checks\n\n" + table(["Trade", "Finding"], [
        [t["trade_id"], ", ".join(t["findings"])] for t in execution["trades"] if t["findings"]])
    execution_details += "\n\n## Scope\n\n" + execution["scope"]
    execution_details += "\n\nTiming is the mid-price move between signal and fill. Execution is the fill-versus-contemporaneous-mid difference; it includes spread/impact and does not distinguish them without richer data. Input ledger: input-trades.json."
    write_bundle(root, "execution-gap", "Backtest-to-Fill Diagnostic",
                 "Reconcile theoretical and observed trade P&L, attribute the difference, and flag future-dated features. Every number below comes from the included synthetic ledger.",
                 execution, execution_details, execution_image)
    bot_details = "## Account results\n\n" + table(
        ["Account", "Enabled", "Submissions", "Unique order IDs", "Position", "Ledger"],
        [[a[k] for k in ["account", "enabled", "submissions", "distinct_order_ids", "position", "ledger_position"]]
         for a in bot["accounts"]])
    bot_details += "\n\n## Exercised events\n\n" + table(["Event", "Count"], sorted(bot["event_counts"].items()))
    bot_details += "\n\n## Scope\n\n" + bot["scope"]
    bot_details += "\n\nOne account is disabled, one disconnects and reconnects, one acknowledgement is lost, and one order is rejected. The SQLite-backed router is restarted during the replay. Stops and trailing exits use closed prices, not intrabar execution."
    write_bundle(root, "multi-account-bot", "Multi-Account Signal Execution",
                 "A closed-candle example strategy routes long/flat targets to seven simulated accounts. Failures remain isolated and order intent survives a router restart.",
                 bot, bot_details, bot_image)
