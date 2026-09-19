"""One module per frame.

A frame is a stance the model is put into: its own brief, its own tool surface,
its own pool. Each frame lives in its own file so a stage can be read, argued
with and changed without the other three in the way, and ``graph.py`` holds
only the topology.
"""

from . import antithesis, assume, orientate, synthesis

__all__ = ["antithesis", "assume", "orientate", "synthesis"]
