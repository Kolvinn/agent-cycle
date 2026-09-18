"""The round driver and everything around it.

Layering, and the reason for it:

- :mod:`.ui` is the only place a terminal library appears.
- the runner (next) talks to :class:`~.ui.protocol.UI` and to the ledger, and
  to nothing else — so a full round can be replayed headless, with scripted
  sign-offs and no model.
"""

from .ui import UI, ScriptedUI, SignOff, Verdict, interactive_ui

__all__ = ["UI", "ScriptedUI", "SignOff", "Verdict", "interactive_ui"]
