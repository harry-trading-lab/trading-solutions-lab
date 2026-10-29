"""Application gateway: no engine import, only an HTTP contract.

Development credential can access a static fixture, never the live route.
Example only: production requires TLS, identity lifecycle, rate limits and IAM.
"""

import argparse
import hmac
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


def make_server(
    port,
    engine_url,
    service_token,
    developer_token,
    application_token,
    audit_path,
    host="127.0.0.1",
):
    tokens = [service_token, developer_token, application_token]
    if any(not t or len(t) < 32 for t in tokens) or len(set(tokens)) != 3:
        raise ValueError(
            "three distinct random tokens of at least 32 characters required"
        )
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, status, payload, role):
            # Log decisions only: no headers, token, query, body or formula.
            route = self.path if self.path in ("/v1/mock", "/v1/quote") else "unknown"
            event = {"role": role, "route": route, "status": status}
            with lock:
                with open(audit_path, "a", encoding="utf-8") as out:
                    out.write(json.dumps(event) + "\n")
            raw = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            self.send(404, {"error": "not_found"}, "anonymous")

        def do_POST(self):
            supplied = self.headers.get("Authorization", "")
            role = "anonymous"
            if hmac.compare_digest(
                supplied.encode(), ("Bearer " + developer_token).encode()
            ):
                role = "developer"
            elif hmac.compare_digest(
                supplied.encode(), ("Bearer " + application_token).encode()
            ):
                role = "application"
            if role == "anonymous":
                return self.send(401, {"error": "unauthorized"}, role)
            if self.path not in ("/v1/mock", "/v1/quote"):
                return self.send(404, {"error": "not_found"}, role)
            if self.path == "/v1/quote" and role != "application":
                return self.send(403, {"error": "forbidden"}, role)
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 4096:
                    return self.send(413, {"error": "payload_size"}, role)
                self.connection.settimeout(2)
                body = self.rfile.read(length)
                json.loads(body)
            except (ValueError, UnicodeError, TimeoutError):
                return self.send(400, {"error": "invalid_request"}, role)
            if self.path == "/v1/mock":
                return self.send(
                    200,
                    {"future_value_cents": 12100, "model": "static-fixture-v1"},
                    role,
                )
            request = Request(
                engine_url + "/calculate",
                data=body,
                headers={
                    "Authorization": "Bearer " + service_token,
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urlopen(request, timeout=2) as response:
                    result = json.load(response)
            except HTTPError as exc:
                exc.close()
                if exc.code in (400, 413):
                    return self.send(exc.code, {"error": "invalid_request"}, role)
                return self.send(502, {"error": "calculation_unavailable"}, role)
            except (URLError, TimeoutError, ValueError):
                return self.send(502, {"error": "calculation_unavailable"}, role)
            self.send(200, result, role)

    return ThreadingHTTPServer((host, port), Handler)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    server = make_server(
        args.port,
        os.environ["ENGINE_URL"],
        os.environ["SERVICE_TOKEN"],
        os.environ["DEVELOPER_TOKEN"],
        os.environ["APPLICATION_TOKEN"],
        os.environ["AUDIT_PATH"],
        args.host,
    )
    print(server.server_address[1], flush=True)
    server.serve_forever()
