"""Entry point: python -m cbim_kernel <args>  =  python .cbim/engine <args>"""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from cbim_kernel import cli

if __name__ == "__main__":
    sys.exit(cli.main(sys.argv[1:]))
