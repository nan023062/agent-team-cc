"""dream.actions — governance-loop Action nodes.

Each Action is a subclass of bt.core.node.Node with tick(bb)->Status. No
cross-tick state on self (the bt iron rule applies here too).
"""
