"""
hooks_src/_lib/mcp_client.py — UDS JSON-RPC-lite client for hook scripts.

stdlib-only. No business knowledge. No `cbim.*` imports.

Wire format (newline-delimited JSON, keep-alive):
    request : {"tool": "<name>", "args": {...}} + "\n"
    response: {"ok": true,  "result": <dict>}    + "\n"
              {"ok": false, "error": "<msg>"}    + "\n"

Public surface:
    class McpClient(sock_path)
        .call(tool, args, timeout=5.0) -> dict | None
        .close()
    call(tool, args, cwd, timeout=5.0) -> dict | None
        Convenience: build a client for `cwd`'s sock, call once, close.

Returns None whenever the call could not be completed (server unreachable
after retry budget, or server returned ok=false). In both failure modes a
single line is written to stderr with the prefix `[CBIM:hook]`.
"""

from __future__ import annotations

import json
import socket
import sys
import time
from pathlib import Path

from .paths import mcp_sock_path, project_root_from_cwd


_BACKOFF_SECONDS = (0.05, 0.20, 0.50, 1.00)


def _stderr(msg: str) -> None:
    try:
        print(msg, file=sys.stderr, flush=True)
    except Exception:
        pass


class McpClient:
    """One TCP-style connection to the MCP server's UDS listener."""

    def __init__(self, sock_path: Path):
        self._sock_path = Path(sock_path)
        self._sock: socket.socket | None = None
        self._buf = b""

    def _connect(self, timeout: float) -> str | None:
        """Try to connect with exponential backoff. Returns last error or None on success."""
        last_err = "no attempts made"
        for delay in (0.0,) + _BACKOFF_SECONDS:
            if delay:
                time.sleep(delay)
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.settimeout(timeout)
                s.connect(str(self._sock_path))
                self._sock = s
                return None
            except (OSError, socket.error) as e:
                last_err = f"{type(e).__name__}: {e}"
                try:
                    s.close()
                except Exception:
                    pass
        return last_err

    def _readline(self) -> bytes:
        assert self._sock is not None
        while b"\n" not in self._buf:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise ConnectionError("server closed connection")
            self._buf += chunk
        line, _, rest = self._buf.partition(b"\n")
        self._buf = rest
        return line

    def call(self, tool: str, args: dict, timeout: float = 5.0) -> dict | None:
        if self._sock is None:
            err = self._connect(timeout)
            if err is not None:
                _stderr(f"[CBIM:hook] mcp unreachable at {self._sock_path}: {err}")
                return None

        try:
            req = json.dumps({"tool": tool, "args": args or {}}, ensure_ascii=False)
            self._sock.sendall(req.encode("utf-8") + b"\n")
            line = self._readline()
            resp = json.loads(line.decode("utf-8"))
        except (OSError, ConnectionError, json.JSONDecodeError) as e:
            _stderr(f"[CBIM:hook] mcp transport error on {tool}: {type(e).__name__}: {e}")
            self.close()
            return None

        if resp.get("ok"):
            result = resp.get("result")
            return result if isinstance(result, dict) else {"result": result}
        _stderr(f"[CBIM:hook] mcp tool {tool} failed: {resp.get('error', 'unknown')}")
        return None

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
            self._buf = b""


def call(tool: str, args: dict, cwd: str, timeout: float = 5.0) -> dict | None:
    """One-shot: locate sock from `cwd`, connect, call, close."""
    root = project_root_from_cwd(cwd)
    sock = mcp_sock_path(root)
    client = McpClient(sock)
    try:
        return client.call(tool, args, timeout=timeout)
    finally:
        client.close()
