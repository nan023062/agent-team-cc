"""
dashboard/server.py — HTTP front-end for the CBIM dashboard UI.

This module is a thin adapter: it serves the static files from
`.cbim/dashboard/` and forwards `/api/*` requests to the `services` layer.
All data shaping lives in `services.*_service`; this file owns only the
HTTP wire format and the heartbeat-driven shutdown.

Endpoints:
  GET /api/entries    - memory entries (short + medium tier)   [services.memory_service]
  GET /api/agents     - work agents from .claude/agents/       [services.agent_service]
  GET /api/knowledge  - .dna modules across the project tree   [services.knowledge_service]
  GET /api/log        - current session log tail               [services.log_service]
  GET /heartbeat      - keep-alive (browser pings every 10s)
"""

from __future__ import annotations

import http.server
import json
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import services

_HEARTBEAT_TIMEOUT = 30  # seconds - server self-terminates if no ping
_DEFAULT_PORT = 8765
_PORT_FALLBACK_ATTEMPTS = 20


def load_port(cbim_dir: Path) -> int:
    """Read `dashboard.port` from .cbim/config.json (or fall back to default).

    Errors in the config file are non-fatal: we log to stderr and fall
    back. Misconfiguration shouldn't lock the user out of the UI.
    """
    cfg_path = cbim_dir / "config.json"
    if not cfg_path.exists():
        return _DEFAULT_PORT
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"[cbim] warning: failed to read {cfg_path}: {e}", file=sys.stderr)
        return _DEFAULT_PORT
    return int(cfg.get("dashboard", {}).get("port") or _DEFAULT_PORT)


def start_server(dashboard_dir: Path, cbim_dir: Path, root_dir: Path,
                 port: int | None = None, open_browser: bool = True) -> None:
    """Bind the HTTP server and serve until the heartbeat watchdog fires.

    Args:
        dashboard_dir: Directory holding index.html / app.js / style.css.
        cbim_dir:      The `.cbim/` directory - needed so services can
                       resolve project root from cwd, and so log_service
                       can find session log files.
        root_dir:      Project root (where `.dna/` modules live).
        port:          Override; otherwise read from config.json.
        open_browser:  If False, don't auto-launch the browser (CI mode).

    Port-conflict policy: tries up to 20 consecutive ports starting at the
    requested one; the actual bound port is recorded in the PID file so
    consumers (dashboard.py launcher, auto_preview hook, /cbim_dashboard
    command) read the real port instead of guessing.
    """
    if port is None:
        port = load_port(cbim_dir)

    last_beat = [time.monotonic()]

    requested_port = port
    server = None
    bound_port = -1
    last_err: OSError | None = None
    for offset in range(_PORT_FALLBACK_ATTEMPTS):
        candidate = requested_port + offset
        try:
            handler = _make_handler(dashboard_dir, cbim_dir, root_dir, last_beat, candidate)
            server = http.server.HTTPServer(("127.0.0.1", candidate), handler)
            bound_port = candidate
            break
        except OSError as e:
            last_err = e
            continue

    if server is None:
        end_port = requested_port + _PORT_FALLBACK_ATTEMPTS - 1
        print(
            f"[cbim] dashboard: tried ports {requested_port}..{end_port}, "
            f"all in use ({last_err})",
            file=sys.stderr,
        )
        sys.exit(1)

    if bound_port != requested_port:
        print(
            f"[cbim] dashboard.port {requested_port} busy; bound to {bound_port}",
            file=sys.stderr,
        )

    pid_path = cbim_dir / "dashboard" / ".run" / ".preview.pid"
    pid_tmp_path = pid_path.with_suffix(pid_path.suffix + ".tmp")
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_tmp_path.write_text(
        json.dumps({"pid": os.getpid(), "port": bound_port}),
        encoding="utf-8",
    )
    os.replace(pid_tmp_path, pid_path)

    threading.Thread(
        target=_watchdog, args=(server, last_beat), daemon=True
    ).start()

    url = f"http://127.0.0.1:{bound_port}"
    if open_browser:
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()
    print(
        f"[cbim] dashboard at {url}  (auto-stops {_HEARTBEAT_TIMEOUT}s after "
        f"browser closes)",
        file=sys.stderr,
    )
    try:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    finally:
        try:
            pid_path.unlink(missing_ok=True)
        except OSError:
            pass
    print("[cbim] dashboard stopped", file=sys.stderr)


# ---------------------------------------------------------------------------
# HTTP plumbing
# ---------------------------------------------------------------------------

def _watchdog(server: http.server.HTTPServer, last_beat: list) -> None:
    while True:
        time.sleep(5)
        if time.monotonic() - last_beat[0] > _HEARTBEAT_TIMEOUT:
            print("\n[cbim] browser closed - shutting down", file=sys.stderr)
            server.shutdown()
            return


def _make_handler(dashboard_dir: Path, cbim_dir: Path, root_dir: Path, last_beat: list, bound_port: int):
    """Build a SimpleHTTPRequestHandler bound to dashboard_dir.

    Routes /api/* to the services layer; everything else falls through to
    static-file serving for the SPA assets.
    """

    class _Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(dashboard_dir), **kwargs)

        def do_GET(self):  # noqa: N802 - required by stdlib
            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/api/entries":
                self._serve_json(services.list_entries(cwd=root_dir))
            elif path == "/api/agents":
                self._serve_json(services.list_agents(cwd=root_dir, include_builtin=True))
            elif path == "/api/knowledge":
                self._serve_json(services.list_modules(cwd=root_dir))
            elif path == "/api/log":
                qs = parse_qs(parsed.query)
                try:
                    since = int(qs.get("since", ["0"])[0])
                except (ValueError, TypeError):
                    since = 0
                self._serve_json(services.read_log(cbim=cbim_dir, since=since))
            elif path == "/api/info":
                payload = json.dumps({
                    "host": "127.0.0.1",
                    "port": bound_port,
                    "root_dir": str(root_dir.resolve()),
                    "cbim_dir": str(cbim_dir.resolve()),
                }).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            elif path == "/heartbeat":
                last_beat[0] = time.monotonic()
                self.send_response(204)
                self.end_headers()
            else:
                super().do_GET()

        def _serve_json(self, data) -> None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):  # noqa: A003 - stdlib override
            pass  # suppress per-request access logs

    return _Handler
