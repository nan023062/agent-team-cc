import sys
from pathlib import Path

# Don't drop __pycache__ next to source files — the installer imports modules
# from cbim-prompt/ to materialize the framework, and we don't want stray
# bytecode files leaking into either the source tree or the installed
# .cbim-prompt/ tree.
sys.dont_write_bytecode = True

sys.path.insert(0, str(Path(__file__).resolve().parent))
from installer.cli import main

sys.exit(main())
