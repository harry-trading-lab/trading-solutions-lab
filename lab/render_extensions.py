"""Render customer-facing evidence using the existing report design."""
from .render import figure, finish, write_bundle, table, INK, TEAL, ORANGE


def order_image(r, path):
    fig = figure("Repeat an order. Preserve every stop link.", "04  ORDER PLAN PREVIEW", [
        (r["additional_repeats"], "Additional copies requested"),
        (r["groups"], "Original + copies"),
        (r["order_count"], "Preview orders"),
        (r["total_entry_shares"], "Aggregate entry shares")])
    ax = fig.add_axes([.08, .18, .84, .39])
    for i in range(r["groups"]):
        parent, child = r["orders"][i*2:i*2+2]
        y = r["groups"]-i
        ax.text(.03, y, f"Group {i+1}", va="center", fontsize=12, color=INK)
        ax.text(.24, y, f"{parent['orderId']}  {parent['action']} {parent['totalQuantity']} @ {parent['lmtPrice']}",
                va="center", fontsize=12, color=TEAL)
        ax.annotate("", xy=(.60,y), xytext=(.52,y), arrowprops=dict(arrowstyle="->", color=INK))
        ax.text(.63, y, f"{child['orderId']}  STOP @ {child['auxPrice']}", va="center", fontsize=12, color=ORANGE)
    ax.set_xlim(0,1)
    ax.set_ylim(.3,r["groups"]+.7)
    ax.set_axis_off()
    fig.text(.08,.125,"OFFLINE ONLY  /  All transmit=False  /  Stops reference their own parent", fontsize=11,color=INK)
    finish(fig,ax,path)


def research_image(r, path):
    fig = figure("A strategy trial with untouched test windows.", "05  STRATEGY VALIDATION", [
        (len(r["candidates"]), "Predeclared lookbacks"),
        (r["fold_count"], "Out-of-sample windows"),
        (r["out_of_sample_observations"], "Test observations"),
        ("5 / 10 bps", "Base / stressed turnover costs")])
    ax = fig.add_axes([.08,.18,.84,.40])
    ax.plot(r["curve"], color=TEAL,label="Training-selected strategy, net",linewidth=2)
    ax.plot(r["benchmark_curve"], color=ORANGE,label="Buy-and-hold within each window, net",linewidth=2)
    for x in (60,120,180):
        ax.axvline(x,color=INK,alpha=.15,linestyle="--")
    ax.axhline(1,color=INK,alpha=.2)
    ax.set_xlabel("Out-of-sample observation (synthetic data)")
    ax.set_ylabel("Growth of 1.00")
    ax.legend(frameon=False,fontsize=10)
    fig.text(.08,.105,"All windows shown, including losses. This demonstrates a process, not a profitable strategy.",fontsize=10,color=INK)
    finish(fig,ax,path)


def reports(root, orders, trial):
    details = "## Preview result\n\n" + table(
        ["ID", "Type", "Side", "Shares", "Price", "Parent", "Transmit"],
        [[o["orderId"],o["orderType"],o["action"],o["totalQuantity"],o.get("lmtPrice",o.get("auxPrice")),
          o["parentId"],o["transmit"]] for o in orders["orders"]])
    details += "\n\n## Try a different input\n\n```sh\npython repeat_orders.py --repeats 2 --quantity 5 --entry 100 --stop 98\n```"
    details += "\n\n## First milestone\n\nAgree whether copies are concurrent or sequential and whether an external helper is acceptable. "
    details += "Then adapt one agreed order type to the client's paper account and verify parent/child status and cancellation. "
    details += "This preview is concurrent only and does not modify TWS itself."
    details += "\n\n## Integration checklist\n\nQualify the contract and tick size; allocate broker-valid order IDs; "
    details += "agree the transmit sequence; reconcile acknowledgements, partial fills and cancellations in paper trading. "
    details += "The preview uses synthetic local IDs and all orders remain transmit=False."
    details += "\n\n## Official API reference\n\n[IBKR Campus: complex orders](https://www.interactivebrokers.com/campus/trading-lessons/python-complex-orders/). "
    details += "The demo follows the documented parentId/attached-order concept; no real SDK connection has been exercised."
    details += "\n\n## Scope\n\n" + orders["scope"]
    write_bundle(root,"order-repeat","Repeated Entry + Stop Order Preview",
        "A runnable offline example converts four additional repeats into five independent entry/stop pairs. "
        "It validates stop direction, tick alignment and aggregate share limits before producing the plan.", orders,details,order_image)
    details = "## Every out-of-sample window\n\n" + table(
        ["Test indices", "Chosen lookback", "Net return", "Benchmark", "10 bps stress", "Max drawdown"],
        [[f"{f['test_start']}–{f['test_end_exclusive']-1}",f["selected_lookback"],
          f"{f['test']['net_return']:.2%}",f"{f['benchmark']['net_return']:.2%}",
          f"{f['double_cost_net_return']:.2%}",f"{f['test']['max_drawdown']:.2%}"] for f in trial["folds"]])
    details += "\n\n## Method\n\nFour SMA lookbacks (5, 10, 20, 40) are declared before the experiment. "
    details += "Each expanding training window selects by net return, with deterministic ties. Parameters freeze for the next 60 observations. "
    details += "The final training mark precedes the test entry by one observation. "
    details += "Features use previous closes and the return proxy uses the next open-to-open interval. "
    details += "Every fold starts flat, charges turnover plus final liquidation, and reports an equally reset buy-and-hold comparator. "
    details += "JSON includes every candidate training score and every test return. The supplied input-bars.json is synthetic and reproducible."
    details += "\n\n## First milestone\n\nReplace the synthetic fixture with one agreed licensed dataset and test one supplied strategy against a baseline. "
    details += "Deliver reproducible code, an experiment log, all fold results and a recommendation to reject, investigate or extend. "
    details += "NSE/BSE delivery additionally needs point-in-time universe/corporate actions, trading calendars, market-specific costs and data rights. "
    details += "Those are not implemented here. Multiple-testing significance and large strategy searches require a separate validation design."
    details += "\n\n## Scope\n\n" + trial["scope"]
    write_bundle(root,"strategy-trial","Small Strategy Validation Trial",
        "An executable research process: choose parameters using past data, freeze them, and report every out-of-sample result "
        "with a baseline and doubled-cost stress. Synthetic data demonstrates the pipeline; no investment performance is claimed.",
        trial,details,research_image)
