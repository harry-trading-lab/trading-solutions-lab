"""Private demo engine. Public formula is intentionally a placeholder."""

import argparse
import hmac
import json
import os
from decimal import Decimal, ROUND_HALF_UP
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def calculate(data):
    if not isinstance(data, dict) or set(data) != {
        "principal_cents",
        "annual_rate_bps",
        "years",
    }:
        raise ValueError("invalid schema")
    for key, upper in [
        ("principal_cents", 10**12),
        ("annual_rate_bps", 5000),
        ("years", 50),
    ]:
        if type(data[key]) is not int or not 0 <= data[key] <= upper:
            raise ValueError("invalid bounds")
    amount = (
        Decimal(data["principal_cents"])
        * (1 + Decimal(data["annual_rate_bps"]) / 10000) ** data["years"]
    )
    return {
        "future_value_cents": int(
            amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        ),
        "model": "public-placeholder-v1",
    }


def make_server(port, token, host="127.0.0.1"):
    if not token or len(token) < 32:
        raise ValueError("provide a random service token of at least 32 characters")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, status, payload):
            raw = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            self.send(404, {"error": "not_found"})

        def do_POST(self):
            if not hmac.compare_digest(
                self.headers.get("Authorization", "").encode(),
                ("Bearer " + token).encode(),
            ):
                return self.send(401, {"error": "unauthorized"})
            if self.path != "/calculate":
                return self.send(404, {"error": "not_found"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 4096:
                    return self.send(413, {"error": "payload_size"})
                self.connection.settimeout(2)
                data = json.loads(self.rfile.read(size))
                output = calculate(data)
            except (ValueError, TypeError, UnicodeError, TimeoutError):
                return self.send(400, {"error": "invalid_request"})
            self.send(200, output)

    return ThreadingHTTPServer((host, port), Handler)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8091)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    server = make_server(args.port, os.environ["SERVICE_TOKEN"], args.host)
    print(server.server_address[1], flush=True)
    server.serve_forever()
