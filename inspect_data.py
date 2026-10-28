"""Read a compatible data fixture and print a JSON diagnostic."""
import argparse
import json
from pathlib import Path
from lab.market_audit import audit
from lab.execution_gap import analyze

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("kind", choices=["audit", "execution"])
parser.add_argument("path", type=Path)
args = parser.parse_args()
result = audit(args.path) if args.kind == "audit" else analyze(json.loads(args.path.read_text()))
print(json.dumps(result, indent=2, allow_nan=False))
