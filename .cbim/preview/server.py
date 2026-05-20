"""
server.py — Local HTTP server for CBIM preview.

Serves static files from cbim-prompt/preview/ and provides:
  GET /api/entries    — memory entries (short + medium tier)
  GET /api/agents     — agent definitions from cbim-prompt/agents/
  GET /api/knowledge  — .dna modules scanned from project root
  GET /heartbeat      — keep-alive (client pings every 10s)
"""

import http.server
import json
import re
import sys
import threading
import webbrowser
from pathlib import Path

TIERS = ["short", "medium"]
_HEARTBEAT_TIMEOUT = 30  # seconds


def start_server(store_dir: Path, preview_dir: Path, cbim_dir: Path,
                 root_dir: Path, port: int = 8765) -> None:
    import time
    last_beat = [time.monotonic()]

    handler = _make_handler(store_dir, preview_dir, cbim_dir, root_dir, last_beat)
    server = http.server.HTTPServer(("127.0.0.1", port), handler)

    def _watchdog():
        while True:
            time.sleep(5)
            if time.monotonic() - last_beat[0] > _HEARTBEAT_TIMEOUT:
                print("\n[cbim] browser closed — shutting down", file=sys.stderr)
                server.shutdown()
                return

    threading.Thread(target=_watchdog, daemon=True).start()

    url = f"http://127.0.0.1:{port}"
    threading.Timer(0.3, lambda: webbrowser.open(url)).start()
    print(f"[cbim] preview at {url}  (auto-stops {_HEARTBEAT_TIMEOUT}s after browser closes)",
          file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    print("[cbim] preview stopped", file=sys.stderr)


def _make_handler(store_dir: Path, preview_dir: Path, cbim_dir: Path,
                  root_dir: Path, last_beat: list):
    import time

    class _Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(preview_dir), **kwargs)

        def do_GET(self):
            if self.path == "/api/entries":
                self._serve_json(_collect_entries(store_dir))
            elif self.path == "/api/agents":
                self._serve_json(_collect_agents(cbim_dir))
            elif self.path == "/api/knowledge":
                self._serve_json(_collect_knowledge(root_dir))
            elif self.path == "/heartbeat":
                last_beat[0] = time.monotonic()
                self.send_response(204)
                self.end_headers()
            else:
                super().do_GET()

        def _serve_json(self, data):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass  # suppress per-request logs

    return _Handler


# ---------------------------------------------------------------------------
# Memory data collection
# ---------------------------------------------------------------------------

def _collect_entries(store_dir: Path) -> list[dict]:
    entries = []
    for tier in TIERS:
        tier_dir = store_dir / tier
        if not tier_dir.exists():
            continue
        for md_file in sorted(tier_dir.glob("*.md"), reverse=True):
            entries.append(_parse_entry(md_file, tier))
    return entries


def _parse_entry(path: Path, tier: str) -> dict:
    try:
        raw = path.read_text(encoding="utf-8")
    except (FileNotFoundError, PermissionError):
        raw = ""
    meta = _parse_frontmatter(raw)
    body = _strip_frontmatter(raw)
    title = _extract_title(body, path.name)
    return {
        "id": path.name,
        "tier": tier,
        "date": meta.get("date") or _date_from_name(path.name),
        "keyword": meta.get("keyword", ""),
        "type": meta.get("type", ""),
        "modules": meta.get("modules", ""),
        "sources": meta.get("sources", ""),
        "title": title,
        "body": body,
    }


# Built-in agents are not shown in the preview — only user-defined work agents.
_BUILTIN_AGENTS = {"architect", "hr", "auditor", "programmer"}


# ---------------------------------------------------------------------------
# Agents data collection
# ---------------------------------------------------------------------------

def _collect_agents(cbim_dir: Path) -> list[dict]:
    agents_dir = cbim_dir.parent / ".claude" / "agents"
    if not agents_dir.exists():
        return []
    agents = []
    for agent_dir in sorted(agents_dir.iterdir()):
        if not agent_dir.is_dir():
            continue
        if agent_dir.name in _BUILTIN_AGENTS:
            continue
        md = agent_dir / f"{agent_dir.name}.md"
        if not md.exists():
            continue
        try:
            raw = md.read_text(encoding="utf-8")
        except (FileNotFoundError, PermissionError):
            continue
        meta = _parse_frontmatter(raw)
        body = _strip_frontmatter(raw)
        skills = _collect_agent_skills(agent_dir)
        agents.append({
            "id": agent_dir.name,
            "name": meta.get("name", agent_dir.name),
            "description": meta.get("description", ""),
            "model": meta.get("model", ""),
            "tools": meta.get("tools", ""),
            "skills": skills,
            "body": body,
        })
    return agents


def _collect_agent_skills(agent_dir: Path) -> list[dict]:
    skills_dir = agent_dir / "skills"
    if not skills_dir.exists():
        return []
    skills = []
    for skill_file in sorted(skills_dir.glob("*.md")):
        try:
            raw = skill_file.read_text(encoding="utf-8")
        except (FileNotFoundError, PermissionError):
            raw = ""
        skills.append({
            "id": skill_file.stem,
            "body": _strip_frontmatter(raw),
        })
    return skills


# ---------------------------------------------------------------------------
# Knowledge data collection
# ---------------------------------------------------------------------------

def _collect_knowledge(root_dir: Path) -> list[dict]:
    """Scan modules using dual format: module.md (new) or module.json (legacy)."""
    modules = []
    seen_dirs: set[Path] = set()

    # New format: .dna/module.md
    for mm in sorted(root_dir.rglob(".dna/module.md")):
        mod_dir = mm.parent.parent
        seen_dirs.add(mod_dir)
        aimod = mm.parent
        try:
            raw = mm.read_text(encoding="utf-8")
        except Exception:
            continue
        data = _parse_frontmatter(raw)
        body = _strip_frontmatter(raw)
        rel = str(mod_dir.relative_to(root_dir))
        contract = (aimod / "contract.md").read_text(encoding="utf-8") \
            if (aimod / "contract.md").exists() else ""
        workflows = _collect_workflows(aimod / "workflows")
        kw = data.get("keywords", "")
        if isinstance(kw, str):
            kw = [k.strip() for k in kw.split(",") if k.strip()] if kw else []
        deps = data.get("dependencies", "")
        if isinstance(deps, str):
            deps = [d.strip() for d in deps.split(",") if d.strip()] if deps else []
        modules.append({
            "id": rel or ".",
            "path": rel or ".",
            "name": data.get("name", rel),
            "owner": data.get("owner", ""),
            "description": data.get("description", ""),
            "keywords": kw if isinstance(kw, list) else [],
            "dependencies": deps if isinstance(deps, list) else [],
            "architecture": body,
            "contract": contract,
            "workflows": workflows,
        })

    # Legacy format: .dna/module.json (only if not already loaded)
    for mj in sorted(root_dir.rglob(".dna/module.json")):
        mod_dir = mj.parent.parent
        if mod_dir in seen_dirs:
            continue
        try:
            data = json.loads(mj.read_text(encoding="utf-8"))
        except Exception:
            continue
        aimod = mj.parent
        rel = str(mod_dir.relative_to(root_dir))
        arch = (aimod / "architecture.md").read_text(encoding="utf-8") \
            if (aimod / "architecture.md").exists() else ""
        contract = (aimod / "contract.md").read_text(encoding="utf-8") \
            if (aimod / "contract.md").exists() else ""
        workflows = _collect_workflows(aimod / "workflows")
        modules.append({
            "id": rel or ".",
            "path": rel or ".",
            "name": data.get("name", rel),
            "owner": data.get("owner", ""),
            "description": data.get("description", ""),
            "keywords": data.get("keywords", []),
            "dependencies": data.get("dependencies", []),
            "architecture": arch,
            "contract": contract,
            "workflows": workflows,
        })
    return modules


def _collect_workflows(workflows_dir: Path) -> list[dict]:
    if not workflows_dir.exists():
        return []
    workflows = []
    for wf_dir in sorted(workflows_dir.iterdir()):
        if not wf_dir.is_dir():
            continue
        wf_file = wf_dir / "workflow.md"
        if not wf_file.exists():
            continue
        try:
            raw = wf_file.read_text(encoding="utf-8")
        except (FileNotFoundError, PermissionError):
            raw = ""
        meta = _parse_frontmatter(raw)
        workflows.append({
            "id": wf_dir.name,
            "name": meta.get("name", wf_dir.name),
            "body": _strip_frontmatter(raw),
        })
    return workflows


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str) -> dict:
    meta: dict = {}
    if not text.startswith("---"):
        return meta
    end = text.find("\n---", 3)
    if end == -1:
        return meta
    for line in text[3:end].strip().splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return meta


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:].strip()
    return text.strip()


def _extract_title(body: str, fallback: str) -> str:
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("## "):
            return line[3:].strip()
        if line and not line.startswith("#"):
            return line[:80]
    return fallback


def _date_from_name(name: str) -> str:
    m = re.match(r"(\d{4}-\d{2}-\d{2})", name)
    return m.group(1) if m else ""
