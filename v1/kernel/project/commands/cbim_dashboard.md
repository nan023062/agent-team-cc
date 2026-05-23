---
description: Open (or reopen) the CBIM dashboard in the browser
allowed-tools: mcp__cbim__dashboard_ensure_running, Bash
---

Run these two steps in order:

1. Call the `dashboard_ensure_running` MCP tool. It either confirms the dashboard is already running or spawns it; it returns a JSON dict with a `url` field.

2. Open the returned URL in the user's browser using:

   ```bash
   python3 -c "import webbrowser, sys; webbrowser.open(sys.argv[1])" "<URL>"
   ```

   (substitute `<URL>` with the `url` field from step 1's return value)

Then print the URL to the user.
