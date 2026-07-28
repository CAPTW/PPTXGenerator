from __future__ import annotations

from typing import Any

from ..schemas.layer_manifest_v5 import validate_layer_manifest
from ..schemas.object_graph_v1 import validate_object_graph
from ..schemas.psd_like_layer_model import validate_psd_like_document
from ..schemas.semantic_slot_graph import validate_semantic_slot_graph


def validate_layer_protocol(
    psd_like_layer_model: dict[str, Any],
    object_graph: dict[str, Any],
    layer_manifest: dict[str, Any],
    semantic_slot_graph: dict[str, Any],
) -> dict[str, Any]:
    checks = {
        "psd_like_layer_model": validate_psd_like_document(psd_like_layer_model),
        "object_graph": validate_object_graph(object_graph),
        "layer_manifest": validate_layer_manifest(layer_manifest),
        "semantic_slot_graph": validate_semantic_slot_graph(semantic_slot_graph),
    }
    failures = [failure for check in checks.values() for failure in check.get("failures", [])]
    warnings = [warning for check in checks.values() for warning in check.get("warnings", [])]
    return {"schema_name": "layer_protocol_validation", "pass": not failures, "checks": checks, "failures": failures, "warnings": warnings}
