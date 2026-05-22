"""
cli.py — Empty after P3 Wave 1.

Historical context: this module used to host cmd_agents_* / cmd_modules_*
argparse handlers that the top-level engine/cli.py dispatched into. Those
handlers were thin wrappers over cbi.resources.{Agent,DNAModule}; in P3 Wave 1
the wrapper layer was deleted and the handler logic was inlined into
cbim_kernel/engine/cli.py as _handle_agent_* / _handle_dna_* private functions.

Why keep the file at all: the .dna/module.md description still references
cbi._primitives.cli as a logical surface, and downstream packages may have an
in-flight import we don't see. If you find yourself importing from here,
prefer:
    from cbim_kernel.cbi.resources import Agent, DNAModule
or, for the CLI dispatch handlers themselves:
    cbim_kernel.engine.cli._handle_agent_* / _handle_dna_*
"""
