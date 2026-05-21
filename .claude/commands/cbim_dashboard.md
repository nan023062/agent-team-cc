---
description: Open (or reopen) the CBIM preview dashboard in the browser
allowed-tools: Bash
---

Ensure the CBIM preview server is running and open the dashboard in the browser.

Run the following two commands in order:

1. Start the server if it isn't already running (idempotent):
   `python3 .cbim/hooks/auto_preview.py`

2. Open the browser to the dashboard URL regardless of whether the server was already running:
   `python3 -c "import json, webbrowser; from pathlib import Path; cfg = json.loads(Path('.cbim/config.json').read_text()) if Path('.cbim/config.json').exists() else {}; port = cfg.get('preview', {}).get('port', 8765); webbrowser.open(f'http://127.0.0.1:{port}'); print(f'[cbim] dashboard opened at http://127.0.0.1:{port}')"`

Then tell the user: "Dashboard opened at http://127.0.0.1:8765" (use the actual port from config).
