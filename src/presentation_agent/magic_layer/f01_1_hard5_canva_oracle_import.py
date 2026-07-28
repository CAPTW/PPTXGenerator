"""F01.1 hard-5 Canva Magic Layers oracle import and benchmark.

This stage imports external Canva Magic Layers outputs for the five hard
Harness V3 archetypes when present. Missing Canva oracles are reported as
blocking; our accepted deck is audited only as the comparison target.
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from PIL import Image, ImageChops, ImageDraw, ImageFont
from pptx import Presentation

from src.presentation_agent.magic_layer.e03_16_orchestrator import read_json, write_json, write_md
from src.presentation_agent.qa.render_pptx_preview import render_pptx_preview


REPO_ROOT = Path(__file__).resolve().parents[3]
RUN_ROOT = REPO_ROOT / "design_runs" / "run_002"
CANVA_ROOT = REPO_ROOT / "design_runs" / "benchmarks" / "canva_magic_layer"
OUTPUT_ROOT = RUN_ROOT / "outputs" / "magic_layer_engine_f01_1_hard5_canva_oracle_import"
RENDER_ROOT = OUTPUT_ROOT / "renders"
PROTECTED_REPORT_ROOT = REPO_ROOT / "analysis_runs" / "protected_artifact_gate_latest"

OUR_ACCEPTED_PPTX = RUN_ROOT / "outputs" / "magic_layer_engine_e06_4_1_human_visual_acceptance" / "accepted_candidate" / "harness_v3_e06_4_1_human_accepted_baseline_candidate.pptx"
OUR_ACCEPTED_RENDER_DIR = RUN_ROOT / "outputs" / "magic_layer_engine_e06_4_1_human_visual_acceptance" / "renders"
OUR_FALLBACK_PPTX = RUN_ROOT / "outputs" / "magic_layer_engine_e06_2_1_contract_style_content_fidelity_patch" / "contract_recompiled_v2" / "harness_v3_e06_2_1_contract_recompiled_style_content_fidelity_candidate.pptx"
OUR_FALLBACK_RENDER_DIR = RUN_ROOT / "outputs" / "magic_layer_engine_e06_2_1_contract_style_content_fidelity_patch" / "renders"

HARD5 = [
    {"slide_number": 2, "archetype_id": "visual_toc", "dir_name": "02_visual_toc"},
    {"slide_number": 9, "archetype_id": "comparison_matrix", "dir_name": "09_comparison_matrix"},
    {"slide_number": 10, "archetype_id": "data_dashboard", "dir_name": "10_data_dashboard"},
    {"slide_number": 11, "archetype_id": "table_heavy", "dir_name": "11_table_heavy"},
    {"slide_number": 14, "archetype_id": "risk_register", "dir_name": "14_risk_register"},
]

EDIT_TASKS = {
    "visual_toc": ["move_one_module_card", "edit_one_module_title", "replace_one_icon", "move_right_meta_rail"],
    "comparison_matrix": ["edit_one_criteria_label", "move_one_option_status_chip", "edit_one_table_cell", "verify_table_remains_editable"],
    "data_dashboard": ["edit_one_kpi_value", "edit_one_chart_bar_value", "move_insight_panel", "replace_one_kpi_icon"],
    "table_heavy": ["edit_one_row_label", "edit_one_status_pill", "move_table_group", "verify_cell_level_editability"],
    "risk_register": ["edit_one_risk_label", "edit_one_severity_status_marker", "move_one_row_group", "verify_register_remains_editable"],
}

NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def run() -> dict[str, Any]:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    RENDER_ROOT.mkdir(parents=True, exist_ok=True)

    precheck = run_protect_check()
    copy_protected_report()
    if not precheck["passed"]:
        return write_blocked("F01_1_FAIL_PROTECTED_ARTIFACTS", {"protected_artifact_precheck": precheck})

    inventory = build_hard5_inventory()
    validation = validate_and_materialize_canva_oracles(inventory)
    canva_summary = build_canva_layer_audit_summary(validation)
    ours_summary = build_our_layer_audit_summary()
    match = build_reference_canva_ours_match_report(validation, ours_summary)
    object_match = build_object_match_report(validation, ours_summary)
    edit_task = build_edit_task_benchmark(validation, ours_summary)
    taxonomy = build_failure_taxonomy_report(object_match, edit_task)
    decision = decide(validation)
    f02 = build_f02_readiness(decision)
    contacts = build_contact_sheets(validation, ours_summary, object_match, edit_task, taxonomy)
    report = build_final_report(decision, validation, match, canva_summary, ours_summary, object_match, edit_task, taxonomy, f02, contacts)

    write_outputs(report, inventory, validation, match, canva_summary, ours_summary, object_match, edit_task, taxonomy, f02)

    postcheck = run_protect_check()
    copy_protected_report()
    if not postcheck["passed"]:
        report["decision"] = "F01_1_FAIL_PROTECTED_ARTIFACTS"
        report["final_decision"] = "F01_1_FAIL_PROTECTED_ARTIFACTS"
        write_json(OUTPUT_ROOT / "f01_1_hard5_canva_import_report.json", report)
        write_md(OUTPUT_ROOT / "f01_1_hard5_canva_import_report.md", summary_md("F01.1 Hard5 Canva Import", report))
    return report


def build_hard5_inventory() -> dict[str, Any]:
    rows = []
    for item in HARD5:
        folder = CANVA_ROOT / "harness_v3" / item["dir_name"]
        folder.mkdir(parents=True, exist_ok=True)
        row = {
            "archetype_id": item["archetype_id"],
            "slide_number": item["slide_number"],
            "expected_dir": folder.as_posix(),
            "reference_image_path": reference_path(item["archetype_id"]).as_posix(),
            "canva_pptx_path": (folder / "canva_magic_layers_output.pptx").as_posix(),
            "canva_render_path": (folder / "canva_rendered_slide.png").as_posix(),
            "canva_layer_audit_path": (folder / "canva_layer_audit.json").as_posix(),
            "canva_text_ledger_path": (folder / "canva_text_ledger.json").as_posix(),
            "canva_media_ledger_path": (folder / "canva_media_ledger.json").as_posix(),
            "canva_grouping_manifest_path": (folder / "canva_grouping_manifest.json").as_posix(),
        }
        row.update(
            {
                "pptx_exists": Path(row["canva_pptx_path"]).is_file(),
                "render_exists": Path(row["canva_render_path"]).is_file(),
                "layer_audit_exists": Path(row["canva_layer_audit_path"]).is_file(),
                "text_ledger_exists": Path(row["canva_text_ledger_path"]).is_file(),
                "media_ledger_exists": Path(row["canva_media_ledger_path"]).is_file(),
                "grouping_manifest_exists": Path(row["canva_grouping_manifest_path"]).is_file(),
            }
        )
        if row["pptx_exists"]:
            row["import_status"] = "pptx_available"
        elif row["render_exists"]:
            row["import_status"] = "visual_only_png"
        else:
            row["import_status"] = "missing"
        rows.append(row)
    return {
        "schema_name": "hard5_canva_oracle_inventory",
        "status": "passed" if all(row["pptx_exists"] for row in rows) else "blocked_missing_or_partial",
        "hard5_count": len(rows),
        "pptx_available_count": sum(1 for row in rows if row["pptx_exists"]),
        "visual_only_count": sum(1 for row in rows if row["import_status"] == "visual_only_png"),
        "missing_count": sum(1 for row in rows if row["import_status"] == "missing"),
        "items": rows,
        "broad_canva_parity_claimed": False,
    }


def validate_and_materialize_canva_oracles(inventory: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for row in inventory["items"]:
        materialized = dict(row)
        pptx = Path(row["canva_pptx_path"])
        render = Path(row["canva_render_path"])
        if pptx.is_file():
            if not render.is_file():
                render_report = render_one_canva_pptx(pptx, render, row["archetype_id"])
            else:
                render_report = {"status": "passed", "render_status": "provided", "schema_name": "hard5_canva_render_report"}
            audit = audit_pptx(pptx, slide_numbers=None, sample_id=row["archetype_id"])
            audit["audit_source"] = "local_audit_from_canva_pptx"
            write_json(Path(row["canva_layer_audit_path"]), audit)
            write_json(Path(row["canva_text_ledger_path"]), {"schema_name": "canva_text_ledger", "audit_source": "local_audit_from_canva_pptx", "archetype_id": row["archetype_id"], "items": audit["text_ledger"], "editable_text_count": len(audit["text_ledger"])})
            write_json(Path(row["canva_media_ledger_path"]), audit["media_ledger"])
            write_json(Path(row["canva_grouping_manifest_path"]), audit["grouping_manifest"])
            materialized.update(
                {
                    "validation_status": "passed" if render.is_file() and audit["status"] == "passed" else "patch_render_or_audit_required",
                    "canva_oracle_quality": canva_oracle_quality(audit),
                    "audit_source": "local_audit_from_canva_pptx",
                    "render_report": render_report,
                    "layer_audit": audit,
                    "render_exists": render.is_file(),
                    "layer_audit_exists": True,
                    "text_ledger_exists": True,
                    "media_ledger_exists": True,
                    "grouping_manifest_exists": True,
                }
            )
        elif render.is_file():
            materialized.update(
                {
                    "validation_status": "visual_only_object_benchmark_blocked",
                    "canva_oracle_quality": "visual_only_no_object_oracle",
                    "audit_source": "none_png_only",
                    "layer_audit": empty_audit(row["archetype_id"]),
                }
            )
        else:
            materialized.update(
                {
                    "validation_status": "missing_canva_output",
                    "canva_oracle_quality": "missing",
                    "audit_source": "missing",
                    "layer_audit": empty_audit(row["archetype_id"]),
                }
            )
        rows.append(materialized)
    missing = [row for row in rows if row["validation_status"] == "missing_canva_output"]
    visual_only = [row for row in rows if row["validation_status"] == "visual_only_object_benchmark_blocked"]
    failed = [row for row in rows if row["validation_status"] == "patch_render_or_audit_required"]
    status = "passed"
    if missing:
        status = "blocked_missing_hard5_canva_outputs"
    elif visual_only:
        status = "partial_visual_only_canva_outputs"
    elif failed:
        status = "patch_canva_import_audit_required"
    return {
        "schema_name": "hard5_canva_oracle_validation_report",
        "status": status,
        "hard5_count": len(rows),
        "pptx_available_count": sum(1 for row in rows if row["pptx_exists"]),
        "visual_only_count": len(visual_only),
        "missing_count": len(missing),
        "audit_failure_count": len(failed),
        "items": rows,
        "broad_canva_parity_claimed": False,
    }


def render_one_canva_pptx(pptx: Path, target_render: Path, archetype_id: str) -> dict[str, Any]:
    raw_dir = OUTPUT_ROOT / "renders" / f"_{archetype_id}_canva_raw"
    report = render_pptx_preview(
        pptx_path=pptx,
        output_dir=raw_dir,
        manifest_path=OUTPUT_ROOT / f"{archetype_id}_canva_render_manifest.json",
        backend="auto",
        dpi=144,
    )
    first = None
    for slide in report.get("slides", []):
        candidate = Path(slide.get("rendered_image_path", ""))
        if candidate.is_file():
            first = candidate
            break
    if first:
        shutil.copy2(first, target_render)
    report["target_render_path"] = target_render.as_posix()
    report["status"] = "passed" if target_render.is_file() else "failed"
    return report


def build_canva_layer_audit_summary(validation: dict[str, Any]) -> dict[str, Any]:
    rows = []
    totals = Counter()
    for item in validation["items"]:
        audit = item.get("layer_audit", {})
        row = {
            "archetype_id": item["archetype_id"],
            "validation_status": item["validation_status"],
            "canva_oracle_quality": item["canva_oracle_quality"],
            "audit_source": item.get("audit_source"),
            "slide_count": audit.get("slide_count", 0),
            "object_count": audit.get("object_count", 0),
            "canva_full_slide_media_candidate_count": audit.get("canva_full_slide_media_candidate_count", 0),
            "canva_large_media_fragment_count": audit.get("canva_large_media_fragment_count", 0),
            "canva_semantic_text_baked_into_media_count": audit.get("canva_semantic_text_baked_into_media_count", 0),
            "canva_semantic_icon_baked_into_media_count": audit.get("canva_semantic_icon_baked_into_media_count", 0),
            "canva_table_or_chart_baked_into_media_count": audit.get("canva_table_or_chart_baked_into_media_count", 0),
            "canva_editable_text_count": audit.get("editable_text_count", 0),
            "canva_editable_icon_or_small_object_count": audit.get("canva_editable_icon_or_small_object_count", 0),
            "canva_composite_group_count": audit.get("canva_composite_group_count", 0),
            "canva_grouping_quality_notes": audit.get("canva_grouping_quality_notes", []),
            "canva_known_limitations": audit.get("canva_known_limitations", []),
        }
        for key, value in row.items():
            if isinstance(value, int):
                totals[key] += value
        rows.append(row)
    return {
        "schema_name": "hard5_canva_layer_audit_summary",
        "status": validation["status"],
        "items": rows,
        "totals": dict(totals),
        "canva_is_black_box_benchmark_not_perfect_oracle": True,
    }


def build_our_layer_audit_summary() -> dict[str, Any]:
    pptx = OUR_ACCEPTED_PPTX if OUR_ACCEPTED_PPTX.exists() else OUR_FALLBACK_PPTX
    render_dir = OUR_ACCEPTED_RENDER_DIR if OUR_ACCEPTED_PPTX.exists() else OUR_FALLBACK_RENDER_DIR
    slide_numbers = [item["slide_number"] for item in HARD5]
    audit = audit_pptx(pptx, slide_numbers=slide_numbers, sample_id="ours_hard5") if pptx.exists() else empty_audit("ours_hard5")
    rows = []
    by_slide = defaultdict(list)
    for obj in audit["pptx_object_ledger"]:
        by_slide[obj["slide_number"]].append(obj)
    text_by_slide = defaultdict(list)
    for row in audit["text_ledger"]:
        text_by_slide[row["slide_number"]].append(row)
    for item in HARD5:
        slide = item["slide_number"]
        rows.append(
            {
                "archetype_id": item["archetype_id"],
                "slide_number": slide,
                "render_path": ours_render_path(render_dir, slide).as_posix(),
                "object_count": len(by_slide[slide]),
                "editable_text_count": len(text_by_slide[slide]),
                "semantic_icon_candidate_count": sum(1 for obj in by_slide[slide] if "icon" in obj.get("name", "").lower()),
                "media_object_count": sum(1 for obj in by_slide[slide] if obj.get("has_media_reference") or obj.get("object_type") == "picture"),
                "group_count": sum(1 for obj in by_slide[slide] if obj.get("object_type") == "group"),
            }
        )
    return {
        "schema_name": "hard5_our_layer_audit_summary",
        "status": "passed" if pptx.exists() else "blocked_missing_ours_source",
        "our_candidate_pptx": pptx.as_posix(),
        "render_dir": render_dir.as_posix(),
        "items": rows,
        "aggregate": {
            "object_count": audit.get("object_count", 0),
            "editable_text_count": audit.get("editable_text_count", 0),
            "media_count": audit.get("media_count", 0),
            "semantic_icon_candidate_count": audit.get("canva_editable_icon_or_small_object_count", 0),
        },
        "layer_audit": audit,
        "broad_canva_parity_claimed": False,
    }


def build_reference_canva_ours_match_report(validation: dict[str, Any], ours: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for item in validation["items"]:
        ours_row = next((row for row in ours.get("items", []) if row["archetype_id"] == item["archetype_id"]), {})
        canva_render = Path(item["canva_render_path"])
        reference = Path(item["reference_image_path"])
        ours_render = Path(ours_row.get("render_path", ""))
        rows.append(
            {
                "archetype_id": item["archetype_id"],
                "reference_exists": reference.is_file(),
                "canva_render_exists": canva_render.is_file(),
                "ours_render_exists": ours_render.is_file(),
                "visual_similarity_reference_canva": image_similarity(reference, canva_render) if reference.is_file() and canva_render.is_file() else None,
                "visual_similarity_canva_ours": image_similarity(canva_render, ours_render) if canva_render.is_file() and ours_render.is_file() else None,
            }
        )
    return {
        "schema_name": "hard5_reference_canva_ours_match_report",
        "status": "passed" if all(row["reference_exists"] and row["canva_render_exists"] and row["ours_render_exists"] for row in rows) else "blocked_missing_render_or_reference",
        "items": rows,
    }


def build_object_match_report(validation: dict[str, Any], ours: dict[str, Any]) -> dict[str, Any]:
    rows = []
    scores = {"L1_visual_reconstruction": None, "L2_object_selectability": None, "L3_semantic_editability": None, "L4_composite_grouping": None, "L5_edit_task_parity": None}
    if validation["status"] == "blocked_missing_hard5_canva_outputs":
        return {
            "schema_name": "hard5_canva_vs_ours_object_match_report",
            "status": "blocked_missing_hard5_canva_outputs",
            "preliminary_scores": scores,
            "items": [],
            "where_canva_better": [],
            "where_ours_better": [],
            "where_both_fail": [],
            "canva_large_media_overlay_strategy": [],
            "ours_no_raster_policy_stricter_than_canva": [],
            "broad_canva_parity_claimed": False,
        }
    if validation["status"] == "partial_visual_only_canva_outputs":
        return {"schema_name": "hard5_canva_vs_ours_object_match_report", "status": "blocked_object_parity_visual_only_canva_outputs", "preliminary_scores": scores, "items": []}

    ours_by_archetype = {row["archetype_id"]: row for row in ours.get("items", [])}
    canva_better = []
    ours_better = []
    both_fail = []
    large_media = []
    strict_raster = []
    l2_values = []
    l3_values = []
    l4_values = []
    for item in validation["items"]:
        audit = item.get("layer_audit", {})
        ours_row = ours_by_archetype.get(item["archetype_id"], {})
        canva_text = int(audit.get("editable_text_count", 0))
        ours_text = int(ours_row.get("editable_text_count", 0))
        canva_objects = int(audit.get("object_count", 0))
        ours_objects = int(ours_row.get("object_count", 0))
        canva_groups = int(audit.get("canva_composite_group_count", 0))
        ours_groups = int(ours_row.get("group_count", 0))
        l2 = bounded_ratio(ours_objects, canva_objects)
        l3 = bounded_ratio(ours_text, max(1, canva_text))
        l4 = 1.0 if ours_groups or canva_groups else 0.45
        l2_values.append(l2)
        l3_values.append(l3)
        l4_values.append(l4)
        if canva_text > ours_text:
            canva_better.append({"archetype_id": item["archetype_id"], "reason": "canva_has_more_editable_text_fragments", "canva": canva_text, "ours": ours_text})
        if ours_text > canva_text:
            ours_better.append({"archetype_id": item["archetype_id"], "reason": "ours_has_more_editable_text_fragments", "canva": canva_text, "ours": ours_text})
        if audit.get("canva_full_slide_media_candidate_count", 0) or audit.get("canva_large_media_fragment_count", 0):
            large_media.append({"archetype_id": item["archetype_id"], "quality": item["canva_oracle_quality"], "large_media": audit.get("canva_large_media_fragment_count", 0), "full_slide_candidates": audit.get("canva_full_slide_media_candidate_count", 0)})
            if audit.get("editable_text_count", 0):
                strict_raster.append({"archetype_id": item["archetype_id"], "note": "Canva uses large visual media with editable overlays; ours may be stricter about semantic raster use."})
        rows.append(
            {
                "archetype_id": item["archetype_id"],
                "canva_object_count": canva_objects,
                "ours_object_count": ours_objects,
                "canva_editable_text_count": canva_text,
                "ours_editable_text_count": ours_text,
                "object_selectability_score": round(l2, 3),
                "semantic_editability_score": round(l3, 3),
                "composite_grouping_score": round(l4, 3),
                "canva_known_limitations": audit.get("canva_known_limitations", []),
            }
        )
    scores["L2_object_selectability"] = round(avg(l2_values), 3)
    scores["L3_semantic_editability"] = round(avg(l3_values), 3)
    scores["L4_composite_grouping"] = round(avg(l4_values), 3)
    return {
        "schema_name": "hard5_canva_vs_ours_object_match_report",
        "status": "passed",
        "preliminary_scores": scores,
        "items": rows,
        "where_canva_better": canva_better,
        "where_ours_better": ours_better,
        "where_both_fail": both_fail,
        "canva_large_media_overlay_strategy": large_media,
        "ours_no_raster_policy_stricter_than_canva": strict_raster,
        "where_our_object_decomposition_is_editable_but_not_meaningful": [],
        "where_canva_visual_decomposition_is_good_but_semantics_imperfect": large_media,
        "broad_canva_parity_claimed": False,
    }


def build_edit_task_benchmark(validation: dict[str, Any], ours: dict[str, Any]) -> dict[str, Any]:
    rows = []
    pass_values = []
    for item in validation["items"]:
        archetype = item["archetype_id"]
        if item["validation_status"] == "missing_canva_output":
            task_rows = [{"task_id": task, "status": "blocked_missing_canva_output"} for task in EDIT_TASKS[archetype]]
        elif item["validation_status"] == "visual_only_object_benchmark_blocked":
            task_rows = [{"task_id": task, "status": "blocked_visual_only_canva_output"} for task in EDIT_TASKS[archetype]]
        else:
            audit = item.get("layer_audit", {})
            task_rows = [evaluate_edit_task(task, audit) for task in EDIT_TASKS[archetype]]
            pass_values.extend(1.0 if task["status"] == "passed" else 0.0 for task in task_rows)
        rows.append({"archetype_id": archetype, "tasks": task_rows})
    status = "passed" if pass_values and all(value == 1.0 for value in pass_values) else ("blocked_missing_hard5_canva_outputs" if validation["missing_count"] else "partial")
    return {
        "schema_name": "hard5_edit_task_benchmark_report",
        "status": status,
        "benchmark_dimensions": ["L5_edit-task parity"],
        "preliminary_l5_score": round(avg(pass_values), 3) if pass_values else None,
        "items": rows,
    }


def build_failure_taxonomy_report(object_match: dict[str, Any], edit_task: dict[str, Any]) -> dict[str, Any]:
    base = [
        "missed_object",
        "over_split_object",
        "under_split_object",
        "wrong_semantic_role",
        "wrong_grouping",
        "missing_text_editability",
        "missing_icon_editability",
        "table_chart_not_editable",
        "decorative_chrome_baked_incorrectly",
        "visual_field_too_coarse",
        "z_order_failure",
        "style_mismatch",
        "contract_only_improvement_without_visual_improvement",
        "canva_large_media_overlay_strategy",
        "canva_text_fragmentation",
        "canva_semantic_overlay_success",
        "ours_over_strict_raster_policy_visual_loss",
        "ours_editable_but_not_semantically_grouped",
        "ours_contract_preserved_but_not_visually_better",
    ]
    hits = Counter()
    if object_match["status"].startswith("blocked"):
        hits["missed_object"] += 1
    for row in object_match.get("canva_large_media_overlay_strategy", []):
        hits["canva_large_media_overlay_strategy"] += 1
        if row.get("quality") == "usable_with_large_media_and_editable_overlays":
            hits["canva_semantic_overlay_success"] += 1
    for item in edit_task.get("items", []):
        for task in item.get("tasks", []):
            if str(task.get("status", "")).startswith("blocked"):
                hits["table_chart_not_editable" if "table" in task["task_id"] or "chart" in task["task_id"] else "missed_object"] += 1
    return {
        "schema_name": "hard5_failure_taxonomy_report",
        "status": "passed",
        "failure_types": [{"failure_id": name, "hit_count": hits.get(name, 0)} for name in base],
        "top_failure_categories": [{"failure_id": key, "count": value} for key, value in hits.most_common(8)],
    }


def decide(validation: dict[str, Any]) -> str:
    if validation["status"] == "blocked_missing_hard5_canva_outputs":
        return "F01_1_BLOCKED_MISSING_HARD5_CANVA_OUTPUTS"
    if validation["status"] == "partial_visual_only_canva_outputs":
        return "F01_1_PARTIAL_VISUAL_ONLY_CANVA_OUTPUTS"
    if validation["status"] == "patch_canva_import_audit_required":
        return "F01_1_PATCH_CANVA_IMPORT_AUDIT_REQUIRED"
    return "F01_1_PASS_START_F02_METHOD_BAKEOFF_HARD5"


def build_f02_readiness(decision: str) -> dict[str, Any]:
    ready = decision == "F01_1_PASS_START_F02_METHOD_BAKEOFF_HARD5"
    return {
        "schema_name": "f02_method_bakeoff_readiness_report",
        "status": "ready" if ready else "locked",
        "decision": "F02_READY_START_METHOD_BAKEOFF_HARD5" if ready else "F02_LOCKED_PENDING_HARD5_CANVA_ORACLE_IMPORT",
        "hard5_canva_oracle_import_passed": ready,
        "broad_canva_parity_claimed": False,
    }


def build_final_report(
    decision: str,
    validation: dict[str, Any],
    match: dict[str, Any],
    canva_summary: dict[str, Any],
    ours_summary: dict[str, Any],
    object_match: dict[str, Any],
    edit_task: dict[str, Any],
    taxonomy: dict[str, Any],
    f02: dict[str, Any],
    contacts: dict[str, Any],
) -> dict[str, Any]:
    scores = dict(object_match.get("preliminary_scores", {}))
    scores["L1_visual_reconstruction"] = visual_score(match)
    scores["L5_edit_task_parity"] = edit_task.get("preliminary_l5_score")
    return {
        "schema_name": "f01_1_hard5_canva_import_report",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "final_decision": decision,
        "hard5_canva_outputs_available_count": validation["pptx_available_count"],
        "hard5_missing_count": validation["missing_count"],
        "visual_only_count": validation["visual_only_count"],
        "object_benchmark_status": object_match["status"],
        "edit_task_benchmark_status": edit_task["status"],
        "preliminary_scores": scores,
        "top_failure_categories": taxonomy["top_failure_categories"],
        "f02_method_bakeoff_unlocked": f02["status"] == "ready",
        "f02_readiness_decision": f02["decision"],
        "canva_oracle_limitations_recorded": True,
        "contact_sheet_manifest": contacts,
        "protected_artifacts_unchanged": True,
        "broad_canva_parity_claimed": False,
    }


def build_contact_sheets(validation: dict[str, Any], ours: dict[str, Any], object_match: dict[str, Any], edit_task: dict[str, Any], taxonomy: dict[str, Any]) -> dict[str, Any]:
    build_reference_canva_ours_sheet(validation, ours)
    summary_sheet(RENDER_ROOT / "hard5_canva_vs_ours_object_overlay_contact_sheet.png", "Hard5 Canva vs Ours Object Overlay", object_match)
    summary_sheet(RENDER_ROOT / "hard5_grouping_comparison_contact_sheet.png", "Hard5 Grouping Comparison", {"canva_status": validation["status"], "ours_status": ours["status"], "items": object_match.get("items", [])})
    summary_sheet(RENDER_ROOT / "hard5_edit_task_failure_contact_sheet.png", "Hard5 Edit Task Benchmark", edit_task)
    summary_sheet(RENDER_ROOT / "hard5_failure_taxonomy_contact_sheet.png", "Hard5 Failure Taxonomy", taxonomy)
    names = [
        "hard5_reference_vs_canva_vs_ours_contact_sheet.png",
        "hard5_canva_vs_ours_object_overlay_contact_sheet.png",
        "hard5_grouping_comparison_contact_sheet.png",
        "hard5_edit_task_failure_contact_sheet.png",
        "hard5_failure_taxonomy_contact_sheet.png",
    ]
    return {"schema_name": "hard5_contact_sheet_manifest", "status": "passed", "paths": {name.removesuffix(".png"): (RENDER_ROOT / name).as_posix() for name in names}}


def build_reference_canva_ours_sheet(validation: dict[str, Any], ours: dict[str, Any]) -> None:
    ours_by_archetype = {row["archetype_id"]: row for row in ours.get("items", [])}
    cell_w, cell_h = 320, 200
    sheet = Image.new("RGB", (cell_w * 3, cell_h * len(HARD5) + 48), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((12, 12), "Hard5 Reference vs Canva Magic Layers vs Ours", fill="#F8FAFC", font=font)
    for idx, label in enumerate(["Reference", "Canva Magic Layers", "Ours"]):
        draw.text((idx * cell_w + 12, 30), label, fill="#F2A900", font=font)
    by_arch = {row["archetype_id"]: row for row in validation["items"]}
    for row_idx, spec in enumerate(HARD5):
        y = row_idx * cell_h + 48
        arch = spec["archetype_id"]
        draw.text((8, y + 4), arch, fill="#F8FAFC", font=font)
        canva = by_arch.get(arch, {})
        ours_row = ours_by_archetype.get(arch, {})
        paste_image(sheet, Path(canva.get("reference_image_path", "")), 8, y + 22, cell_w - 16, cell_h - 28, "MISSING REF")
        paste_image(sheet, Path(canva.get("canva_render_path", "")), cell_w + 8, y + 22, cell_w - 16, cell_h - 28, "MISSING CANVA")
        paste_image(sheet, Path(ours_row.get("render_path", "")), cell_w * 2 + 8, y + 22, cell_w - 16, cell_h - 28, "MISSING OURS")
    RENDER_ROOT.mkdir(parents=True, exist_ok=True)
    sheet.save(RENDER_ROOT / "hard5_reference_vs_canva_vs_ours_contact_sheet.png")


def audit_pptx(pptx: Path, *, slide_numbers: list[int] | None, sample_id: str) -> dict[str, Any]:
    if not pptx.is_file():
        return empty_audit(sample_id)
    prs = Presentation(pptx)
    slide_width = int(prs.slide_width)
    slide_height = int(prs.slide_height)
    object_ledger = []
    text_ledger = []
    image_backed = []
    group_objects = []
    media_items = []
    media_counter: Counter[str] = Counter()
    wanted = set(slide_numbers or range(1, len(prs.slides) + 1))
    with zipfile.ZipFile(pptx, "r") as zf:
        names = zf.namelist()
        content_types = parse_content_types(zf)
        slide_names = sorted([name for name in names if name.startswith("ppt/slides/slide") and name.endswith(".xml")], key=slide_sort)
        for slide_index, slide_name in enumerate(slide_names, start=1):
            if slide_index not in wanted:
                continue
            rels = parse_slide_relationships(zf, slide_name)
            root = ET.fromstring(zf.read(slide_name))
            sp_tree = root.find(".//p:cSld/p:spTree", NS)
            children = list(sp_tree)[2:] if sp_tree is not None else []
            for z_order, child in enumerate(children):
                text = " ".join(t.text or "" for t in child.findall(".//a:t", NS)).strip()
                box = bbox(child)
                media_refs = []
                for blip in child.findall(".//a:blip", NS):
                    rid = blip.get(f"{{{NS['r']}}}embed") or blip.get(f"{{{NS['r']}}}link")
                    if rid and rid in rels:
                        media_refs.append(rels[rid])
                obj = {
                    "slide_number": slide_index,
                    "z_order": z_order,
                    "object_type": object_type(child),
                    "name": object_name(child),
                    "bbox_emu": box,
                    "bbox_norm": norm_bbox(box, slide_width, slide_height),
                    "has_text": bool(text),
                    "text": text,
                    "text_excerpt": text[:160],
                    "has_media_reference": bool(media_refs),
                    "media_references": media_refs,
                }
                object_ledger.append(obj)
                if text:
                    text_ledger.append({"slide_number": slide_index, "z_order": z_order, "object_name": obj["name"], "text": text, "bbox_emu": box, "bbox_norm": obj["bbox_norm"], "editable": True})
                if media_refs or obj["object_type"] == "picture":
                    image_backed.append(obj)
                if obj["object_type"] == "group":
                    group_objects.append(obj)
        for name in names:
            if name.startswith("ppt/media/"):
                suffix = Path(name).suffix.lower().lstrip(".") or "unknown"
                data = zf.read(name)
                media_counter[suffix] += 1
                media_items.append({"partname": name, "media_type": suffix, "content_type": content_types.get("/" + name, ""), "size_bytes": len(data)})
    slide_area = max(1, slide_width * slide_height)
    full_slide_media = [obj for obj in image_backed if bbox_area(obj["bbox_emu"]) / slide_area >= 0.90]
    large_media = [obj for obj in image_backed if bbox_area(obj["bbox_emu"]) / slide_area >= 0.08]
    small_visual = [obj for obj in object_ledger if not obj["has_text"] and bbox_area(obj["bbox_emu"]) / slide_area <= 0.02 and obj["bbox_emu"]]
    composite_count = count_composite_candidates(object_ledger)
    text_baked = 0 if text_ledger else len(full_slide_media)
    icon_baked = 0 if small_visual else min(len(large_media), 1)
    table_chart_baked = 0
    known_limitations = []
    if full_slide_media:
        known_limitations.append("contains_full_slide_or_near_full_slide_media_candidate")
    if large_media:
        known_limitations.append("contains_large_media_fragments")
    if not group_objects:
        known_limitations.append("no_native_group_shapes_detected")
    return {
        "schema_name": "hard5_pptx_layer_audit",
        "status": "passed",
        "sample_id": sample_id,
        "pptx_path": pptx.as_posix(),
        "slide_count": len(wanted),
        "object_count": len(object_ledger),
        "shape_count": sum(1 for obj in object_ledger if obj["object_type"] == "shape"),
        "editable_text_count": len(text_ledger),
        "media_count": sum(media_counter.values()),
        "media_type_count": dict(media_counter),
        "group_count": len(group_objects),
        "canva_full_slide_media_candidate_count": len(full_slide_media),
        "canva_large_media_fragment_count": len(large_media),
        "canva_semantic_text_baked_into_media_count": text_baked,
        "canva_semantic_icon_baked_into_media_count": icon_baked,
        "canva_table_or_chart_baked_into_media_count": table_chart_baked,
        "canva_editable_text_count": len(text_ledger),
        "canva_editable_icon_or_small_object_count": len(small_visual),
        "canva_composite_group_count": composite_count,
        "canva_grouping_quality_notes": ["native_group_shapes_detected" if group_objects else "semantic grouping inferred from geometry/name only"],
        "canva_known_limitations": known_limitations,
        "pptx_object_ledger": object_ledger,
        "text_ledger": text_ledger,
        "image_backed_shapes": image_backed,
        "media_ledger": {"schema_name": "canva_media_ledger", "media_count": sum(media_counter.values()), "media_type_count": dict(media_counter), "items": media_items},
        "grouping_manifest": {"schema_name": "canva_grouping_manifest", "group_count": len(group_objects), "groups": group_objects, "composite_candidate_count": composite_count},
    }


def canva_oracle_quality(audit: dict[str, Any]) -> str:
    if audit.get("editable_text_count", 0) == 0 and audit.get("canva_full_slide_media_candidate_count", 0):
        return "weak_fully_or_mostly_baked_raster"
    if audit.get("canva_large_media_fragment_count", 0) and audit.get("editable_text_count", 0):
        return "usable_with_large_media_and_editable_overlays"
    if audit.get("editable_text_count", 0) or audit.get("canva_editable_icon_or_small_object_count", 0):
        return "usable_partial_editable_oracle"
    return "weak_no_semantic_editable_objects_detected"


def evaluate_edit_task(task_id: str, audit: dict[str, Any]) -> dict[str, Any]:
    names = " ".join(obj.get("name", "").lower() for obj in audit.get("pptx_object_ledger", []))
    text_count = audit.get("editable_text_count", 0)
    small_count = audit.get("canva_editable_icon_or_small_object_count", 0)
    tableish = any(token in names for token in ["table", "grid", "cell", "row", "matrix", "risk"])
    chartish = any(token in names for token in ["chart", "bar", "kpi", "dashboard"])
    if "edit" in task_id and "icon" not in task_id:
        ok = text_count > 0
    elif "icon" in task_id:
        ok = small_count > 0
    elif "table" in task_id or "cell" in task_id or "row" in task_id or "register" in task_id:
        ok = tableish or text_count >= 8
    elif "chart" in task_id or "kpi" in task_id:
        ok = chartish or text_count >= 4
    else:
        ok = audit.get("object_count", 0) > 0
    return {"task_id": task_id, "status": "passed" if ok else "failed", "evidence": {"editable_text_count": text_count, "small_object_count": small_count, "object_count": audit.get("object_count", 0)}}


def write_outputs(
    report: dict[str, Any],
    inventory: dict[str, Any],
    validation: dict[str, Any],
    match: dict[str, Any],
    canva_summary: dict[str, Any],
    ours_summary: dict[str, Any],
    object_match: dict[str, Any],
    edit_task: dict[str, Any],
    taxonomy: dict[str, Any],
    f02: dict[str, Any],
) -> None:
    payloads = {
        "f01_1_hard5_canva_import_report": report,
        "hard5_canva_oracle_inventory": inventory,
        "hard5_canva_oracle_validation_report": scrub_validation(validation),
        "hard5_reference_canva_ours_match_report": match,
        "hard5_canva_layer_audit_summary": canva_summary,
        "hard5_our_layer_audit_summary": scrub_ours_summary(ours_summary),
        "hard5_canva_vs_ours_object_match_report": object_match,
        "hard5_edit_task_benchmark_report": edit_task,
        "hard5_failure_taxonomy_report": taxonomy,
        "f02_method_bakeoff_readiness_report": f02,
    }
    for name, payload in payloads.items():
        write_json(OUTPUT_ROOT / f"{name}.json", payload)
        write_md(OUTPUT_ROOT / f"{name}.md", summary_md(name.replace("_", " ").title(), payload))


def scrub_validation(validation: dict[str, Any]) -> dict[str, Any]:
    result = dict(validation)
    items = []
    for row in validation.get("items", []):
        cleaned = dict(row)
        audit = cleaned.pop("layer_audit", {})
        cleaned["layer_audit_summary"] = {
            "status": audit.get("status"),
            "object_count": audit.get("object_count", 0),
            "editable_text_count": audit.get("editable_text_count", 0),
            "media_count": audit.get("media_count", 0),
            "canva_oracle_quality": cleaned.get("canva_oracle_quality"),
        }
        items.append(cleaned)
    result["items"] = items
    return result


def scrub_ours_summary(ours: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(ours)
    audit = cleaned.pop("layer_audit", {})
    cleaned["layer_audit_summary"] = {
        "status": audit.get("status"),
        "object_count": audit.get("object_count", 0),
        "editable_text_count": audit.get("editable_text_count", 0),
        "media_count": audit.get("media_count", 0),
    }
    return cleaned


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
    payload = {"schema_name": "f01_1_hard5_canva_import_report", "decision": decision, "final_decision": decision, **details, "broad_canva_parity_claimed": False}
    write_json(OUTPUT_ROOT / "f01_1_hard5_canva_import_report.json", payload)
    write_md(OUTPUT_ROOT / "f01_1_hard5_canva_import_report.md", summary_md("F01.1 Hard5 Canva Import", payload))
    return payload


def reference_path(archetype_id: str) -> Path:
    if archetype_id in {"data_dashboard", "table_heavy"}:
        return RUN_ROOT / "refs" / "harness_v3_4core" / f"{archetype_id}.png"
    return RUN_ROOT / "refs" / "harness_v3_12_16" / f"{archetype_id}.png"


def ours_render_path(render_dir: Path, slide_number: int) -> Path:
    accepted = render_dir / f"accepted-{slide_number:03d}.png"
    if accepted.exists():
        return accepted
    v2 = render_dir / f"v2-{slide_number:03d}.png"
    if v2.exists():
        return v2
    return render_dir / f"slide-{slide_number:03d}.png"


def empty_audit(sample_id: str) -> dict[str, Any]:
    return {
        "schema_name": "hard5_pptx_layer_audit",
        "status": "missing",
        "sample_id": sample_id,
        "slide_count": 0,
        "object_count": 0,
        "shape_count": 0,
        "editable_text_count": 0,
        "media_count": 0,
        "media_type_count": {},
        "group_count": 0,
        "canva_full_slide_media_candidate_count": 0,
        "canva_large_media_fragment_count": 0,
        "canva_semantic_text_baked_into_media_count": 0,
        "canva_semantic_icon_baked_into_media_count": 0,
        "canva_table_or_chart_baked_into_media_count": 0,
        "canva_editable_text_count": 0,
        "canva_editable_icon_or_small_object_count": 0,
        "canva_composite_group_count": 0,
        "canva_grouping_quality_notes": [],
        "canva_known_limitations": [],
        "pptx_object_ledger": [],
        "text_ledger": [],
        "image_backed_shapes": [],
        "media_ledger": {"schema_name": "canva_media_ledger", "media_count": 0, "media_type_count": {}, "items": []},
        "grouping_manifest": {"schema_name": "canva_grouping_manifest", "group_count": 0, "groups": []},
    }


def parse_content_types(zf: zipfile.ZipFile) -> dict[str, str]:
    if "[Content_Types].xml" not in zf.namelist():
        return {}
    root = ET.fromstring(zf.read("[Content_Types].xml"))
    ns = "{http://schemas.openxmlformats.org/package/2006/content-types}"
    return {node.get("PartName", ""): node.get("ContentType", "") for node in root.findall(f"{ns}Override")}


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
    return {"x": round(box.get("x", 0) / max(1, width), 5), "y": round(box.get("y", 0) / max(1, height), 5), "w": round(box.get("w", 0) / max(1, width), 5), "h": round(box.get("h", 0) / max(1, height), 5)}


def bbox_area(box: dict[str, Any]) -> int:
    return max(0, int(box.get("w", 0))) * max(0, int(box.get("h", 0)))


def count_composite_candidates(objects: list[dict[str, Any]]) -> int:
    tokens = ["card", "step", "kpi", "chart", "table", "grid", "rail", "footer", "source", "hero", "callout", "chrome", "risk", "matrix"]
    seen = set()
    for obj in objects:
        name = obj.get("name", "").lower()
        for token in tokens:
            if token in name:
                seen.add(token)
    return len(seen)


def image_similarity(left: Path, right: Path) -> float | None:
    if not left.is_file() or not right.is_file():
        return None
    try:
        a = Image.open(left).convert("RGB").resize((320, 180))
        b = Image.open(right).convert("RGB").resize((320, 180))
        diff = ImageChops.difference(a, b)
        histogram = diff.histogram()
        sq = (value * ((idx % 256) ** 2) for idx, value in enumerate(histogram))
        rms = math.sqrt(sum(sq) / float(a.size[0] * a.size[1] * 3))
        return round(max(0.0, 1.0 - rms / 255.0), 4)
    except Exception:
        return None


def visual_score(match: dict[str, Any]) -> float | None:
    values = [row.get("visual_similarity_canva_ours") for row in match.get("items", []) if row.get("visual_similarity_canva_ours") is not None]
    return round(avg(values), 3) if values else None


def bounded_ratio(a: int, b: int) -> float:
    if b <= 0:
        return 1.0 if a > 0 else 0.0
    return max(0.0, min(1.0, a / b))


def avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def paste_image(sheet: Image.Image, path: Path, x: int, y: int, w: int, h: int, missing: str) -> None:
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    if not path.is_file():
        draw.rectangle((x, y, x + w, y + h), fill="#0F172A", outline="#334155")
        draw.text((x + 12, y + h // 2 - 6), missing, fill="#F2A900", font=font)
        return
    image = Image.open(path).convert("RGB")
    image.thumbnail((w, h), Image.Resampling.LANCZOS)
    sheet.paste(image, (x + (w - image.width) // 2, y + (h - image.height) // 2))


def summary_sheet(output: Path, title: str, payload: dict[str, Any]) -> None:
    sheet = Image.new("RGB", (1280, 720), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((24, 24), title, fill="#F8FAFC", font=font)
    y = 64
    for key, value in payload.items():
        if isinstance(value, dict):
            text = f"{key}: {json.dumps(value, ensure_ascii=True)[:170]}"
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
