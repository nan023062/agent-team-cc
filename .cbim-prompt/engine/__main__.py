import sys

# Force UTF-8 on the standard streams so we can emit non-ASCII skill/convention
# text (mermaid arrows, warning symbols, CJK content) on Windows consoles
# whose default code page is GBK/CP936.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from .cli import main

raise SystemExit(main())
