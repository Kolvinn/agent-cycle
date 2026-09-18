"""UI adapters.

``protocol`` and ``scripted`` are import-safe anywhere. ``interactive`` pulls
in a terminal library, so it is imported lazily via :func:`interactive_ui` —
that keeps the headless test path free of any dependency on a presentation
stack, which is the point of the split.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .protocol import UI, SignOff, Verdict
from .scripted import ScriptedUI

if TYPE_CHECKING:
    from .interactive import InteractiveUI


def interactive_ui(*, width: int | None = None) -> "InteractiveUI":
    from .interactive import InteractiveUI

    return InteractiveUI(width=width)


__all__ = ["UI", "ScriptedUI", "SignOff", "Verdict", "interactive_ui"]
