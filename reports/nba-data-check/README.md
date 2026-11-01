# NBA play-by-play: inspect the output, not just the architecture

![Actual cached-data recheck](preview.png)

On 2026-10-31 I rechecked an existing personal project's 2024–25 NBA cache.
This is a read-only inspection of saved data, not a fresh download or a complete-season claim.

| Observed result | Value |
|---|---:|
| Processed game-state rows | 69,344 |
| Distinct processed games | 595 |
| Raw per-game Parquet files | 721 |
| Raw game IDs absent from processed output | 126 |
| Processed game IDs absent from the raw cache | 0 |
| Null values in the five checked core fields | 0 |

**The useful finding:** a schema check passes while coverage is incomplete relative to the raw cache. Checking only row format would miss 126 unrepresented games. Their cause has not been diagnosed in this audit.

## What I built in the underlying personal project

NBA V2/V3 feeds are collected into per-game raw Parquet files, then parsed into game-state records with clocks, scores and team identifiers. The existing collector logs failures and skips raw files already on disk. A file-existence check is not a completeness check.

## Inspect the evidence

[Timestamped results, file hash and five output rows](results.json) · [Standalone read-only audit](audit_parquet.py)

The public audit is a new, small utility for inspecting an equivalent local Parquet file and raw directory. The private collection/parsing code and model features are not published.

```sh
python -m pip install pandas pyarrow
python reports/nba-data-check/audit_parquet.py --processed /path/to/game_states.parquet --raw-dir /path/to/raw/season
```

It prints JSON and never modifies the inputs. Supply your own files; the underlying vendor dataset is not redistributed. The report includes a small output excerpt and aggregate checks only.

## A bounded client engagement

Provide a sanitized output sample, source inventory and expected schema. I can inspect missing records, schema mismatches and failed collection steps, then deliver findings and an agreed repair. Acceptance needs an explicit coverage target; this audit does not establish source completeness, team-label correctness or a production SLA.
