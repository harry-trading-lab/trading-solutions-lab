"""Preview concurrent entry/stop copies offline. Never sends an order."""
import argparse
import json
from lab.order_repeat import plan

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--side", choices=["BUY", "SELL"], default="BUY")
    p.add_argument("--quantity", type=int, default=10)
    p.add_argument("--entry", default="100.00")
    p.add_argument("--stop", default="98.00")
    p.add_argument("--repeats", type=int, default=4, help="ADDITIONAL copies after original")
    p.add_argument("--max-shares", type=int, default=100)
    args = p.parse_args()
    try:
        print(json.dumps(plan(**vars(args)), indent=2, allow_nan=False))
    except ValueError as exc:
        p.error(str(exc))
