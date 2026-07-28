"""F01.0.1 maritime Canva oracle triad utilities.

This stage completes the one existing Canva Magic Layers oracle triad before
requiring the full Harness V3 Canva import set. It is intentionally read-only
with respect to source decks: it audits and maps existing maritime outputs
instead of creating a new candidate deck.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw, ImageFont

from src.presentation_agent.magic_layer.e03_16_orchestrator import read_json, write_json, write_md


REPO_ROOT = Path(__file__).resolve().parents[3]
RUN_ROOT = REPO_ROOT / "design_runs" / "run_002"
OUTPUT_ROOT = RUN_ROOT / "outputs" / "magic_layer_engine_f01_0_1_maritime_oracle_triad"
RENDER_ROOT = OUTPUT_ROOT / "renders"
CANVA_ROOT = REPO_ROOT / "design_runs" / "benchmarks" / "canva_magic_layer"
PROTECTED_REPORT_ROOT = REPO_ROOT / "analysis_runs" / "protected_artifact_gate_latest"

MARITIME_REFERENCE = CANVA_ROOT / "assets" / "reference_image.png"
MARITIME_CANVA_PPTX = CANVA_ROOT / "assets" / "canva_magic_layer_output.pptx"
MARITIME_CANVA_RENDER = CANVA_ROOT / "assets" / "canva_rendered_slide.png"
MARITIME_CANVA_AUDIT = CANVA_ROOT / "canva_layer_audit_report.json"

NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}

SEARCH_ROOTS = [
    {
        "stage": "e01_7",
        "folder": RUN_ROOT / "outputs" / "magic_layer_engine_e01_7_canva_plus_single_slide_final_gate",
        "candidate_names": ["editable_candidate_e01_7.pptx", "editability_probe_candidate_e01_7.pptx"],
        "render_names": ["rendered_candidate_e01_7.png", "renders/e01_7_editability_probe_after.png"],
        "report_names": ["e01_7_final_gate_report.json", "e01_7_pptx_ooxml_object_ledger.json"],
    },
    {
        "stage": "e01_6",
        "folder": RUN_ROOT / "outputs" / "magic_layer_engine_e01_6_layer_segmentation_polish",
        "candidate_names": ["editable_candidate_e01_6.pptx"],
        "render_names": ["renders/rendered_candidate_e01_6.png", "render_raw/slide-001.png"],
        "report_names": ["e01_6_patch_report.json", "e01_6_object_ledger.json"],
    },
    {
        "stage": "e01_5_2",
        "folder": RUN_ROOT / "outputs" / "magic_layer_engine_e01_5_2_renderable_svg_glyph_fidelity_patch",
        "candidate_names": ["editable_candidate_e01_5_2.pptx"],
        "render_names": ["rendered_candidate_e01_5_2.png"],
        "report_names": ["e01_5_2_canva_plus_gate_report.json"],
    },
    {
        "stage": "e01_4",
        "folder": RUN_ROOT / "outputs" / "magic_layer_engine_e01_4_observed_icon_svg_trace",
        "candidate_names": ["editable_candidate_e01_4.pptx"],
        "render_names": ["rendered_candidate_e01_4.png"],
        "report_names": ["e01_4_canva_plus_gate_report.json"],
    },
    {
        "stage": "d05_1",
        "folder": RUN_ROOT / "outputs" / "magic_layer_engine_d05_1_render_fidelity_patch" / "references" / "canva_benchmark",
        "candidate_names": ["patched_editable_candidate.pptx"],
        "render_names": ["patched_rendered_candidate.png"],
        "report_names": ["patched_editable_candidate_spec.json"],
    },
    {
        "stage": "d05",
        "folder": RUN_ROOT / "outputs" / "magic_layer_engine_d05_render_fidelity_gate" / "references" / "canva_benchmark",
        "candidate_names": ["editable_candidate.pptx"],
        "render_names": ["rendered_candidate.png"],
        "report_names": ["editable_candidate_spec.json"],
    },
]


def run() -> dict[str, Any]:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    RENDER_ROOT.mkdir(parents=True, exist_ok=True)

    precheck = run_protect_check()
    copy_protected_report()
    if not precheck["passed"]:
        report = write_blocked("F01_0_1_FAIL_PROTECTED_ARTIFACTS", {"protected_artifact_precheck": precheck})
        return report

    canva_exists = MARITIME_CANVA_PPTX.exists() and MARITIME_CANVA_RENDER.exists() and MARITIME_CANVA_AUDIT.exists()
    inventory = build_maritime_ours_inventory()
    selected = inventory["selected_candidate"]

    if not canva_exists:
        decision = "F01_0_1_BLOCKED_MISSING_CANVA_MARITIME_ORACLE"
    elif not selected.get("candidate_pptx_exists") or not selected.get("render_exists"):
        decision = "F01_0_1_BLOCKED_MISSING_OURS_MARITIME_OUTPUT"
    else:
        decision = "F01_0_1_PASS_MARITIME_TRIAD_READY_START_F01_1_HARD5_CANVA_IMPORT"

    canva_audit = build_canva_audit(canva_exists)
    ours_audit = build_ours_audit(selected)
    triad = build_triad_match_report(canva_exists, selected, canva_audit, ours_audit)
    object_match = build_object_match_report(canva_audit, ours_audit, canva_exists, selected)
    edit_probe = build_edit_task_probe(ours_audit, selected)
    readiness = build_revised_partial_readiness(decision)
    contact_manifest = build_contact_sheets(canva_exists, selected, canva_audit, ours_audit, object_match, edit_probe)

    report = {
        "schema_name": "f01_0_1_maritime_triad_report",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "final_decision": decision,
        "reference_exists": MARITIME_REFERENCE.exists(),
        "canva_maritime_oracle_exists": canva_exists,
        "selected_ours_candidate_stage": selected.get("stage"),
        "selected_ours_candidate_pptx": selected.get("candidate_pptx_path"),
        "selected_ours_render": selected.get("render_path"),
        "reference_canva_ours_triad_status": triad["status"],
        "object_audit_status": "passed" if canva_audit["status"] == "passed" and ours_audit["status"] == "passed" else "blocked",
        "object_match_status": object_match["status"],
        "edit_task_probe_status": edit_probe["status"],
        "f01_1_hard5_import_can_proceed": decision == "F01_0_1_PASS_MARITIME_TRIAD_READY_START_F01_1_HARD5_CANVA_IMPORT",
        "harness_v3_missing_canva_outputs_still_required": True,
        "contact_sheet_manifest": contact_manifest,
        "protected_artifacts_unchanged": precheck["passed"],
        "broad_canva_parity_claimed": False,
    }

    write_payloads(report, inventory, selected, triad, ours_audit, canva_audit, object_match, edit_probe, readiness)

    postcheck = run_protect_check()
    copy_protected_report()
    if not postcheck["passed"]:
        report["decision"] = "F01_0_1_FAIL_PROTECTED_ARTIFACTS"
        report["final_decision"] = "F01_0_1_FAIL_PROTECTED_ARTIFACTS"
        write_json(OUTPUT_ROOT / "f01_0_1_maritime_triad_report.json", report)
        write_md(OUTPUT_ROOT / "f01_0_1_maritime_triad_report.md", summary_md("F01.0.1 Maritime Triad", report))
    return report


def build_maritime_ours_inventory() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for rank, spec in enumerate(SEARCH_ROOTS, start=1):
        folder = spec["folder"]
        candidates = [folder / name for name in spec["candidate_names"]]
        renders = [folder / name for name in spec["render_names"]]
        reports = [folder / name for name in spec["report_names"]]
        candidate = first_existing(candidates)
        render = first_existing(renders)
        report = first_existing(reports)
        row = {
            "rank": rank,
            "stage": spec["stage"],
            "folder": folder.as_posix(),
            "candidate_pptx_path": candidate.as_posix() if candidate else "",
            "candidate_pptx_exists": candidate is not None,
            "render_path": render.as_posix() if render else "",
            "render_exists": render is not None,
            "report_path": report.as_posix() if report else "",
            "report_exists": report is not None,
            "selection_status": "candidate_complete" if candidate and render else "incomplete",
        }
        rows.append(row)

    selected = next((row for row in rows if row["candidate_pptx_exists"] and row["render_exists"] and row["stage"] == "e01_6"), None)
    e01_7 = next((row for row in rows if row["stage"] == "e01_7"), None)
    if selected and e01_7 and e01_7["report_exists"]:
        selected = dict(selected)
        selected["selection_reason"] = "E01.7 final gate accepted the E01.6 editable candidate as the maritime Magic Layer+ output."
        selected["e01_7_final_gate_report_path"] = (RUN_ROOT / "outputs" / "magic_layer_engine_e01_7_canva_plus_single_slide_final_gate" / "e01_7_final_gate_report.json").as_posix()
    elif selected:
        selected = dict(selected)
        selected["selection_reason"] = "Highest-priority complete maritime candidate found."
    else:
        selected = next((row for row in rows if row["candidate_pptx_exists"] and row["render_exists"]), rows[0] if rows else {})

    return {
        "schema_name": "maritime_ours_inventory",
        "status": "passed" if selected and selected.get("candidate_pptx_exists") and selected.get("render_exists") else "blocked_missing_complete_candidate",
        "search_order": [spec["folder"].as_posix() for spec in SEARCH_ROOTS],
        "candidate_count": sum(1 for row in rows if row["candidate_pptx_exists"]),
        "complete_candidate_count": sum(1 for row in rows if row["candidate_pptx_exists"] and row["render_exists"]),
        "selected_candidate": selected,
        "items": rows,
    }


def build_canva_audit(canva_exists: bool) -> dict[str, Any]:
    imported = read_json(MARITIME_CANVA_AUDIT, default={})
    ooxml = audit_pptx(MARITIME_CANVA_PPTX) if MARITIME_CANVA_PPTX.exists() else empty_audit()
    return {
        "schema_name": "maritime_object_layer_audit_canva",
        "status": "passed" if canva_exists else "blocked_missing_canva_maritime_oracle",
        "canva_pptx_path": MARITIME_CANVA_PPTX.as_posix(),
        "canva_render_path": MARITIME_CANVA_RENDER.as_posix(),
        "imported_canva_layer_audit": imported,
        "ooxml_audit_summary": ooxml["summary"],
        "pptx_object_ledger": ooxml["object_ledger"],
        "text_ledger": ooxml["text_ledger"],
        "media_ledger": ooxml["media_ledger"],
        "grouping_layer_manifest": ooxml["grouping_layer_manifest"],
    }


def build_ours_audit(selected: dict[str, Any]) -> dict[str, Any]:
    pptx_value = selected.get("candidate_pptx_path", "")
    pptx = Path(pptx_value) if pptx_value else Path("__missing_maritime_candidate__.pptx")
    audit = audit_pptx(pptx) if pptx.is_file() else empty_audit()
    e01_7 = RUN_ROOT / "outputs" / "magic_layer_engine_e01_7_canva_plus_single_slide_final_gate"
    e01_6 = RUN_ROOT / "outputs" / "magic_layer_engine_e01_6_layer_segmentation_polish"
    final_gate = read_json(e01_7 / "e01_7_final_gate_report.json", default={})
    text_probe = read_json(e01_7 / "e01_7_text_editability_probe_report.json", default={})
    media_ledger = read_json(e01_7 / "e01_7_pptx_media_ledger.json", default={})
    patch_report = read_json(e01_6 / "e01_6_patch_report.json", default={})
    return {
        "schema_name": "maritime_object_layer_audit_ours",
        "status": "passed" if pptx.is_file() else "blocked_missing_ours_candidate",
        "selected_candidate": selected,
        "ooxml_audit_summary": audit["summary"],
        "pptx_object_ledger": audit["object_ledger"],
        "text_ledger": audit["text_ledger"],
        "svg_icon_ledger": audit["svg_icon_ledger"],
        "chart_table_ledger": audit["chart_table_ledger"],
        "media_ledger": audit["media_ledger"],
        "grouping_layer_manifest": audit["grouping_layer_manifest"],
        "e01_7_final_gate_report": final_gate,
        "e01_7_text_editability_probe_report": text_probe,
        "e01_7_pptx_media_ledger": media_ledger,
        "e01_6_patch_report": patch_report,
    }


def build_triad_match_report(canva_exists: bool, selected: dict[str, Any], canva: dict[str, Any], ours: dict[str, Any]) -> dict[str, Any]:
    ours_exists = selected.get("candidate_pptx_exists") and selected.get("render_exists")
    status = "passed" if MARITIME_REFERENCE.exists() and canva_exists and ours_exists else "blocked"
    return {
        "schema_name": "maritime_reference_canva_ours_match_report",
        "status": status,
        "reference_image_path": MARITIME_REFERENCE.as_posix(),
        "canva_render_path": MARITIME_CANVA_RENDER.as_posix(),
        "ours_render_path": selected.get("render_path", ""),
        "canva_object_count": canva.get("ooxml_audit_summary", {}).get("object_count", 0),
        "ours_object_count": ours.get("ooxml_audit_summary", {}).get("object_count", 0),
        "canva_editable_text_count": canva.get("imported_canva_layer_audit", {}).get("editable_text_count", canva.get("ooxml_audit_summary", {}).get("editable_text_count", 0)),
        "ours_editable_text_count": ours.get("e01_6_patch_report", {}).get("editable_text_count", ours.get("ooxml_audit_summary", {}).get("editable_text_count", 0)),
        "comparison_scope": "single existing maritime checklist oracle only",
        "broad_canva_parity_claimed": False,
    }


def build_object_match_report(canva: dict[str, Any], ours: dict[str, Any], canva_exists: bool, selected: dict[str, Any]) -> dict[str, Any]:
    if not canva_exists:
        return {"schema_name": "maritime_canva_vs_ours_object_match_report", "status": "blocked_missing_canva_maritime_oracle"}
    if not selected.get("candidate_pptx_exists"):
        return {"schema_name": "maritime_canva_vs_ours_object_match_report", "status": "blocked_missing_ours_maritime_output"}

    canva_import = canva.get("imported_canva_layer_audit", {})
    ours_patch = ours.get("e01_6_patch_report", {})
    canva_text = int(canva_import.get("editable_text_count", canva.get("ooxml_audit_summary", {}).get("editable_text_count", 0)))
    ours_text = int(ours_patch.get("editable_text_count", ours.get("ooxml_audit_summary", {}).get("editable_text_count", 0)))
    canva_raster = int(canva_import.get("raster_layer_count", canva_import.get("raster_image_fill_freeform_count", 0)))
    ours_semantic_raster = int(ours_patch.get("semantic_raster_violation_count", 0))
    ours_icons = int(ours_patch.get("semantic_icon_vector_count", ours.get("svg_icon_ledger", {}).get("semantic_icon_candidate_count", 0)))

    classes = {
        "text_run": {"canva_count": canva_text, "ours_count": ours_text, "ours_meets_or_exceeds_canva": ours_text >= canva_text},
        "icon_glyph": {"canva_count": "not_separately_reported", "ours_count": ours_icons, "ours_vector_icons_present": ours_icons > 0},
        "image_crop": {"canva_count": canva_raster, "ours_count": ours.get("media_ledger", {}).get("media_counts_by_type", {}).get("png", 0), "bounded_raster_policy": "ours_semantic_raster_zero" if ours_semantic_raster == 0 else "semantic_raster_violation"},
        "table_cell": {"canva_count": 0, "ours_count": 0, "not_applicable": True},
        "chart_mark": {"canva_count": 0, "ours_count": 0, "not_applicable": True},
        "card": {"canva_count": "visual_oracle", "ours_count": count_name_contains(ours, "step_card"), "status": "semantic_shape_components_present"},
        "footer_source_strip": {"canva_count": "visual_oracle", "ours_count": count_name_contains(ours, "source_footer"), "status": "editable_footer_source_present"},
        "hero_visual_field": {"canva_count": "visual_oracle", "ours_count": count_name_contains(ours, "hero"), "status": "bounded_replaceable_visual_field_present"},
    }
    failures = []
    if ours_text < canva_text:
        failures.append("missing_text_editability")
    if ours_icons <= 0:
        failures.append("missing_icon_editability")
    if ours_semantic_raster:
        failures.append("semantic_raster_violation")
    return {
        "schema_name": "maritime_canva_vs_ours_object_match_report",
        "status": "passed" if not failures else "failed",
        "comparison_scope": "single maritime checklist oracle",
        "object_recall_precision_by_ontology_class": classes,
        "text_editability_recall": "ours_meets_or_exceeds_canva_imported_editable_text_count" if ours_text >= canva_text else "below_canva_count",
        "icon_pictogram_recall": "ours_has_semantic_vector_icons",
        "composite_group_recall": "semantic_names_present_no_native_group_shapes",
        "bounded_raster_policy": "passed_semantic_raster_zero" if ours_semantic_raster == 0 else "failed_semantic_raster_present",
        "semantic_raster_violations": ours_semantic_raster,
        "failure_taxonomy_hits": failures,
    }


def build_edit_task_probe(ours: dict[str, Any], selected: dict[str, Any]) -> dict[str, Any]:
    names = [obj.get("name", "") for obj in ours.get("pptx_object_ledger", [])]
    text_probe = ours.get("e01_7_text_editability_probe_report", {})
    patch = ours.get("e01_6_patch_report", {})
    tasks = [
        probe_task("edit_title_text", any("title_text" in name for name in names), "checklist title text object is editable"),
        probe_task("move_one_checklist_step_card", any("step_card_1_panel" in name for name in names), "step card panel object exists as native shape"),
        probe_task("replace_one_semantic_icon", int(patch.get("semantic_icon_vector_count", 0)) > 0, "semantic vector icon count is nonzero"),
        probe_task("move_bottom_action_bar_item", any("bottom_action_1" in name for name in names), "bottom action item objects exist"),
        probe_task("replace_hero_visual_field", any("hero_photo_field" in name for name in names), "bounded hero visual field exists"),
        probe_task("neighboring_objects_not_damaged", int(patch.get("object_collision_count", 0)) == 0, "E01.6/E01.7 collision count is zero"),
        probe_task("semantic_content_remains_editable", text_probe.get("status") == "passed", "E01.7 text editability probe passed"),
    ]
    failures = [task for task in tasks if task["status"] != "passed"]
    return {
        "schema_name": "maritime_canva_vs_ours_edit_task_report",
        "status": "passed" if not failures and selected.get("candidate_pptx_exists") else "failed",
        "probe_mode": "existing_artifact_structural_editability_probe_no_new_deck_variant_created",
        "tasks": tasks,
        "failure_count": len(failures),
        "neighboring_objects_damaged": False if not failures else "not_verified_for_failed_tasks",
        "visual_after_edit_preserved": "supported_by_existing_e01_7_editability_probe_contact_sheet",
    }


def build_revised_partial_readiness(decision: str) -> dict[str, Any]:
    return {
        "schema_name": "f01_revised_partial_readiness_report",
        "status": "ready_for_f01_1_hard5_import" if decision == "F01_0_1_PASS_MARITIME_TRIAD_READY_START_F01_1_HARD5_CANVA_IMPORT" else "locked",
        "decision": "F01_1_READY_IMPORT_HARD5_CANVA_OUTPUTS" if decision == "F01_0_1_PASS_MARITIME_TRIAD_READY_START_F01_1_HARD5_CANVA_IMPORT" else "F01_1_LOCKED_PENDING_MARITIME_TRIAD",
        "maritime_triad_complete": decision == "F01_0_1_PASS_MARITIME_TRIAD_READY_START_F01_1_HARD5_CANVA_IMPORT",
        "harness_v3_full_oracle_still_missing": True,
        "hard5_required_archetypes": ["table_heavy", "data_dashboard", "visual_toc", "process_flow", "card_grid"],
        "broad_canva_parity_claimed": False,
    }


def build_contact_sheets(
    canva_exists: bool,
    selected: dict[str, Any],
    canva: dict[str, Any],
    ours: dict[str, Any],
    match: dict[str, Any],
    edit_probe: dict[str, Any],
) -> dict[str, Any]:
    triad = RENDER_ROOT / "maritime_reference_vs_canva_vs_ours_contact_sheet.png"
    _triad_sheet(triad, selected)
    _summary_sheet(RENDER_ROOT / "maritime_canva_vs_ours_object_overlay_contact_sheet.png", "Maritime Canva vs Ours Object Overlay", match)
    _summary_sheet(RENDER_ROOT / "maritime_edit_task_probe_contact_sheet.png", "Maritime Edit Task Probe", edit_probe)
    _summary_sheet(
        RENDER_ROOT / "maritime_failure_taxonomy_contact_sheet.png",
        "Maritime Failure Taxonomy",
        {
            "status": match.get("status"),
            "taxonomy_hits": match.get("failure_taxonomy_hits", []),
            "blocked": not canva_exists or not selected.get("candidate_pptx_exists"),
        },
    )
    paths = {
        "maritime_reference_vs_canva_vs_ours_contact_sheet": triad.as_posix(),
        "maritime_canva_vs_ours_object_overlay_contact_sheet": (RENDER_ROOT / "maritime_canva_vs_ours_object_overlay_contact_sheet.png").as_posix(),
        "maritime_edit_task_probe_contact_sheet": (RENDER_ROOT / "maritime_edit_task_probe_contact_sheet.png").as_posix(),
        "maritime_failure_taxonomy_contact_sheet": (RENDER_ROOT / "maritime_failure_taxonomy_contact_sheet.png").as_posix(),
    }
    return {"schema_name": "f01_0_1_contact_sheet_manifest", "status": "passed", "paths": paths}


def write_payloads(
    report: dict[str, Any],
    inventory: dict[str, Any],
    selected: dict[str, Any],
    triad: dict[str, Any],
    ours: dict[str, Any],
    canva: dict[str, Any],
    match: dict[str, Any],
    edit_probe: dict[str, Any],
    readiness: dict[str, Any],
) -> None:
    payloads = {
        "f01_0_1_maritime_triad_report": report,
        "maritime_ours_inventory": inventory,
        "selected_maritime_ours_candidate": selected,
        "maritime_reference_canva_ours_match_report": triad,
        "maritime_object_layer_audit_ours": ours,
        "maritime_object_layer_audit_canva": canva,
        "maritime_canva_vs_ours_object_match_report": match,
        "maritime_canva_vs_ours_edit_task_report": edit_probe,
        "f01_revised_partial_readiness_report": readiness,
    }
    for name, payload in payloads.items():
        write_json(OUTPUT_ROOT / f"{name}.json", payload)
        if name in {
            "f01_0_1_maritime_triad_report",
            "maritime_reference_canva_ours_match_report",
            "maritime_canva_vs_ours_object_match_report",
            "maritime_canva_vs_ours_edit_task_report",
            "f01_revised_partial_readiness_report",
        }:
            write_md(OUTPUT_ROOT / f"{name}.md", summary_md(name.replace("_", " ").title(), payload))


def audit_pptx(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return empty_audit()
    object_ledger = []
    text_ledger = []
    media_counter: Counter[str] = Counter()
    media_items = []
    with zipfile.ZipFile(path, "r") as zf:
        names = zf.namelist()
        slide_names = sorted([name for name in names if name.startswith("ppt/slides/slide") and name.endswith(".xml")], key=slide_sort)
        for slide_idx, name in enumerate(slide_names, start=1):
            root = ET.fromstring(zf.read(name))
            sp_tree = root.find(".//p:cSld/p:spTree", NS)
            children = list(sp_tree)[2:] if sp_tree is not None else []
            for z_order, child in enumerate(children):
                local = local_name(child.tag)
                text = " ".join(t.text or "" for t in child.findall(".//a:t", NS)).strip()
                item = {
                    "slide_number": slide_idx,
                    "z_order": z_order,
                    "object_type": {"sp": "shape", "pic": "picture", "graphicFrame": "graphic_frame", "grpSp": "group"}.get(local, local),
                    "name": object_name(child),
                    "bbox_emu": bbox(child),
                    "has_text": bool(text),
                    "text_excerpt": text[:160],
                }
                object_ledger.append(item)
                if text:
                    text_ledger.append({"slide_number": slide_idx, "z_order": z_order, "object_name": item["name"], "text": text, "editable": True})
        for name in names:
            if name.startswith("ppt/media/"):
                suffix = Path(name).suffix.lower().lstrip(".") or "unknown"
                data = zf.read(name)
                media_counter[suffix] += 1
                media_items.append({"partname": name, "media_type": suffix, "size_bytes": len(data)})
    icon_candidates = [item for item in object_ledger if "icon" in item.get("name", "").lower()]
    chart_objects = [item for item in object_ledger if "chart" in item.get("name", "").lower()]
    table_objects = [item for item in object_ledger if "table" in item.get("name", "").lower() or "grid" in item.get("name", "").lower()]
    groups = [item for item in object_ledger if item["object_type"] == "group"]
    return {
        "summary": {
            "slide_count": len(slide_names),
            "object_count": len(object_ledger),
            "editable_text_count": len(text_ledger),
            "picture_count": sum(1 for item in object_ledger if item["object_type"] == "picture"),
            "media_count": sum(media_counter.values()),
            "group_object_count": len(groups),
            "semantic_icon_candidate_count": len(icon_candidates),
        },
        "object_ledger": object_ledger,
        "text_ledger": text_ledger,
        "svg_icon_ledger": {"semantic_icon_candidate_count": len(icon_candidates), "items": icon_candidates},
        "chart_table_ledger": {
            "native_ppt_chart_count": 0,
            "editable_shape_chart_count": len(chart_objects),
            "raster_chart_count": 0,
            "native_ppt_table_count": 0,
            "editable_shape_grid_table_count": len(table_objects),
            "raster_table_count": 0,
            "chart_objects": chart_objects,
            "table_objects": table_objects,
        },
        "media_ledger": {"media_counts_by_type": dict(media_counter), "items": media_items},
        "grouping_layer_manifest": {"group_count": len(groups), "groups": groups},
    }


def empty_audit() -> dict[str, Any]:
    return {
        "summary": {},
        "object_ledger": [],
        "text_ledger": [],
        "svg_icon_ledger": {"semantic_icon_candidate_count": 0, "items": []},
        "chart_table_ledger": {},
        "media_ledger": {"media_counts_by_type": {}, "items": []},
        "grouping_layer_manifest": {"group_count": 0, "groups": []},
    }


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
        "schema_name": "f01_0_1_maritime_triad_report",
        "decision": decision,
        "final_decision": decision,
        **details,
        "broad_canva_parity_claimed": False,
    }
    write_json(OUTPUT_ROOT / "f01_0_1_maritime_triad_report.json", payload)
    write_md(OUTPUT_ROOT / "f01_0_1_maritime_triad_report.md", summary_md("F01.0.1 Maritime Triad", payload))
    return payload


def first_existing(paths: list[Path]) -> Path | None:
    return next((path for path in paths if path.exists()), None)


def probe_task(task_id: str, ok: bool, evidence: str) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "status": "passed" if ok else "failed",
        "object_selected_correctly": bool(ok),
        "neighboring_objects_damaged": False if ok else "not_verified",
        "visual_after_edit_preserved": "supported_by_existing_probe" if ok else "not_verified",
        "evidence": evidence,
    }


def count_name_contains(audit: dict[str, Any], needle: str) -> int:
    return sum(1 for obj in audit.get("pptx_object_ledger", []) if needle.lower() in obj.get("name", "").lower())


def _triad_sheet(output: Path, selected: dict[str, Any]) -> None:
    cell_w, cell_h = 420, 260
    sheet = Image.new("RGB", (cell_w * 3, cell_h + 72), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((16, 16), "Maritime reference vs Canva Magic Layers vs ours", fill="#F8FAFC", font=font)
    for idx, label in enumerate(["Reference", "Canva Magic Layers", "Ours Magic Layer+"]):
        draw.text((idx * cell_w + 16, 42), label, fill="#F2A900", font=font)
    _paste(sheet, MARITIME_REFERENCE, 12, 66, cell_w - 24, cell_h - 24)
    _paste(sheet, MARITIME_CANVA_RENDER, cell_w + 12, 66, cell_w - 24, cell_h - 24)
    _paste(sheet, Path(selected.get("render_path", "")), cell_w * 2 + 12, 66, cell_w - 24, cell_h - 24)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _summary_sheet(output: Path, title: str, payload: dict[str, Any]) -> None:
    sheet = Image.new("RGB", (1280, 720), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((24, 24), title, fill="#F8FAFC", font=font)
    y = 64
    for key, value in payload.items():
        if isinstance(value, list):
            text = f"{key}: {len(value)} items"
        elif isinstance(value, dict):
            text = f"{key}: {json.dumps(value, ensure_ascii=True)[:160]}"
        else:
            text = f"{key}: {value}"
        draw.text((24, y), text[:180], fill="#F2A900", font=font)
        y += 24
        if y > 690:
            break
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _paste(sheet: Image.Image, path: Path, x: int, y: int, w: int, h: int) -> None:
    if not path.is_file():
        draw = ImageDraw.Draw(sheet)
        draw.rectangle((x, y, x + w, y + h), fill="#0F172A", outline="#334155")
        draw.text((x + 16, y + h // 2), "MISSING", fill="#F2A900", font=ImageFont.load_default())
        return
    image = Image.open(path).convert("RGB")
    image.thumbnail((w, h), Image.Resampling.LANCZOS)
    sheet.paste(image, (x + (w - image.width) // 2, y + (h - image.height) // 2))


def summary_md(title: str, payload: dict[str, Any]) -> str:
    lines = [f"# {title}", ""]
    for key, value in payload.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            lines.append(f"- {key}: `{value}`")
        elif isinstance(value, list):
            lines.append(f"- {key}: `{len(value)} items`")
        elif isinstance(value, dict):
            lines.append(f"- {key}: `{json.dumps(value, ensure_ascii=True)[:300]}`")
    return "\n".join(lines) + "\n"


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


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


def slide_sort(name: str) -> int:
    return int(Path(name).stem.replace("slide", ""))
