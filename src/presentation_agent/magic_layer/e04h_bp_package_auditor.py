"""Audit E04H visual backplate transfer at PPTX package level."""

from __future__ import annotations

import json
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


CNVPR = ".//{http://schemas.openxmlformats.org/presentationml/2006/main}cNvPr"
PIC = ".//{http://schemas.openxmlformats.org/presentationml/2006/main}pic"


def inspect_pptx_visual_layers(pptx_path: str | Path) -> dict[str, Any]:
    """Return package-level counts that distinguish native chrome from picture media."""

    path = Path(pptx_path)
    object_names: list[str] = []
    media_parts: list[str] = []
    picture_object_count = 0
    backplate_object_names: list[str] = []
    slide_count = 0

    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            lower = name.lower()
            if lower.startswith("ppt/media/"):
                media_parts.append(name)
            if lower.startswith("ppt/slides/slide") and lower.endswith(".xml"):
                slide_count += 1
                root = ET.fromstring(archive.read(name))
                picture_object_count += len(root.findall(PIC))
                for element in root.findall(CNVPR):
                    object_name = element.attrib.get("name", "")
                    if object_name:
                        object_names.append(object_name)
                        if _is_backplate_name(object_name):
                            backplate_object_names.append(object_name)

    return {
        "schema_name": "pptx_visual_layer_inventory",
        "status": "passed" if path.exists() else "failed",
        "pptx_path": path.as_posix(),
        "slide_count": slide_count,
        "media_count": len(media_parts),
        "picture_object_count": picture_object_count,
        "visual_backplate_object_count": len(backplate_object_names),
        "media_parts": sorted(media_parts),
        "object_names": object_names,
        "visual_backplate_object_names": backplate_object_names,
        "canva_parity_claimed": False,
    }


def audit_visual_backplate_transfer(
    e03h_p2_root: str | Path,
    e04h_deck_path: str | Path,
    layout_report_path: str | Path,
) -> dict[str, Any]:
    """Audit whether E04H actually transferred selected E03H-P2 visual backplates."""

    root = Path(e03h_p2_root)
    selections = _read_json(Path(layout_report_path)).get("selections", [])
    source_inventory = inspect_pptx_visual_layers(e04h_deck_path)
    reference_pack = root / "editable_hybrid_reference_pack_svg_rebound.pptx"
    reference_pack_inventory = inspect_pptx_visual_layers(reference_pack)

    rows = []
    selected_with_backplates = 0
    for row in selections:
        reference_id = row["selected_reference_id"]
        candidate = root / "references" / reference_id / "editable_candidate.pptx"
        backplate_image = _backplate_image_for_reference(root, reference_id)
        reference_inventory = inspect_pptx_visual_layers(candidate)
        reference_has_backplate = (
            reference_inventory["media_count"] > 0
            or reference_inventory["picture_object_count"] > 0
            or backplate_image is not None
        )
        if reference_has_backplate:
            selected_with_backplates += 1
        rows.append(
            {
                "slide_id": row["slide_id"],
                "slide_number": row["slide_number"],
                "selected_reference_id": reference_id,
                "reference_candidate_path": candidate.as_posix(),
                "reference_media_count": reference_inventory["media_count"],
                "reference_picture_object_count": reference_inventory["picture_object_count"],
                "reference_backplate_image": backplate_image.as_posix() if backplate_image else None,
                "reference_has_backplate": reference_has_backplate,
                "e04h_backplate_transferred": False,
                "patch_required": reference_has_backplate,
            }
        )

    transfer_coverage = 0.0
    transfer_pass = (
        source_inventory["media_count"] > 0
        and source_inventory["picture_object_count"] > 0
        and transfer_coverage >= 0.75
    )
    return {
        "schema_name": "e04h_bp_visual_backplate_transfer_report",
        "status": "passed" if transfer_pass else "failed",
        "original_e04h_decision": "E04H_PASS_READY_FOR_E05_34_SLIDE_SCALEOUT_WITH_HYBRID_PACK",
        "source_binding_pass": True,
        "semantic_editability_pass": True,
        "svg_provenance_pass": True,
        "visual_backplate_transfer_pass": transfer_pass,
        "e05_unlocked": False,
        "next_required_stage": "E04H_BP_CLONE_BASED_REBINDING",
        "reference_pack_inventory": reference_pack_inventory,
        "e04h_source_deck_inventory": source_inventory,
        "selected_reference_count": len(selections),
        "selected_references_with_backplates": selected_with_backplates,
        "visual_backplate_transfer_coverage": transfer_coverage,
        "fail_reasons": _audit_fail_reasons(source_inventory, selected_with_backplates),
        "slide_transfer_rows": rows,
        "canva_parity_claimed": False,
    }


def build_e04h_bp_quality_override() -> dict[str, Any]:
    return {
        "schema_name": "e04h_bp_quality_override",
        "status": "blocked",
        "original_e04h_decision": "E04H_PASS_READY_FOR_E05_34_SLIDE_SCALEOUT_WITH_HYBRID_PACK",
        "source_binding_pass": True,
        "semantic_editability_pass": True,
        "svg_provenance_pass": True,
        "visual_backplate_transfer_pass": False,
        "e05_unlocked": False,
        "reason": "E04H source-bound deck package contains zero media files and zero picture objects, so the hybrid visual backplate transfer claim is not proven.",
        "next_required_stage": "E04H_BP_CLONE_BASED_REBINDING",
        "canva_parity_claimed": False,
    }


def _audit_fail_reasons(inventory: dict[str, Any], selected_with_backplates: int) -> list[str]:
    reasons = []
    if inventory["media_count"] == 0:
        reasons.append("source-bound deck media count is zero")
    if inventory["picture_object_count"] == 0:
        reasons.append("source-bound deck picture object count is zero")
    if selected_with_backplates and inventory["visual_backplate_object_count"] == 0:
        reasons.append("selected reference backplate groups are absent")
    if inventory["media_count"] == 0 and inventory["picture_object_count"] == 0:
        reasons.append("hybrid pack was used as layout tokens without transferring visual media")
    return reasons


def _backplate_image_for_reference(root: Path, reference_id: str) -> Path | None:
    reference_root = root / "references" / reference_id
    for name in ("backplate_overlay_preview.png", "rendered_candidate.png", "reference_image.png"):
        path = reference_root / name
        if path.exists():
            return path
    return None


def _is_backplate_name(name: str) -> bool:
    return bool(re.search(r"(visual_backplate|backplate|replaceable_visual_field)", name, re.IGNORECASE))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
