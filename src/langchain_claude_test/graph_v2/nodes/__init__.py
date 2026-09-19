"""One module per frame.

A frame is a stance the model is put into: its own prompt, its own tool surface,
its own pool. Keeping each in its own file means a stage can be read, argued
with and changed without the other three in the way — and `graph.py` is left
holding only the topology, so reading the edge list is reading the flow.

``assume`` is the exception in shape but not in kind: it is a subgraph rather
than a single node, because it has two loops in it. It is still one frame.
"""

from . import antithesis, assume, orientate, synthesis

__all__ = ["antithesis", "assume", "orientate", "synthesis"]
