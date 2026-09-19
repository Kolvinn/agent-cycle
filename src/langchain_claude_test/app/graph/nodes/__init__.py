"""The three frames. Each is one module exposing ``NAME`` and one async node
function of the same name; the edge list in ``graph.py`` is where they meet.
"""

from __future__ import annotations

from . import antithesis, orientate, synthesis

__all__ = ["antithesis", "orientate", "synthesis"]
