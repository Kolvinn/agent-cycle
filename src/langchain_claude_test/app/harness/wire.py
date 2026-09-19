"""A pydantic model's path to a schema the CLI's validator accepts.

The CLI validates ``output_format`` with Ajv 8 in strict mode against the
draft-07 vocabulary and ships the schema as a *tool's* ``input_schema``. Eight
of eleven pydantic constructs pass untouched; three need repair. Measured in
``scripts/spikes/spike_04_structured_output.py``; ported here unchanged in
substance.

1. **Strip ``discriminator``**, keep the ``oneOf`` beside it. Pydantic still
   applies the discriminated validator on the way back in.
2. **Expand ``prefixItems``** into ``items`` plus ``minItems``/``maxItems``.
   Positional typing is lost, so keep tuples out of wire schemas.
3. **Rewrite a bare ``$ref`` root** into the referenced object, keeping
   ``$defs`` so recursion inside still resolves.

The reply is validated against the **untransformed** model: the transform
changes the wire schema, never the type the graph keeps.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


def _strip_discriminator(node: Any) -> Any:
    if isinstance(node, dict):
        return {k: _strip_discriminator(v) for k, v in node.items() if k != "discriminator"}
    if isinstance(node, list):
        return [_strip_discriminator(v) for v in node]
    return node


def _expand_prefix_items(node: Any) -> Any:
    if isinstance(node, dict):
        out = {k: _expand_prefix_items(v) for k, v in node.items() if k != "prefixItems"}
        if (prefix := node.get("prefixItems")) is not None:
            out["items"] = {"anyOf": [_expand_prefix_items(i) for i in prefix]}
            out["minItems"] = out["maxItems"] = len(prefix)
        return out
    if isinstance(node, list):
        return [_expand_prefix_items(v) for v in node]
    return node


def _inline_ref_root(schema: dict[str, Any]) -> dict[str, Any]:
    ref = schema.get("$ref")
    if not ref or "type" in schema:
        return schema
    key = ref.rsplit("/", 1)[-1]
    target = dict(schema.get("$defs", {}).get(key, {}))
    if not target:
        return schema
    target["$defs"] = schema["$defs"]
    return target


def to_wire_schema(model: type[BaseModel]) -> dict[str, Any]:
    """``model_json_schema()``, repaired for the CLI's validator."""
    return _expand_prefix_items(_strip_discriminator(_inline_ref_root(model.model_json_schema())))


def validate_payload(model: type[BaseModel], structured_output: Any) -> BaseModel:
    """Validate against the untransformed model."""
    return model.model_validate(structured_output)
