"""actions/ — concrete BT leaf nodes used by the main loop ROOT.

Each Action follows the iron rules from README §2:
  - subclass Node
  - only mutate state via bb.*
  - no cross-tick fields on self
  - yield = set bb.pending_dispatch + return RUNNING
"""
