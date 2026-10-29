"""Local subprocess integration harness. Generates ephemeral credentials in memory."""

import json
import os
import secrets
import select
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def post(url, path, token="", data=None, raw=None):
    body = (
        raw
        if raw is not None
        else json.dumps(data if data is not None else {}).encode()
    )
    request = Request(
        url + path,
        data=body,
        method="POST",
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=4) as res:
            return res.status, json.load(res)
    except HTTPError as exc:
        try:
            return exc.code, json.load(exc)
        finally:
            exc.close()


@contextmanager
def running_services():
    processes = []
    with tempfile.TemporaryDirectory() as temp:
        service, developer, application = (secrets.token_hex(24) for _ in range(3))
        audit = Path(temp) / "audit.jsonl"

        def start(module, extra):
            env = {**os.environ, **extra}
            child = subprocess.Popen(
                [sys.executable, "-m", module, "--port", "0"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            processes.append(child)
            ready, _, _ = select.select([child.stdout], [], [], 10)
            if not ready:
                raise RuntimeError("service startup timed out")
            line = child.stdout.readline().strip()
            if not line.isdigit():
                raise RuntimeError("service failed to start")
            return child, "http://127.0.0.1:" + line

        try:
            engine, private = start(
                "solutions.calculation_boundary.engine.server",
                {"SERVICE_TOKEN": service},
            )
            gateway, public = start(
                "solutions.calculation_boundary.gateway.server",
                {
                    "ENGINE_URL": private,
                    "SERVICE_TOKEN": service,
                    "DEVELOPER_TOKEN": developer,
                    "APPLICATION_TOKEN": application,
                    "AUDIT_PATH": str(audit),
                },
            )
            yield dict(
                public=public,
                private=private,
                service=service,
                developer=developer,
                application=application,
                audit=audit,
                engine=engine,
                gateway=gateway,
            )
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
                try:
                    process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()
