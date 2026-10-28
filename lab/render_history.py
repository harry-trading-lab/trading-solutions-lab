"""Visual evidence for the synthetic resumable collector."""
from .render import figure, finish, write_bundle, table, TEAL, ORANGE, INK


def preview(r,path):
    fig=figure("Resume the download. Keep the data consistent.", "06  HISTORICAL DATA COLLECTION",[
        (r["symbol_count"],"Synthetic symbols"),(f"{r['unique_bars']:,}","Unique one-minute observations"),
        (r["overlap_rows_deduplicated"],"Overlapping rows deduplicated"),
        (r["completed_rerun_requests"],"Requests on completed rerun")])
    ax=fig.add_axes([.10,.26,.82,.27])
    before=r["bars_before_restart"]
    ax.barh([0],[before],color=ORANGE,label="Persisted before interruption",height=.45)
    ax.barh([0],[r["unique_bars"]-before],left=[before],color=TEAL,label="Collected after reopening SQLite",height=.45)
    ax.set_xlim(0,40000)
    ax.set_yticks([])
    ax.set_xlabel("Persisted unique observations",color=INK)
    ax.legend(loc="upper center",bbox_to_anchor=(.5,1.4),ncol=2,frameon=False,fontsize=10)
    fig.text(.10,.16,f"{r['pages_before_restart']} pages before restart + {r['pages_after_restart']} after restart = 400 completed pages",fontsize=12,color=INK)
    fig.text(.10,.115,"Every final symbol hash matches an independent uninterrupted run.",fontsize=12,color=INK)
    finish(fig,ax,path)


def report(root,r):
    details="## Executed checks\n\n"+table(["Check","Result"],[
        ["Unique observations",r["unique_bars"]],["Symbols",r["symbol_count"]],
        ["Committed pages before / after restart",f"{r['pages_before_restart']} / {r['pages_after_restart']}"],
        ["Boundary duplicates removed",r["overlap_rows_deduplicated"]],
        ["Injected transient errors",str(r["retry_errors"])],
        ["Recorded retry waits (simulated seconds)",r["simulated_wait_seconds"]],
        ["Requests when rerun after completion",r["completed_rerun_requests"]],
        ["Matches independent clean-run hashes",r["matches_uninterrupted_run"]]])
    details+="\n\n## Try it\n\n```sh\npython collect_history_demo.py --output /tmp/history-demo\npython -m unittest test_history_collector -v\n```\n\nOnly Python standard-library modules are needed for the collector. "
    details+="The CLI writes a result JSON containing 100 symbol manifests and sample observations; no external data is downloaded."
    details+="\n\n## What is demonstrated\n\nAn atomic SQLite transaction stores a page and advances its checkpoint together. "
    details+="Matching duplicates are ignored; conflicting values or gaps roll back the entire page. "
    details+="A bounded retry loop respects the injected retry-after value. After 23 successful pages, the database connection "
    details+="is closed and reopened; completed work is not requested again. Tests also exercise persistent errors, cursor loops and conflict rollback."
    details+="\n\n## First paid module\n\nAdapt one licensed data source for an agreed symbol list, interval and time range; "
    details+="deliver a restartable collector, machine-readable output and a completeness report. "
    details+="Broker contract resolution, permissions, historical-data duration limits, pacing and calendars are adapter work. "
    details+="The existing [data audit](../data-audit/) illustrates complementary checks on five-minute data; "
    details+="its input schema differs, so these two demos are not yet an integrated production pipeline."
    details+="\n\n## Demand and attribution\n\nAn independent original demonstration inspired by the public task category "
    details+="of collecting one-minute history for approximately 100 symbols. A corresponding historical contract and review are visible "
    details+="in [this public work history](https://www.upwork.com/freelancers/~011d14bd8974209306). "
    details+="That contract belongs to another freelancer. No client code, data or work product was used. "
    details+="Actual earnings are private; this demonstration makes no historical sales claim."
    details+="\n\n## Platform reference\n\n[IBKR historical-data documentation](https://www.interactivebrokers.com/docs/tws-api/doc/md/introduction). "
    details+="The synthetic provider's cursor and HTTP-like errors are not the TWS callback protocol."
    details+="\n\n## Scope\n\n"+r["scope"]
    write_bundle(root,"history-collector","Resumable Historical Data Collector",
        "Collect 39,000 synthetic observations across 100 symbols, resume after interruption, remove page overlap "
        "and verify every output against an uninterrupted control run. An original offline portfolio example.",r,details,preview)
