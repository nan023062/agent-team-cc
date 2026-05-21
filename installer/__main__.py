"""Entry point for ``python -m installer``."""
import sys

from installer.cli import main

sys.exit(main(sys.argv[1:]))
