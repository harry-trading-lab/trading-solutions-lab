"""Run real sandbox API checks; private credential file must be outside this repo."""
import argparse
import json
from pathlib import Path
from lab.sandbox_api import AlpacaPaper, TastytradeSandbox, OandaPractice, APIError, timestamp


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    clients = {"tastytrade": TastytradeSandbox, "alpaca": AlpacaPaper, "oanda": OandaPractice}
    parser.add_argument("venue", choices=clients)
    parser.add_argument("--credentials", required=True, type=Path)
    parser.add_argument("--exercise-orders", action="store_true", help="Submit and cancel one simulated order")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    credential_path = args.credentials.resolve()
    if credential_path.is_relative_to(Path(__file__).resolve().parent):
        parser.error("Keep credentials outside this repository")
    if credential_path.stat().st_mode & 0o077:
        parser.error("Credential file must be readable only by its owner (chmod 600)")
    credentials = json.loads(credential_path.read_text())
    cls = clients[args.venue]
    result = {"checked_at_utc": timestamp(), "transport": "real HTTPS", "simulated_funds_only": True}
    try:
        result.update(cls(credentials).check(args.exercise_orders))
    except (APIError, ValueError, KeyError) as exc:
        # No tracebacks / credentials / raw account payloads in the public result.
        parser.exit(1, f"Sandbox check failed: {type(exc).__name__}: {exc}\n")
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
