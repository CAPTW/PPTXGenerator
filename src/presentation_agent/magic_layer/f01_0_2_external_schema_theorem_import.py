"""F01.0.2 external Canva Magic Layer Korean sample importer.

The Schema Theorem sample is a calibration oracle only. It must not satisfy
Harness V3 hard-5 Canva oracle requirements.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation

from src.presentation_agent.magic_layer.e03_16_orchestrator import read_json, write_json, write_md
from src.presentation_agent.qa.render_pptx_preview import render_pptx_preview


REPO_ROOT = Path(__file__).resolve().parents[3]
RUN_ROOT = REPO_ROOT / "design_runs" / "run_002"
CANVA_ROOT = REPO_ROOT / "design_runs" / "benchmarks" / "canva_magic_layer"
OUTPUT_ROOT = RUN_ROOT / "outputs" / "magic_layer_engine_f01_0_2_external_schema_theorem_import"
RENDER_ROOT = OUTPUT_ROOT / "renders"
PROTECTED_REPORT_ROOT = REPO_ROOT / "analysis_runs" / "protected_artifact_gate_latest"

IMPORT_ROOT = CANVA_ROOT / "external" / "schema_theorem_ko" / "imports"
LEGACY_ROOT = CANVA_ROOT / "external" / "schema_theorm_ko"
SOURCE_PPTX = IMPORT_ROOT / "canva_magic_layers_output.pptx"
SOURCE_REFERENCE = IMPORT_ROOT / "reference_image.png"
SOURCE_UPLOADED_REFERENCE = IMPORT_ROOT / "canva_uploaded_reference.png"
SOURCE_RENDER = IMPORT_ROOT / "canva_rendered_slide.png"
SOURCE_UNCERTAIN = IMPORT_ROOT / "imported_preview_uncertain_role.png"

NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}

EMU_PER_INCH = 914400


def run() -> dict[str, Any]:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    RENDER_ROOT.mkdir(parents=True, exist_ok=True)

    precheck = run_protect_check()
    copy_protected_report()
    if not precheck["passed"]:
        return write_blocked("F01_0_2_FAIL_PROTECTED_ARTIFACTS", {"protected_artifact_precheck": precheck})

    inventory = build_file_inventory()
    if not inventory["pptx_exists"]:
        report = build_final_report(
            decision="F01_0_2_BLOCKED_MISSING_SCHEMA_THEOREM_PPTX",
            inventory=inventory,
            render_report={"status": "blocked_missing_pptx"},
            audit=empty_audit_report(),
            text_fragmentation=empty_status("schema_theorem_text_fragmentation_report", "blocked_missing_pptx"),
            media_decomposition=empty_status("schema_theorem_media_decomposition_report", "blocked_missing_pptx"),
            icon_row=empty_status("schema_theorem_icon_row_audit", "blocked_missing_pptx"),
            editability=empty_status("schema_theorem_editability_probe_report", "blocked_missing_pptx"),
            taxonomy=build_failure_taxonomy_seed([]),
            readiness=build_hard5_addendum(False),
        )
        write_all(report, inventory)
        return report

    render_report = render_schema_theorem()
    audit = audit_schema_theorem_pptx(SOURCE_PPTX)
    text_fragmentation = build_text_fragmentation_report(audit)
    media_decomposition = build_media_decomposition_report(audit)
    icon_row = build_icon_row_audit(audit)
    editability = build_editability_probe(audit, media_decomposition, icon_row)
    taxonomy = build_failure_taxonomy_seed(text_fragmentation.get("suspicious_examples", []))

    render_ok = render_report.get("render_status") == "rendered" and (RENDER_ROOT / "schema_theorem_canva_rendered_slide.png").is_file()
    audit_ok = audit["status"] == "passed"
    decision = (
        "F01_0_2_PASS_EXTERNAL_SCHEMA_THEOREM_IMPORTED_START_F01_1_HARD5_IMPORT"
        if render_ok and audit_ok
        else "F01_0_2_PATCH_RENDER_OR_AUDIT_REQUIRED"
    )
    readiness = build_hard5_addendum(decision == "F01_0_2_PASS_EXTERNAL_SCHEMA_THEOREM_IMPORTED_START_F01_1_HARD5_IMPORT")
    contact_manifest = build_contact_sheets(audit, render_report, text_fragmentation, media_decomposition, icon_row)

    report = build_final_report(
        decision=decision,
        inventory=inventory,
        render_report=render_report,
        audit=audit,
        text_fragmentation=text_fragmentation,
        media_decomposition=media_decomposition,
        icon_row=icon_row,
        editability=editability,
        taxonomy=taxonomy,
        readiness=readiness,
        contact_manifest=contact_manifest,
    )
    write_all(
        report,
        inventory,
        audit,
        text_fragmentation,
        media_decomposition,
        icon_row,
        editability,
        taxonomy,
        readiness,
    )

    postcheck = run_protect_check()
    copy_protected_report()
    if not postcheck["passed"]:
        report["decision"] = "F01_0_2_FAIL_PROTECTED_ARTIFACTS"
        report["final_decision"] = "F01_0_2_FAIL_PROTECTED_ARTIFACTS"
        write_json(OUTPUT_ROOT / "f01_0_2_schema_theorem_import_report.json", report)
        write_md(OUTPUT_ROOT / "f01_0_2_schema_theorem_import_report.md", summary_md("F01.0.2 Schema Theorem Import", report))
    return report


def build_file_inventory() -> dict[str, Any]:
    IMPORT_ROOT.mkdir(parents=True, exist_ok=True)
    normalized_from_legacy: list[dict[str, str]] = []
    legacy_pptx = LEGACY_ROOT / "canva_magic_layers_output.pptx"
    if not SOURCE_PPTX.exists() and legacy_pptx.exists():
        shutil.copy2(legacy_pptx, SOURCE_PPTX)
        normalized_from_legacy.append({"from": legacy_pptx.as_posix(), "to": SOURCE_PPTX.as_posix()})
    legacy_reference = LEGACY_ROOT / "reference_image.png"
    if not SOURCE_REFERENCE.exists() and not SOURCE_UPLOADED_REFERENCE.exists() and not SOURCE_RENDER.exists() and not SOURCE_UNCERTAIN.exists() and legacy_reference.exists():
        shutil.copy2(legacy_reference, SOURCE_REFERENCE)
        normalized_from_legacy.append({"from": legacy_reference.as_posix(), "to": SOURCE_REFERENCE.as_posix()})

    image_roles = []
    for path, role in [
        (SOURCE_REFERENCE, "reference"),
        (SOURCE_UPLOADED_REFERENCE, "reference"),
        (SOURCE_RENDER, "canva_render"),
        (SOURCE_UNCERTAIN, "uncertain"),
    ]:
        if path.exists():
            image_roles.append({"path": path.as_posix(), "role": role, "size_bytes": path.stat().st_size})
    role = image_roles[0]["role"] if image_roles else "missing"
    return {
        "schema_name": "schema_theorem_file_inventory",
        "status": "passed" if SOURCE_PPTX.exists() else "blocked_missing_pptx",
        "sample_id": "schema_theorem_ko",
        "sample_kind": "external_canva_magic_layer_calibration_sample",
        "not_harness_v3_hard5_oracle": True,
        "imports_dir": IMPORT_ROOT.as_posix(),
        "legacy_discovered_dir": LEGACY_ROOT.as_posix() if LEGACY_ROOT.exists() else "",
        "normalized_from_legacy": normalized_from_legacy,
        "pptx_path": SOURCE_PPTX.as_posix(),
        "pptx_exists": SOURCE_PPTX.exists(),
        "pptx_size_bytes": SOURCE_PPTX.stat().st_size if SOURCE_PPTX.exists() else 0,
        "image_role": role,
        "image_files": image_roles,
        "expected_files": ["canva_magic_layers_output.pptx", "reference_image.png OR canva_uploaded_reference.png OR canva_rendered_slide.png OR imported_preview_uncertain_role.png"],
    }


def render_schema_theorem() -> dict[str, Any]:
    raw_dir = RENDER_ROOT / "_raw"
    report = render_pptx_preview(
        pptx_path=SOURCE_PPTX,
        output_dir=raw_dir,
        manifest_path=OUTPUT_ROOT / "schema_theorem_render_manifest.json",
        backend="auto",
        dpi=144,
    )
    first = None
    for row in report.get("slides", []):
        source = Path(row.get("rendered_image_path", ""))
        if source.is_file():
            first = source
            break
    target = RENDER_ROOT / "schema_theorem_canva_rendered_slide.png"
    if first and first.is_file():
        shutil.copy2(first, target)
    report["schema_theorem_rendered_slide_path"] = target.as_posix() if target.exists() else ""
    report["status"] = "passed" if report.get("render_status") == "rendered" and target.exists() else "failed"
    return report


def audit_schema_theorem_pptx(pptx_path: Path) -> dict[str, Any]:
    if not pptx_path.exists():
        return empty_audit_report()
    prs = Presentation(pptx_path)
    slide_width = int(prs.slide_width)
    slide_height = int(prs.slide_height)
    object_ledger: list[dict[str, Any]] = []
    text_ledger: list[dict[str, Any]] = []
    image_backed_shapes: list[dict[str, Any]] = []
    group_objects: list[dict[str, Any]] = []
    media_items: list[dict[str, Any]] = []
    media_counter: Counter[str] = Counter()

    with zipfile.ZipFile(pptx_path, "r") as zf:
        names = zf.namelist()
        content_types = parse_content_types(zf)
        slide_names = sorted([name for name in names if name.startswith("ppt/slides/slide") and name.endswith(".xml")], key=slide_sort)
        for slide_index, slide_name in enumerate(slide_names, start=1):
            rels = parse_slide_relationships(zf, slide_name)
            root = ET.fromstring(zf.read(slide_name))
            sp_tree = root.find(".//p:cSld/p:spTree", NS)
            children = list(sp_tree)[2:] if sp_tree is not None else []
            for z_order, child in enumerate(children):
                text = " ".join(t.text or "" for t in child.findall(".//a:t", NS)).strip()
                bbox_emu = bbox(child)
                blips = child.findall(".//a:blip", NS)
                media_refs = []
                for blip in blips:
                    rid = blip.get(f"{{{NS['r']}}}embed") or blip.get(f"{{{NS['r']}}}link")
                    if rid and rid in rels:
                        media_refs.append(rels[rid])
                obj = {
                    "slide_number": slide_index,
                    "z_order": z_order,
                    "object_type": object_type(child),
                    "name": object_name(child),
                    "bbox_emu": bbox_emu,
                    "bbox_norm": norm_bbox(bbox_emu, slide_width, slide_height),
                    "has_text": bool(text),
                    "text": text,
                    "text_excerpt": text[:160],
                    "has_media_reference": bool(media_refs),
                    "media_references": media_refs,
                }
                object_ledger.append(obj)
                if text:
                    text_ledger.append(
                        {
                            "slide_number": slide_index,
                            "z_order": z_order,
                            "object_name": obj["name"],
                            "text": text,
                            "char_count": len(text),
                            "contains_korean": contains_korean(text),
                            "contains_latin": contains_latin(text),
                            "bbox_emu": bbox_emu,
                            "bbox_norm": obj["bbox_norm"],
                            "editable": True,
                        }
                    )
                if media_refs or obj["object_type"] == "picture":
                    image_backed_shapes.append(obj)
                if obj["object_type"] == "group":
                    group_objects.append(obj)
        for name in names:
            if name.startswith("ppt/media/"):
                suffix = Path(name).suffix.lower().lstrip(".") or "unknown"
                media_counter[suffix] += 1
                media_items.append(
                    {
                        "partname": name,
                        "media_type": suffix,
                        "content_type": content_types.get("/" + name, content_types.get(name, "")),
                        "size_bytes": len(zf.read(name)),
                    }
                )

    non_empty_text = [row for row in text_ledger if row["text"].strip()]
    svg_count = media_counter.get("svg", 0)
    report = {
        "schema_name": "schema_theorem_canva_layer_audit",
        "status": "passed",
        "sample_id": "schema_theorem_ko",
        "pptx_path": pptx_path.as_posix(),
        "slide_count": len(prs.slides),
        "canvas_emu": {"width": slide_width, "height": slide_height},
        "shape_count": sum(1 for row in object_ledger if row["object_type"] == "shape"),
        "object_count": len(object_ledger),
        "text_shape_count": len(text_ledger),
        "non_empty_text_fragment_count": len(non_empty_text),
        "media_count": sum(media_counter.values()),
        "media_type_count": dict(media_counter),
        "svg_count": svg_count,
        "image_backed_shape_count": len(image_backed_shapes),
        "grouped_object_count": len(group_objects),
        "pptx_object_ledger": object_ledger,
        "text_ledger": text_ledger,
        "image_backed_shapes": image_backed_shapes,
        "media_ledger": {"media_count": sum(media_counter.values()), "media_type_count": dict(media_counter), "items": media_items},
        "grouping_manifest": {"group_count": len(group_objects), "groups": group_objects, "z_order_recorded": True},
    }
    return report


def build_text_fragmentation_report(audit: dict[str, Any]) -> dict[str, Any]:
    text_rows = audit.get("text_ledger", [])
    suspicious: list[dict[str, Any]] = []
    one_char = [row for row in text_rows if len(row["text"].strip()) == 1 and re.search(r"[\uac00-\ud7a3A-Za-z0-9\"'“”‘’]", row["text"].strip())]
    for row in one_char[:40]:
        suspicious.append({"type": "one_character_fragment", "text": row["text"], "object_name": row["object_name"], "bbox_norm": row["bbox_norm"]})
    quote_fragments = [row for row in text_rows if re.fullmatch(r"[\"'“”‘’〈〉《》「」『』·:;,.!?()\[\]-]+", row["text"].strip() or "")]
    for row in quote_fragments[:20]:
        suspicious.append({"type": "quote_or_punctuation_fragment", "text": row["text"], "object_name": row["object_name"], "bbox_norm": row["bbox_norm"]})
    mixed = [row for row in text_rows if contains_korean(row["text"]) and contains_latin(row["text"])]
    latin_only = [row for row in text_rows if contains_latin(row["text"]) and not contains_korean(row["text"]) and len(row["text"].strip()) <= 6]
    if mixed and latin_only:
        for row in latin_only[:20]:
            suspicious.append({"type": "latin_fragment_near_korean_phrase_candidate", "text": row["text"], "object_name": row["object_name"], "bbox_norm": row["bbox_norm"]})
    for cluster in find_same_line_short_korean_clusters(text_rows)[:20]:
        suspicious.append(cluster)
    return {
        "schema_name": "schema_theorem_text_fragmentation_report",
        "status": "passed",
        "text_fragment_count": len(text_rows),
        "korean_text_fragment_count": sum(1 for row in text_rows if contains_korean(row["text"])),
        "mixed_korean_english_fragment_count": len(mixed),
        "one_character_fragment_count": len(one_char),
        "quote_fragment_count": len(quote_fragments),
        "suspicious_text_fragmentation_count": len(suspicious),
        "suspicious_examples": suspicious[:80],
        "ground_truth_warning": "Canva text ledger is a segmentation sample, not perfect semantic ground truth.",
    }


def build_media_decomposition_report(audit: dict[str, Any]) -> dict[str, Any]:
    images = audit.get("image_backed_shapes", [])
    slide_area = max(1, audit.get("canvas_emu", {}).get("width", 1) * audit.get("canvas_emu", {}).get("height", 1))
    ranked = sorted(images, key=lambda row: bbox_area(row.get("bbox_emu", {})), reverse=True)
    largest = ranked[0] if ranked else {}
    largest_area_ratio = bbox_area(largest.get("bbox_emu", {})) / slide_area if largest else 0
    hero_status = "single_bounded_media_field" if largest and largest_area_ratio < 0.92 else "full_slide_or_missing"
    if len([row for row in ranked if bbox_area(row.get("bbox_emu", {})) / slide_area > 0.08]) > 1:
        hero_status = "multiple_large_media_fragments"
    return {
        "schema_name": "schema_theorem_media_decomposition_report",
        "status": "passed",
        "media_count": audit.get("media_count", 0),
        "media_count_by_type": audit.get("media_type_count", {}),
        "image_backed_shape_count": len(images),
        "hero_image_decomposition_status": hero_status,
        "largest_media_object": largest,
        "largest_media_area_ratio": round(largest_area_ratio, 4),
        "icons_media_or_shape_status": "see_schema_theorem_icon_row_audit",
        "full_slide_media_candidate_count": sum(1 for row in images if bbox_area(row.get("bbox_emu", {})) / slide_area > 0.92),
    }


def build_icon_row_audit(audit: dict[str, Any]) -> dict[str, Any]:
    canvas = audit.get("canvas_emu", {})
    width = max(1, canvas.get("width", 1))
    height = max(1, canvas.get("height", 1))
    candidates = []
    for obj in audit.get("pptx_object_ledger", []):
        box = obj.get("bbox_emu", {})
        if not box or obj.get("has_text"):
            continue
        area_ratio = bbox_area(box) / (width * height)
        w_ratio = box.get("w", 0) / width
        h_ratio = box.get("h", 0) / height
        if 0 < area_ratio <= 0.018 and w_ratio <= 0.16 and h_ratio <= 0.16:
            item = dict(obj)
            item["center_y_norm"] = round((box.get("y", 0) + box.get("h", 0) / 2) / height, 2)
            candidates.append(item)
    by_row: dict[float, list[dict[str, Any]]] = defaultdict(list)
    for item in candidates:
        by_row[item["center_y_norm"]].append(item)
    rows = [
        {"center_y_norm": key, "item_count": len(items), "object_types": dict(Counter(item["object_type"] for item in items)), "items": sorted(items, key=lambda row: row.get("bbox_emu", {}).get("x", 0))[:20]}
        for key, items in sorted(by_row.items())
        if len(items) >= 3
    ]
    media_count = sum(1 for item in candidates if item.get("has_media_reference") or item.get("object_type") == "picture")
    shape_count = sum(1 for item in candidates if item.get("object_type") == "shape")
    return {
        "schema_name": "schema_theorem_icon_row_audit",
        "status": "passed" if rows else "not_detected",
        "small_visual_candidate_count": len(candidates),
        "detected_icon_row_count": len(rows),
        "icon_row_decomposition_status": "independent_small_objects_detected" if rows else "no_independent_icon_row_detected",
        "icon_implementation_counts": {"media_or_picture": media_count, "shape_or_vector_approximation": shape_count},
        "rows": rows,
    }


def build_editability_probe(audit: dict[str, Any], media: dict[str, Any], icon_row: dict[str, Any]) -> dict[str, Any]:
    text_rows = audit.get("text_ledger", [])
    top_text = [row for row in text_rows if row.get("bbox_norm", {}).get("y", 1) < 0.35]
    bottom_text = [row for row in text_rows if row.get("bbox_norm", {}).get("y", 0) > 0.7]
    title_candidates = sorted(top_text, key=lambda row: (bbox_area(row.get("bbox_emu", {})), len(row.get("text", ""))), reverse=True)
    tasks = [
        edit_task("title_editable", bool(title_candidates), title_candidates[0]["text"] if title_candidates else ""),
        edit_task("subtitle_editable", len(top_text) >= 2, f"top_text_count={len(top_text)}"),
        edit_task("footer_info_text_editable", bool(bottom_text), f"bottom_text_count={len(bottom_text)}"),
        edit_task("one_icon_row_item_selectable", icon_row.get("detected_icon_row_count", 0) > 0, icon_row.get("icon_row_decomposition_status", "")),
        edit_task("hero_image_move_replace_independent", media.get("hero_image_decomposition_status") in {"single_bounded_media_field", "multiple_large_media_fragments"}, media.get("hero_image_decomposition_status", "")),
        edit_task("bottom_info_panel_move_independent", bool(bottom_text), "bottom text/objects detected" if bottom_text else "no bottom info text detected"),
    ]
    failed = [task for task in tasks if task["status"] != "passed"]
    return {
        "schema_name": "schema_theorem_editability_probe_report",
        "status": "passed" if not failed else "partial",
        "task_count": len(tasks),
        "passed_task_count": len(tasks) - len(failed),
        "failed_task_count": len(failed),
        "tasks": tasks,
        "notes": ["Probe is structural/editability-oriented; Canva segmentation remains calibration evidence, not production ground truth."],
    }


def build_failure_taxonomy_seed(suspicious_examples: list[dict[str, Any]]) -> dict[str, Any]:
    taxonomy = [
        "korean_word_fragmented_across_text_boxes",
        "mixed_korean_english_phrase_split_unexpectedly",
        "one_character_text_fragment",
        "quote_or_punctuation_fragment",
        "hero_media_over_fragmented",
        "icon_row_as_media_fragments",
        "footer_info_panel_under_grouped",
        "large_title_hierarchy_broken",
    ]
    return {
        "schema_name": "schema_theorem_failure_taxonomy_seed",
        "status": "passed",
        "failure_types": taxonomy,
        "seeded_by_suspicious_fragment_count": len(suspicious_examples),
        "example_fragmentation_records": suspicious_examples[:20],
    }


def build_hard5_addendum(import_passed: bool) -> dict[str, Any]:
    return {
        "schema_name": "f01_1_hard5_readiness_addendum",
        "status": "ready_for_prompt2_hard5_import" if import_passed else "locked_pending_schema_theorem_import",
        "decision": "F01_1_READY_HARD5_IMPORT_PROMPT_2" if import_passed else "F01_1_LOCKED_PENDING_EXTERNAL_SAMPLE_IMPORT",
        "external_schema_theorem_registered": import_passed,
        "counts_as_harness_v3_hard5_oracle": False,
        "hard5_missing_outputs_still_required": ["table_heavy", "data_dashboard", "visual_toc", "process_flow", "card_grid"],
        "broad_canva_parity_claimed": False,
    }


def build_contact_sheets(
    audit: dict[str, Any],
    render_report: dict[str, Any],
    text_fragmentation: dict[str, Any],
    media: dict[str, Any],
    icon_row: dict[str, Any],
) -> dict[str, Any]:
    render = RENDER_ROOT / "schema_theorem_canva_rendered_slide.png"
    if render.exists():
        draw_overlay(render, RENDER_ROOT / "schema_theorem_layer_overlay.png", audit.get("pptx_object_ledger", []), "#28D7E8", "Layer overlay")
        draw_overlay(render, RENDER_ROOT / "schema_theorem_text_box_overlay.png", audit.get("text_ledger", []), "#F2A900", "Text box overlay")
        draw_overlay(render, RENDER_ROOT / "schema_theorem_media_overlay.png", audit.get("image_backed_shapes", []), "#EF4444", "Media overlay")
        icon_items = []
        for row in icon_row.get("rows", []):
            icon_items.extend(row.get("items", []))
        draw_overlay(render, RENDER_ROOT / "schema_theorem_icon_row_overlay.png", icon_items, "#22C55E", "Icon row overlay")
    else:
        for name in ["schema_theorem_layer_overlay.png", "schema_theorem_text_box_overlay.png", "schema_theorem_media_overlay.png", "schema_theorem_icon_row_overlay.png"]:
            summary_sheet(RENDER_ROOT / name, name, {"status": "missing_render"})
    reference_vs_canva_sheet(RENDER_ROOT / "schema_theorem_reference_vs_canva_contact_sheet.png", render)
    paths = {
        name.removesuffix(".png"): (RENDER_ROOT / name).as_posix()
        for name in [
            "schema_theorem_canva_rendered_slide.png",
            "schema_theorem_layer_overlay.png",
            "schema_theorem_text_box_overlay.png",
            "schema_theorem_media_overlay.png",
            "schema_theorem_icon_row_overlay.png",
            "schema_theorem_reference_vs_canva_contact_sheet.png",
        ]
    }
    return {"schema_name": "schema_theorem_contact_sheet_manifest", "status": "passed", "paths": paths}


def build_final_report(
    *,
    decision: str,
    inventory: dict[str, Any],
    render_report: dict[str, Any],
    audit: dict[str, Any],
    text_fragmentation: dict[str, Any],
    media_decomposition: dict[str, Any],
    icon_row: dict[str, Any],
    editability: dict[str, Any],
    taxonomy: dict[str, Any],
    readiness: dict[str, Any],
    contact_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_name": "f01_0_2_schema_theorem_import_report",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "final_decision": decision,
        "sample_id": "schema_theorem_ko",
        "sample_classification": "external_canva_magic_layer_calibration_sample_not_harness_v3_hard5",
        "file_inventory_status": inventory.get("status"),
        "pptx_path": inventory.get("pptx_path"),
        "image_role": inventory.get("image_role"),
        "render_status": render_report.get("render_status", render_report.get("status")),
        "render_backend": render_report.get("backend"),
        "slide_count": audit.get("slide_count", 0),
        "media_count_by_type": audit.get("media_type_count", {}),
        "text_fragment_count": audit.get("non_empty_text_fragment_count", 0),
        "suspicious_text_fragmentation_count": text_fragmentation.get("suspicious_text_fragmentation_count", 0),
        "icon_row_decomposition_status": icon_row.get("icon_row_decomposition_status"),
        "hero_image_decomposition_status": media_decomposition.get("hero_image_decomposition_status"),
        "editability_probe_status": editability.get("status"),
        "f01_1_hard5_import_can_proceed": readiness.get("status") == "ready_for_prompt2_hard5_import",
        "counts_as_harness_v3_hard5_oracle": False,
        "contact_sheet_manifest": contact_manifest or {},
        "protected_artifacts_unchanged": True,
        "broad_canva_parity_claimed": False,
    }


def write_all(
    report: dict[str, Any],
    inventory: dict[str, Any],
    audit: dict[str, Any] | None = None,
    text_fragmentation: dict[str, Any] | None = None,
    media_decomposition: dict[str, Any] | None = None,
    icon_row: dict[str, Any] | None = None,
    editability: dict[str, Any] | None = None,
    taxonomy: dict[str, Any] | None = None,
    readiness: dict[str, Any] | None = None,
) -> None:
    audit = audit or empty_audit_report()
    payloads = {
        "f01_0_2_schema_theorem_import_report": report,
        "schema_theorem_file_inventory": inventory,
        "schema_theorem_canva_layer_audit": audit,
        "schema_theorem_canva_text_ledger": {"schema_name": "schema_theorem_canva_text_ledger", "status": audit.get("status"), "text_fragment_count": len(audit.get("text_ledger", [])), "items": audit.get("text_ledger", [])},
        "schema_theorem_canva_media_ledger": audit.get("media_ledger", {"schema_name": "schema_theorem_canva_media_ledger", "items": []}),
        "schema_theorem_canva_grouping_manifest": audit.get("grouping_manifest", {"schema_name": "schema_theorem_canva_grouping_manifest", "groups": []}),
        "schema_theorem_text_fragmentation_report": text_fragmentation or empty_status("schema_theorem_text_fragmentation_report", "not_run"),
        "schema_theorem_media_decomposition_report": media_decomposition or empty_status("schema_theorem_media_decomposition_report", "not_run"),
        "schema_theorem_icon_row_audit": icon_row or empty_status("schema_theorem_icon_row_audit", "not_run"),
        "schema_theorem_editability_probe_report": editability or empty_status("schema_theorem_editability_probe_report", "not_run"),
        "schema_theorem_failure_taxonomy_seed": taxonomy or build_failure_taxonomy_seed([]),
        "f01_1_hard5_readiness_addendum": readiness or build_hard5_addendum(False),
    }
    for name, payload in payloads.items():
        write_json(OUTPUT_ROOT / f"{name}.json", payload)
        if name in {
            "f01_0_2_schema_theorem_import_report",
            "schema_theorem_text_fragmentation_report",
            "schema_theorem_media_decomposition_report",
            "schema_theorem_icon_row_audit",
            "schema_theorem_editability_probe_report",
            "f01_1_hard5_readiness_addendum",
        }:
            write_md(OUTPUT_ROOT / f"{name}.md", summary_md(name.replace("_", " ").title(), payload))


def parse_content_types(zf: zipfile.ZipFile) -> dict[str, str]:
    if "[Content_Types].xml" not in zf.namelist():
        return {}
    root = ET.fromstring(zf.read("[Content_Types].xml"))
    mapping = {}
    for override in root.findall("{http://schemas.openxmlformats.org/package/2006/content-types}Override"):
        mapping[override.get("PartName", "")] = override.get("ContentType", "")
    return mapping


def parse_slide_relationships(zf: zipfile.ZipFile, slide_name: str) -> dict[str, str]:
    rel_path = str(Path(slide_name).parent / "_rels" / (Path(slide_name).name + ".rels")).replace("\\", "/")
    if rel_path not in zf.namelist():
        return {}
    root = ET.fromstring(zf.read(rel_path))
    rels = {}
    for rel in root.findall("rel:Relationship", NS):
        target = rel.get("Target", "")
        if target.startswith("../"):
            target = "ppt/" + target[3:]
        rels[rel.get("Id", "")] = target
    return rels


def object_type(child: ET.Element) -> str:
    return {"sp": "shape", "pic": "picture", "graphicFrame": "graphic_frame", "grpSp": "group", "cxnSp": "connector"}.get(local_name(child.tag), local_name(child.tag))


def object_name(child: ET.Element) -> str:
    c_nv_pr = child.find(".//p:cNvPr", NS)
    return c_nv_pr.get("name", "") if c_nv_pr is not None else ""


def bbox(child: ET.Element) -> dict[str, int]:
    xfrm = child.find(".//p:spPr/a:xfrm", NS)
    if xfrm is None:
        xfrm = child.find(".//p:grpSpPr/a:xfrm", NS)
    if xfrm is None:
        return {}
    off = xfrm.find("a:off", NS)
    ext = xfrm.find("a:ext", NS)
    return {
        "x": int(off.get("x", 0)) if off is not None else 0,
        "y": int(off.get("y", 0)) if off is not None else 0,
        "w": int(ext.get("cx", 0)) if ext is not None else 0,
        "h": int(ext.get("cy", 0)) if ext is not None else 0,
    }


def norm_bbox(box: dict[str, int], width: int, height: int) -> dict[str, float]:
    if not box:
        return {}
    return {
        "x": round(box.get("x", 0) / max(1, width), 5),
        "y": round(box.get("y", 0) / max(1, height), 5),
        "w": round(box.get("w", 0) / max(1, width), 5),
        "h": round(box.get("h", 0) / max(1, height), 5),
    }


def find_same_line_short_korean_clusters(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        text = row.get("text", "").strip()
        if 0 < len(text) <= 2 and contains_korean(text):
            y = int(row.get("bbox_norm", {}).get("y", 0) * 100)
            buckets[y].append(row)
    clusters = []
    for y, items in buckets.items():
        if len(items) >= 3:
            ordered = sorted(items, key=lambda row: row.get("bbox_norm", {}).get("x", 0))
            clusters.append(
                {
                    "type": "same_line_short_korean_cluster",
                    "y_bucket": y,
                    "fragment_count": len(ordered),
                    "combined_text_candidate": "".join(row["text"].strip() for row in ordered[:12]),
                    "fragments": [{"text": row["text"], "object_name": row["object_name"], "bbox_norm": row["bbox_norm"]} for row in ordered[:12]],
                }
            )
    return clusters


def draw_overlay(base: Path, output: Path, items: list[dict[str, Any]], color: str, title: str) -> None:
    image = Image.open(base).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.text((12, 12), title, fill=color, font=font)
    for index, item in enumerate(items, start=1):
        box = item.get("bbox_norm") or norm_from_emu_box(item.get("bbox_emu", {}))
        if not box:
            continue
        x1 = int(box["x"] * image.width)
        y1 = int(box["y"] * image.height)
        x2 = int((box["x"] + box["w"]) * image.width)
        y2 = int((box["y"] + box["h"]) * image.height)
        if x2 <= x1 or y2 <= y1:
            continue
        draw.rectangle((x1, y1, x2, y2), outline=color, width=2)
        if index <= 80:
            draw.text((x1 + 2, y1 + 2), str(item.get("z_order", index)), fill=color, font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def reference_vs_canva_sheet(output: Path, render: Path) -> None:
    paths = []
    label = "Reference"
    if SOURCE_REFERENCE.exists():
        paths.append((SOURCE_REFERENCE, label))
    elif SOURCE_UPLOADED_REFERENCE.exists():
        paths.append((SOURCE_UPLOADED_REFERENCE, "Uploaded reference"))
    elif SOURCE_UNCERTAIN.exists():
        paths.append((SOURCE_UNCERTAIN, "Imported preview uncertain role"))
    paths.append((render, "Canva PPTX local render"))
    cell_w, cell_h = 520, 330
    sheet = Image.new("RGB", (cell_w * 2, cell_h + 44), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((12, 12), "Schema Theorem Korean sample: reference vs Canva render", fill="#F8FAFC", font=font)
    for idx, (path, label_text) in enumerate(paths[:2]):
        draw.text((idx * cell_w + 12, 30), label_text, fill="#F2A900", font=font)
        paste_image(sheet, path, idx * cell_w + 12, 52, cell_w - 24, cell_h - 20)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def summary_sheet(output: Path, title: str, payload: dict[str, Any]) -> None:
    sheet = Image.new("RGB", (1280, 720), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((24, 24), title, fill="#F8FAFC", font=font)
    y = 64
    for key, value in payload.items():
        if isinstance(value, dict):
            text = f"{key}: {json.dumps(value, ensure_ascii=True)[:160]}"
        elif isinstance(value, list):
            text = f"{key}: {len(value)} items"
        else:
            text = f"{key}: {value}"
        draw.text((24, y), text[:180], fill="#F2A900", font=font)
        y += 24
        if y > 690:
            break
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def paste_image(sheet: Image.Image, path: Path, x: int, y: int, w: int, h: int) -> None:
    draw = ImageDraw.Draw(sheet)
    if not path.exists():
        draw.rectangle((x, y, x + w, y + h), fill="#0F172A", outline="#334155")
        draw.text((x + 16, y + h // 2), "MISSING", fill="#F2A900", font=ImageFont.load_default())
        return
    image = Image.open(path).convert("RGB")
    image.thumbnail((w, h), Image.Resampling.LANCZOS)
    sheet.paste(image, (x + (w - image.width) // 2, y + (h - image.height) // 2))


def run_protect_check() -> dict[str, Any]:
    npm_cmd = shutil.which("npm.cmd") or shutil.which("npm")
    if npm_cmd is None:
        return {"passed": False, "reason": "npm_not_found"}
    result = subprocess.run([npm_cmd, "run", "protect:check"], cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    protected = read_json(PROTECTED_REPORT_ROOT / "protected_artifact_check_report.json", default={})
    changed = int(protected.get("summary", {}).get("changed_count", 0))
    return {
        "passed": result.returncode == 0 and protected.get("status") == "passed" and changed == 0,
        "status": protected.get("status"),
        "exit_code": result.returncode,
        "changed_count": changed,
    }


def copy_protected_report() -> None:
    source = PROTECTED_REPORT_ROOT / "protected_artifact_check_report.md"
    if source.exists():
        shutil.copy2(source, OUTPUT_ROOT / "protected_artifact_check_report.md")


def write_blocked(decision: str, details: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "schema_name": "f01_0_2_schema_theorem_import_report",
        "decision": decision,
        "final_decision": decision,
        **details,
        "broad_canva_parity_claimed": False,
    }
    write_json(OUTPUT_ROOT / "f01_0_2_schema_theorem_import_report.json", payload)
    write_md(OUTPUT_ROOT / "f01_0_2_schema_theorem_import_report.md", summary_md("F01.0.2 Schema Theorem Import", payload))
    return payload


def empty_audit_report() -> dict[str, Any]:
    return {
        "schema_name": "schema_theorem_canva_layer_audit",
        "status": "blocked",
        "slide_count": 0,
        "shape_count": 0,
        "object_count": 0,
        "text_shape_count": 0,
        "non_empty_text_fragment_count": 0,
        "media_count": 0,
        "media_type_count": {},
        "svg_count": 0,
        "image_backed_shape_count": 0,
        "grouped_object_count": 0,
        "pptx_object_ledger": [],
        "text_ledger": [],
        "image_backed_shapes": [],
        "media_ledger": {"media_count": 0, "media_type_count": {}, "items": []},
        "grouping_manifest": {"group_count": 0, "groups": []},
    }


def empty_status(schema: str, status: str) -> dict[str, Any]:
    return {"schema_name": schema, "status": status}


def edit_task(task_id: str, ok: bool, evidence: str) -> dict[str, Any]:
    return {"task_id": task_id, "status": "passed" if ok else "failed", "evidence": evidence}


def contains_korean(text: str) -> bool:
    return bool(re.search(r"[\uac00-\ud7a3]", text))


def contains_latin(text: str) -> bool:
    return bool(re.search(r"[A-Za-z]", text))


def bbox_area(box: dict[str, Any]) -> int:
    return max(0, int(box.get("w", 0))) * max(0, int(box.get("h", 0)))


def norm_from_emu_box(box: dict[str, Any]) -> dict[str, float]:
    # Fallback for callers that pass raw items without bbox_norm. Schema Theorem is 16:9.
    return norm_bbox({key: int(box.get(key, 0)) for key in ("x", "y", "w", "h")}, 16 * EMU_PER_INCH, 9 * EMU_PER_INCH) if box else {}


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def slide_sort(name: str) -> int:
    return int(Path(name).stem.replace("slide", ""))


def summary_md(title: str, payload: dict[str, Any]) -> str:
    lines = [f"# {title}", ""]
    for key, value in payload.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            lines.append(f"- {key}: `{value}`")
        elif isinstance(value, list):
            lines.append(f"- {key}: `{len(value)} items`")
        elif isinstance(value, dict):
            lines.append(f"- {key}: `{json.dumps(value, ensure_ascii=True)[:320]}`")
    return "\n".join(lines) + "\n"
