---
description: Open (or reopen) the CBIM dashboard in the browser
allowed-tools: Bash
---

Ensure the CBIM dashboard server is running and open the dashboard in the browser.

Run the following two commands in order:

1. Start the server if it isn't already running (idempotent):
   `python3 .cbim/hooks/auto_preview.py`

2. Open the browser to the dashboard URL regardless of whether the server was already running. The port is resolved in this order: (a) the `port` field of `.cbim/dashboard/.run/.preview.pid` (written by the running server, reflects the actual bound port after fallback), (b) `dashboard.port` from `.cbim/config.json`, (c) `8765`.

   ```bash
   python3 -c "
   import json, webbrowser
   from pathlib import Path
   port = None
   pid_path = Path('.cbim/dashboard/.run/.preview.pid')
   if pid_path.exists():
       try:
           port = json.loads(pid_path.read_text()).get('port')
       except (json.JSONDecodeError, OSError):
           pass
   if not port:
       cfg_path = Path('.cbim/config.json')
       if cfg_path.exists():
           try:
               port = json.loads(cfg_path.read_text()).get('dashboard', {}).get('port')
           except (json.JSONDecodeError, OSError):
               pass
   port = port or 8765
   webbrowser.open(f'http://127.0.0.1:{port}')
   print(f'[cbim] dashboard opened at http://127.0.0.1:{port}')
   "
   ```

Then tell the user the URL that the command above printed (it reflects the actual bound port).
