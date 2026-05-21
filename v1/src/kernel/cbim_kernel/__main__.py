"""Entry point: python -m cbim_kernel <args>  =  python .cbim/engine <args>"""
import sys

from cbim_kernel import cli

if __name__ == "__main__":
    sys.exit(cli.main(sys.argv[1:]))
