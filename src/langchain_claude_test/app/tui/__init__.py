"""The terminal — Textual. The only place a UI library is imported.

Everything shown is an event the harness emitted; everything typed goes onto
the runner's queue. The two places a human's answer is needed inside a live
turn — an authority-bearing call, and the model's own question — are modal
screens that resolve a future the harness is awaiting, so the transcript keeps
streaming underneath.
"""
