"""Top-level dispatcher; delegates to cbim_kernel.engine.cli.main()."""
import sys

from engine import cli as engine_cli


def main(argv=None):
    """Run the engine CLI.

    engine_cli.main() today reads sys.argv directly via argparse, so honour
    that contract: install argv into sys.argv before delegating.
    """
    if argv is not None:
        sys.argv = ["cbim_kernel"] + list(argv)
    return engine_cli.main() or 0
