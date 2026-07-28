"""Text-first lock contract for E01X.

Text proposals must be locked before downstream visual masks can consume their
regions. If OCR-capable adapters are unavailable, this module records that
unavailability and emits no recognized text.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schemas import validate_proposal
from .semantic_roles import is_text_role


def build_text_first_lock(
    *,
    reference_image_path: Path,
    output_dir: Path,
    ocr_proposals: list[dict[str, Any]],
    ocr_adapter_statuses: list[dict[str, Any]],
    text_bearing_reference: bool,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    real_text_proposals = [_validate_or_skip(proposal) for proposal in ocr_proposals]
    real_text_proposals = [
        proposal
        for proposal in real_text_proposals
        if proposal is not None
        and proposal.get("source_type") == "real_model"
        and proposal.get("gate_eligible") is True
        and _proposal_is_text_like(proposal)
    ]

    if not real_text_proposals:
        status = "unavailable"
        regions: list[dict[str, Any]] = []
        zones: list[dict[str, Any]] = []
    else:
        status = "passed"
        regions = [
            {
                "region_id": proposal["proposal_id"],
                "source_adapter": proposal["source_adapter"],
                "bbox_px": proposal["bbox_px"],
                "bbox_norm": proposal["bbox_norm"],
                "role_candidates": proposal["role_candidates"],
                "confidence": proposal["confidence"],
                "recognized_text": proposal.get("recognized_text"),
                "text_value_source": "real_model_ocr_or_region_evidence",
                "gate_eligible": True,
            }
            for proposal in real_text_proposals
        ]
        zones = [
            {
                "zone_id": f"LOCK_{region['region_id']}",
                "source_region_id": region["region_id"],
                "bbox_px": region["bbox_px"],
                "bbox_norm": region["bbox_norm"],
                "must_promote_to_ppt_text": True,
                "exclude_from_visual_masks": True,
                "exclude_from_raster_backplate": True,
                "overlap_violation_threshold": 0.05,
            }
            for region in regions
        ]

    ledger = {
        "schema_name": "text_region_ledger",
        "schema_version": "1.0",
        "status": status,
        "reference_image_path": str(reference_image_path),
        "text_bearing_reference": text_bearing_reference,
        "ocr_performed": bool(real_text_proposals),
        "recognized_text_faked": False,
        "regions": regions,
        "canva_parity_claimed": False,
    }
    protected = {
        "schema_name": "protected_text_zones",
        "schema_version": "1.0",
        "status": status,
        "zones": zones,
        "canva_parity_claimed": False,
    }
    report = {
        "schema_name": "text_first_lock_report",
        "schema_version": "1.0",
        "status": status,
        "reference_image_path": str(reference_image_path),
        "text_bearing_reference": text_bearing_reference,
        "ocr_adapter_statuses": ocr_adapter_statuses,
        "ocr_performed": bool(real_text_proposals),
        "recognized_text_faked": False,
        "text_region_count": len(regions),
        "protected_text_zone_count": len(zones),
        "quality_included_in_gate": True,
        "warnings": [] if status == "passed" else ["OCR/text-region adapters unavailable; no text was faked"],
        "canva_parity_claimed": False,
    }
    write_text_first_lock_outputs(output_dir, ledger, protected, report)
    return {"text_region_ledger": ledger, "protected_text_zones": protected, "report": report}


def write_text_first_lock_outputs(output_dir: Path, ledger: dict[str, Any], protected: dict[str, Any], report: dict[str, Any]) -> None:
    (output_dir / "text_region_ledger.json").write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "protected_text_zones.json").write_text(json.dumps(protected, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "text_first_lock_report.md").write_text(text_first_lock_markdown(report), encoding="utf-8")


def text_first_lock_markdown(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Text-First Lock Report",
            "",
            f"- Status: `{report['status']}`",
            f"- Text-bearing reference: `{report['text_bearing_reference']}`",
            f"- OCR performed: `{report['ocr_performed']}`",
            f"- Recognized text faked: `{report['recognized_text_faked']}`",
            f"- Text regions: `{report['text_region_count']}`",
            f"- Protected zones: `{report['protected_text_zone_count']}`",
            "- Canva parity claimed: `False`",
        ]
    ) + "\n"


def _validate_or_skip(proposal: dict[str, Any]) -> dict[str, Any] | None:
    try:
        return validate_proposal(proposal)
    except ValueError:
        return None


def _proposal_is_text_like(proposal: dict[str, Any]) -> bool:
    return any(is_text_role(candidate.get("role", "")) for candidate in proposal.get("role_candidates", []))
