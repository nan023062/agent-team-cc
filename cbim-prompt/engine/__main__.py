import sys
from pathlib import Path

# Force UTF-8 on the standard streams so we can emit non-ASCII skill/convention
# text (mermaid arrows, warning symbols, CJK content) on Windows consoles
# whose default code page is GBK/CP936.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Support both `python -m engine` (cwd=.cbim-prompt/) and
# `python .cbim-prompt/engine` (cwd=project root).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.cli import main
from engine.call_log import log_call

exit_code = 1
argv = sys.argv[1:]
try:
    exit_code = main() or 0
finally:
    log_call(argv, exit_code)
raise SystemExit(exit_code)
