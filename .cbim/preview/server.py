"""
preview/server.py — HTTP front-end for the CBIM preview UI.

This module is a thin adapter: it serves the static files from
`.cbim/preview/` and forwards `/api/*` requests to the `services` layer.
All data shaping lives in `services.*_service`; this file owns only the
HTTP wire format and the heartbeat-driven shutdown.

Endpoints:
  GET /api/entries    — memory entries (short + medium tier)   [services.memory_service]
  GET /api/agents     — work agents from .claude/agents/       [services.agent_service]
  GET /api/knowledge  — .dna modules across the project tree   [services.knowledge_service]
  GET /heartbeat      — keep-alive (browser pings every 10s)
"""

from __future__ import annotations

import http.server
import json
import sys
import threading
import time
import webbrowser
from pathlib import Path

import services

_HEARTBEAT_TIMEOUT = 30  # seconds — server self-terminates if no ping
_DEFAULT_PORT = 8765


def load_port(cbim_dir: Path) -> int:
    """Read `preview.port` from .cbim/config.json (or fall back to default).

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
    return int(cfg.get("preview", {}).get("port") or _DEFAULT_PORT)


def start_server(preview_dir: Path, cbim_dir: Path, root_dir: Path,
                 port: int | None = None, open_browser: bool = True) -> None:
    """Bind the HTTP server and serve until the heartbeat watchdog fires.

    Args:
        preview_dir:  Directory holding index.html / app.js / style.css.
        cbim_dir:     The `.cbim/` directory — needed so services can
                      resolve project root from cwd.
        root_dir:     Project root (where `.dna/` modules live).
        port:         Override; otherwise read from config.json.
        open_browser: If False, don't auto-launch the browser (CI mode).

    Port-conflict policy: hard-error and exit. We do NOT auto-increment —
    silent port drift breaks the SessionStart hook's idempotency contract
    (the PID file would not match what the user expects on :8765).
    """
    if port is None:
        port = load_port(cbim_dir)

    last_beat = [time.monotonic()]
    handler = _make_handler(preview_dir, root_dir, last_beat)

    try:
        server = http.server.HTTPServer(("127.0.0.1", port), handler)
    except OSError as e:
        # EADDRINUSE on macOS/Linux, WSAEACCES on Windows — same intent.
        print(f"[cbim] preview port {port} unavailable ({e}); refusing to "
              f"silently rebind. Set preview.port in .cbim/config.json or "
              f"stop the conflicting process.", file=sys.stderr)
        sys.exit(1)

    threading.Thread(
        target=_watchdog, args=(server, last_beat), daemon=True
    ).start()

    url = f"http://127.0.0.1:{port}"
    if open_browser:
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()
    print(
        f"[cbim] preview at {url}  (auto-stops {_HEARTBEAT_TIMEOUT}s after "
        f"browser closes)",
        file=sys.stderr,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    print("[cbim] preview stopped", file=sys.stderr)


# ---------------------------------------------------------------------------
# HTTP plumbing
# ---------------------------------------------------------------------------

def _watchdog(server: http.server.HTTPServer, last_beat: list) -> None:
    while True:
        time.sleep(5)
        if time.monotonic() - last_beat[0] > _HEARTBEAT_TIMEOUT:
            print("\n[cbim] browser closed — shutting down", file=sys.stderr)
            server.shutdown()
            return


def _make_handler(preview_dir: Path, root_dir: Path, last_beat: list):
    """Build a SimpleHTTPRequestHandler bound to preview_dir.

    Routes /api/* to the services layer; everything else falls through to
    static-file serving for the SPA assets.
    """

    class _Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(preview_dir), **kwargs)

        def do_GET(self):  # noqa: N802 — required by stdlib
            if self.path == "/api/entries":
                self._serve_json(services.list_entries(cwd=root_dir))
            elif self.path == "/api/agents":
                self._serve_json(services.list_agents(cwd=root_dir))
            elif self.path == "/api/knowledge":
                self._serve_json(services.list_modules(cwd=root_dir))
            elif self.path == "/heartbeat":
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

        def log_message(self, fmt, *args):  # noqa: A003 — stdlib override
            pass  # suppress per-request access logs

    return _Handler
