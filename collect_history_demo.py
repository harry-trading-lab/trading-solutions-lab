"""Execute the offline history-collection experiment without third-party packages."""
import argparse
import json
from pathlib import Path
from lab.history_collector import run

if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,default=Path("reports/history-collector"))
    args=p.parse_args()
    result=run()
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/"results.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(result["unique_bars"],"synthetic observations; clean-run match:",result["matches_uninterrupted_run"])
