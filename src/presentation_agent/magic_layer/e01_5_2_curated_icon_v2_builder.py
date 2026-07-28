"""Build curated Magic Layer icon library v2 from render-audited v1 icons."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from .e01_5_1_procedural_svg_factory import procedural_svg_for_role
from .e01_5_1_svg_normalizer import normalize_svg_text, validate_svg_policy


def build_curated_icon_v2(
    *,
    v1_manifest: dict[str, Any],
    v1_audit: dict[str, Any],
    v2_root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    v2_root.mkdir(parents=True, exist_ok=True)
    audit_by_role = {record["role"]: record for record in v1_audit.get("records", [])}
    records = []
    normalization_records = []
    replacement_plan = []
    seen_roles: set[str] = set()
    duplicate_v1_roles: list[str] = []
    for record in v1_manifest.get("records", []):
        role = record["role"]
        if role in seen_roles:
            duplicate_v1_roles.append(role)
            continue
        seen_roles.add(role)
        audit = audit_by_role.get(role, {})
        target_svg = v2_root / f"{role}.svg"
        target_meta = v2_root / f"{role}.json"
        if audit.get("render_quality_status") == "passed":
            source_path = Path(record["svg_path"])
            shutil.copy2(source_path, target_svg)
            source_kind = record["source_kind"]
            replacement_reason = "v1_render_audit_passed"
        else:
            target_svg.write_text(normalize_svg_text(procedural_svg_for_role(role)), encoding="utf-8")
            source_kind = "generated_procedural_svg"
            replacement_reason = "v1_render_audit_failed_rebuilt_procedurally"
        svg_text = target_svg.read_text(encoding="utf-8", errors="ignore")
        policy = validate_svg_policy(svg_text)
        normalized_sha = hashlib.sha256(target_svg.read_bytes()).hexdigest()
        meta = {
            "role": role,
            "family": record.get("family"),
            "source_kind": source_kind,
            "source_path": record.get("svg_path"),
            "source_sha256": record.get("normalized_sha256") or record.get("source_sha256"),
            "normalized_sha256": normalized_sha,
            "viewBox": "0 0 24 24",
            "currentColor": "currentColor" in svg_text,
            "preferred_variant": record.get("preferred_variant", "outline"),
            "aliases": record.get("aliases", []),
            "search_keywords": record.get("search_keywords", []),
            "semantic_confidence": record.get("semantic_confidence", 0.84),
            "visual_style_notes": "v2 renderable glyph selected from audited v1 or deterministic vector fallback",
            "license_or_origin_note": "local_repo_asset",
            "created_by_stage": "E01.5.2",
            "policy_status": policy["policy_status"],
        }
        target_meta.write_text(json.dumps(meta, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
        records.append({**meta, "svg_path": target_svg.as_posix(), "metadata_path": target_meta.as_posix()})
        normalization_records.append(
            {
                "role": role,
                "target_path": target_svg.as_posix(),
                "normalized_sha256": normalized_sha,
                **policy,
            }
        )
        replacement_plan.append(
            {
                "role": role,
                "v1_svg_path": record.get("svg_path"),
                "v2_svg_path": target_svg.as_posix(),
                "decision": "reuse_v1" if replacement_reason == "v1_render_audit_passed" else "replace_with_procedural",
                "reason": replacement_reason,
                "generic_placeholder_allowed": False,
                "semantic_raster_allowed": False,
            }
        )
    coverage = {
        "schema_name": "curated_icon_v2_role_coverage_matrix",
        "status": "passed",
        "v2_role_count": len(records),
        "v1_role_count": len({record["role"] for record in v1_manifest.get("records", [])}),
        "v1_duplicate_role_count": len(duplicate_v1_roles),
        "v1_duplicate_roles": duplicate_v1_roles,
        "v2_role_coverage_gte_v1": len(records) >= len({record["role"] for record in v1_manifest.get("records", [])}),
        "covered_role_count": len(records),
        "rows": [
            {
                "role": record["role"],
                "covered": True,
                "source_kind": record["source_kind"],
                "svg_path": record["svg_path"],
            }
            for record in records
        ],
        "canva_parity_claimed": False,
    }
    manifest = {
        "schema_name": "curated_icon_v2_manifest",
        "status": "passed",
        "curated_root": v2_root.as_posix(),
        "v2_role_count": len(records),
        "v2_svg_count": len(records),
        "v1_unique_role_count": len({record["role"] for record in v1_manifest.get("records", [])}),
        "v1_duplicate_role_count": len(duplicate_v1_roles),
        "v1_svg_reused_count": sum(1 for item in replacement_plan if item["decision"] == "reuse_v1"),
        "v2_rebuilt_icon_count": sum(1 for item in replacement_plan if item["decision"] != "reuse_v1"),
        "records": records,
        "canva_parity_claimed": False,
    }
    normalization = {
        "schema_name": "curated_icon_v2_normalization_report",
        "status": "passed" if all(record["policy_status"] == "passed" for record in normalization_records) else "patch_required",
        "normalized_icon_count": len(normalization_records),
        "blank_or_invalid_svg_count": sum(1 for record in normalization_records if record["policy_status"] != "passed"),
        "text_element_count": sum(1 for record in normalization_records if record["contains_text"]),
        "raster_image_element_count": sum(1 for record in normalization_records if record["contains_image"]),
        "external_reference_count": sum(1 for record in normalization_records if record["contains_external_ref"]),
        "records": normalization_records,
        "observed_icon_replacement_plan": replacement_plan,
        "canva_parity_claimed": False,
    }
    return manifest, coverage, normalization
