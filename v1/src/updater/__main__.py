"""Entry point for ``python -m updater``."""
import sys

from updater.cli import main

sys.exit(main(sys.argv[1:]))
