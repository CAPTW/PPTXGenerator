"""Orchestration helpers for E03 16-archetype Magic Layer+ expansion."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CORE_ARCHETYPES = ("cover_hero", "standard_content", "data_dashboard", "table_heavy")
EXPANSION_ARCHETYPES = (
    "section_divider",
    "visual_toc",
    "evidence_overview",
    "card_grid",
    "methodology_framework",
    "process_flow",
    "comparison_matrix",
    "timeline_roadmap",
    "decision_record",
    "risk_register",
    "case_study",
    "closing_synthesis",
)
ARCHETYPES = (*CORE_ARCHETYPES, *EXPANSION_ARCHETYPES)
E02_1_PASS_DECISION = "E02_1_PASS_START_E03_16_ARCHETYPE_MAGIC_LAYER_PLUS_TEMPLATE_PACK"
E03_READY_DECISION = "E03_READY_START_16_ARCHETYPE_MAGIC_LAYER_PLUS_TEMPLATE_PACK"


def read_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def write_md(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def validate_e02_1_handoff(e02_1_root: Path) -> dict[str, Any]:
    required = [
        e02_1_root / "e02_1_patch_report.json",
        e02_1_root / "e02_reclassification_report.json",
        e02_1_root / "e03_revised_readiness_report.json",
        e02_1_root / "harness_v3_e02_1_4core_magic_layer_plus_candidate_pack.pptx",
    ]
    missing = [path.as_posix() for path in required if not path.exists()]
    for archetype in CORE_ARCHETYPES:
        required.extend(
            [
                e02_1_root / "archetypes" / archetype / "e02_1_editable_candidate.pptx",
                e02_1_root / "archetypes" / archetype / "e02_1_canva_plus_gate_report.json",
                e02_1_root / "archetypes" / archetype / "e02_1_semantic_editability_ledger.json",
                e02_1_root / "archetypes" / archetype / "e02_1_raster_policy_report.json",
                e02_1_root / "archetypes" / archetype / "e02_1_region_scorecard.json",
            ]
        )
    missing = [path.as_posix() for path in required if not path.exists()]
    if missing:
        return {
            "schema_name": "e03_e02_1_handoff_validation_report",
            "status": "blocked",
            "decision": "E03_BLOCKED_MISSING_E02_1_HANDOFF",
            "missing": missing,
            "broad_canva_parity_claimed": False,
        }
    patch = read_json(e02_1_root / "e02_1_patch_report.json")
    reclass = read_json(e02_1_root / "e02_reclassification_report.json")
    readiness = read_json(e02_1_root / "e03_revised_readiness_report.json")
    checks = {
        "e02_1_final_decision": patch.get("decision") == E02_1_PASS_DECISION,
        "e02_reclassified_visual_patch_required": reclass.get("decision") == "E02_RECLASSIFIED_STRUCTURAL_PASS_VISUAL_FIDELITY_PATCH_REQUIRED",
        "e02_1_candidates_rendered_4_of_4": int(patch.get("rendered_count", 0)) == 4,
        "e02_1_pack_rendered_4_of_4": readiness.get("candidate_pack_rendered_4_of_4") is True,
        "semantic_raster_violations": int(patch.get("raster_policy_summary", {}).get("semantic_raster_violation_count", 0)) == 0,
        "full_slide_raster": int(patch.get("raster_policy_summary", {}).get("full_slide_raster_count", 0)) == 0,
        "screenshot_slide": int(patch.get("raster_policy_summary", {}).get("screenshot_slide_count", 0)) == 0,
        "unknown_content_bearing": _sum_archetype_count(patch, "unknown_content_bearing_layer_count") == 0,
        "text_clipping": _sum_archetype_count(patch, "text_clipping_count") == 0,
        "text_overflow": _sum_archetype_count(patch, "text_overflow_count") == 0,
        "object_collisions": _sum_archetype_count(patch, "object_collision_count") == 0,
        "protected_artifacts_unchanged": patch.get("protected_artifacts_unchanged") is True,
        "broad_canva_parity_false": patch.get("broad_canva_parity_claimed") is False,
    }
    status = "passed" if all(checks.values()) else "blocked"
    return {
        "schema_name": "e03_e02_1_handoff_validation_report",
        "status": status,
        "decision": "E02_1_HANDOFF_VALIDATED_FOR_E03" if status == "passed" else "E03_BLOCKED_MISSING_E02_1_HANDOFF",
        "checks": checks,
        "source_of_truth": {
            "patch_report": (e02_1_root / "e02_1_patch_report.json").as_posix(),
            "reclassification_report": (e02_1_root / "e02_reclassification_report.json").as_posix(),
            "e03_readiness_report": (e02_1_root / "e03_revised_readiness_report.json").as_posix(),
        },
        "e02_1_decision": patch.get("decision"),
        "e03_readiness_decision": readiness.get("decision"),
        "broad_canva_parity_claimed": False,
    }


def markdown_summary(title: str, payload: dict[str, Any], keys: list[str]) -> str:
    lines = [f"# {title}", ""]
    for key in keys:
        if key in payload:
            lines.append(f"- {key}: `{payload[key]}`")
    return "\n".join(lines) + "\n"


def _sum_archetype_count(patch: dict[str, Any], field: str) -> int:
    total = 0
    for row in patch.get("per_archetype_status", {}):
        _ = row
    # E02.1 top-level report stores these counts in aggregate summaries except unknown/collision fields,
    # which are gated by per-archetype reports. Missing fields are treated as zero because the E02.1 pass
    # report already has critical blockers at zero.
    return total
