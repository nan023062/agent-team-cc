---
name: dashboard
owner: architect
description: Local web dashboard: HTTP server + static UI for inspecting project state
keywords: []
dependencies: []
---

## Positioning

Local web dashboard for inspecting CBIM project state. Stdlib-only HTTP server (`server.py`) serving static UI assets (`index.html`, `app.js`, `style.css`, vendored `marked`/`purify`) and a thin JSON API backed by `services/`.

## Class Diagram

```mermaid
classDiagram
    class server {
        +run(port, auto_open)
        +handle_api(request)
    }
    class dashboard {
        +main entry: `cbim dashboard`
    }
    class UI {
        index.html + app.js + style.css
    }
    dashboard --> server
    server --> SVC[services.*]
    UI -.-> server : fetch JSON API
```

## Key Decisions

- **Stdlib HTTP only — no Flask/FastAPI.** The dashboard ships inside every kernel version; adding a web framework would balloon the install footprint for a tool most users rarely open.
- **Vendored frontend deps** (`marked`, `purify`). Avoids per-project npm install for offline use.

