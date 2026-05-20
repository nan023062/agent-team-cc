import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from installer.cli import main

sys.exit(main())
