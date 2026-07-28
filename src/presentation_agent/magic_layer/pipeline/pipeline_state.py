from __future__ import annotations

from typing import Any

from .controlled_sample import CONTROLLED_SAMPLE_ID
from .stage_registry import STAGE_ORDER


def build_pipeline_state(*, mode: str = "IMPORT_EXISTING", run_id: str = "p02_import_existing") -> dict[str, Any]:
    return {
        "schema": "pipeline_state.v1",
        "pipeline_id": "magic_layer_pipeline_v2",
        "mode": mode,
        "run_id": run_id,
        "sample_id": CONTROLLED_SAMPLE_ID,
        "stage_states": [
            {
                "stage_id": stage_id,
                "status": "IMPORTED" if mode == "IMPORT_EXISTING" else "PLANNED",
                "evidence_paths": [],
                "limitations": ["controlled_minimal_scope_only"],
                "started": False,
                "completed": mode == "IMPORT_EXISTING",
                "generated_artifacts": [],
                "forbidden_artifacts_created": [],
                "decision_label": None,
            }
            for stage_id in STAGE_ORDER
        ],
        "artifact_states": [],
        "gate_states": [],
        "lineage": {},
        "limitations": ["minimal sample only", "not reference-driven"],
        "blocked_next_actions": ["E03", "E04", "D08", "C11", "bulk", "canonical_promotion"],
        "allowed_next_actions": ["P03_CONTROLLED_REPLAY", "C04_FIXTURE_REPAIR"],
        "product_pass": False,
        "scaleout_allowed": False,
        "canonical_promotion_allowed": False,
    }
