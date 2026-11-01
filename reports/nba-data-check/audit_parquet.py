"""Read-only inspection of a game-state Parquet output and raw game inventory."""
import argparse
import json
from pathlib import Path
import pandas as pd


def audit(processed, raw_dir):
    df = pd.read_parquet(processed)
    required = ["game_id", "quarter", "time_remaining_seconds", "home_score", "away_score"]
    missing = [c for c in required if c not in df]
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing))
    if df.empty:
        raise ValueError("Processed output is empty")
    raw_ids = {p.stem for p in Path(raw_dir).glob("*.parquet")}
    if not raw_ids:
        raise ValueError("Raw inventory contains no Parquet files")
    ids = set(df.game_id.dropna().astype(str))
    return {"rows": len(df), "processed_games": len(ids), "raw_files": len(raw_ids),
            "core_field_null_counts": {c: int(df[c].isna().sum()) for c in required},
            "raw_ids_absent_from_processed": len(raw_ids - ids),
            "processed_ids_absent_from_raw": len(ids - raw_ids),
            "scope": "Cache inventory comparison; not source completeness or semantic correctness."}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.processed, args.raw_dir), indent=2))
