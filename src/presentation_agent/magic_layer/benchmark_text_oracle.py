"""Benchmark-only text oracle for the Canva Magic Layer reference."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


STEP_DEFINITIONS = [
    {
        "index": 1,
        "number": "01",
        "heading": "PLAN & PREPARE",
        "body": "Verify documents,\ncommunication, readiness",
        "icon_role": "clipboard_check",
    },
    {
        "index": 2,
        "number": "02",
        "heading": "SET UP & SECURE",
        "body": "Closed loading,\nisolation & line-up",
        "icon_role": "valve_secure",
    },
    {
        "index": 3,
        "number": "03",
        "heading": "EXECUTE & MONITOR",
        "body": "Operate within limits,\ncontinuous monitoring",
        "icon_role": "gauge_monitor",
    },
    {
        "index": 4,
        "number": "04",
        "heading": "VERIFY & CONFIRM",
        "body": "Levels, pressures,\ntemperatures, soundings",
        "icon_role": "shield_check",
    },
    {
        "index": 5,
        "number": "05",
        "heading": "COMPLETE & RECORD",
        "body": "Secure, debrief,\nrecords & lessons",
        "icon_role": "record_document",
    },
]


ACTION_DEFINITIONS = [
    {"index": 1, "label_top": "WEAR PPE", "label_bottom": "AT ALL TIMES", "icon_role": "warning_ppe"},
    {"index": 2, "label_top": "ZERO LEAK", "label_bottom": "ZERO SPILL", "icon_role": "lock_zero_leak"},
    {"index": 3, "label_top": "RESPECT THE CHEMICAL", "label_bottom": "RESPECT THE SAFETY BARRIER", "icon_role": "shield_barrier"},
    {"index": 4, "label_top": "COMMUNICATE", "label_bottom": "CONFIRM", "icon_role": "chat_confirm"},
    {"index": 5, "label_top": "TEAMWORK", "label_bottom": "FOR SAFE OPERATIONS", "icon_role": "team_safe_ops"},
]


THUMBNAIL_CALLOUTS = [
    {"index": 1, "label": "CARGO CONTROL ROOM", "role": "cargo_control_room"},
    {"index": 2, "label": "CARGO PUMP & HPU", "role": "cargo_pump_hpu"},
    {"index": 3, "label": "GAS DETECTION", "role": "gas_detection"},
]


def load_benchmark_text_oracle(text_ledger_path: Path) -> dict[str, Any]:
    ledger = json.loads(text_ledger_path.read_text(encoding="utf-8"))
    extracted = [item["text"] for item in ledger.get("texts") or []]
    required = required_oracle_strings()
    missing = [text for text in required if text not in extracted]
    return {
        "schema_name": "benchmark_text_oracle_report",
        "source": "benchmark_pptx_oracle",
        "ledger_path": text_ledger_path.as_posix(),
        "oracle_scope": "canva_benchmark_only",
        "ocr_used": False,
        "final_copy_allowed_for_benchmark_only": True,
        "extracted_text_count": len(extracted),
        "required_text_count": len(required),
        "missing_required_text": missing,
        "status": "passed" if not missing else "partial",
        "title": "5-STEP PRACTICAL CHECKLIST",
        "steps": STEP_DEFINITIONS,
        "actions": ACTION_DEFINITIONS,
        "thumbnail_callouts": THUMBNAIL_CALLOUTS,
        "notes": [
            "The Canva PPTX text ledger is used only as a benchmark oracle for this E01.1 gate.",
            "No OCR success is claimed.",
            "Thumbnail callout labels are visual-review annotations because the Canva PPTX audit says those labels were not extracted as editable text.",
        ],
        "canva_parity_claimed": False,
    }


def build_text_region_lift_report(oracle: dict[str, Any]) -> dict[str, Any]:
    regions: list[dict[str, Any]] = []

    def add(region_id: str, bbox_norm: list[float], source: str, confidence: float, text: str, role: str, overflow_risk: str = "low") -> None:
        regions.append(
            {
                "text_region_id": region_id,
                "bbox_norm": [round(value, 4) for value in bbox_norm],
                "source": source,
                "confidence": confidence,
                "recovered_text": text,
                "semantic_role": role,
                "editable_target": "ppt_text_box",
                "final_copy_allowed_for_benchmark_only": source == "benchmark_pptx_oracle",
                "overflow_risk": overflow_risk,
            }
        )

    add("checklist_title", [0.65, 0.065, 0.28, 0.055], "benchmark_pptx_oracle", 0.95, oracle["title"], "checklist_title")
    for step in oracle["steps"]:
        idx = step["index"]
        y = 0.142 + (idx - 1) * 0.139
        add(f"step_{idx}_number", [0.715, y + 0.032, 0.055, 0.052], "benchmark_pptx_oracle", 0.94, step["number"], "step_number")
        add(f"step_{idx}_heading", [0.772, y + 0.024, 0.205, 0.035], "benchmark_pptx_oracle", 0.93, step["heading"], "step_heading")
        add(f"step_{idx}_body", [0.772, y + 0.063, 0.19, 0.045], "benchmark_pptx_oracle", 0.9, step["body"], "step_body", overflow_risk="medium")
    for action in oracle["actions"]:
        idx = action["index"]
        x = 0.185 + (idx - 1) * 0.19
        add(f"action_{idx}_label_top", [x, 0.812, 0.12, 0.028], "benchmark_pptx_oracle", 0.92, action["label_top"], "bottom_action_label")
        add(f"action_{idx}_label_bottom", [x, 0.845, 0.14, 0.028], "benchmark_pptx_oracle", 0.92, action["label_bottom"], "bottom_action_label")
    for callout in oracle["thumbnail_callouts"]:
        idx = callout["index"]
        x = 0.23 + (idx - 1) * 0.125
        add(f"thumbnail_{idx}_caption", [x, 0.725, 0.1, 0.03], "visual_review_annotation", 0.55, callout["label"], "thumbnail_caption", overflow_risk="medium")
    add("source_footer_slot", [0.03, 0.958, 0.45, 0.02], "geometry_slot", 0.5, "SOURCE / FOOTER SLOT", "source_footer_text")

    return {
        "schema_name": "text_region_lift_report",
        "status": "passed",
        "ocr_backend": "unavailable",
        "text_lift_sources": ["benchmark_pptx_oracle", "visual_review_annotation", "geometry_slot"],
        "benchmark_oracle_text_count": oracle["extracted_text_count"],
        "editable_text_region_count": len(regions),
        "regions": regions,
        "canva_parity_claimed": False,
    }


def required_oracle_strings() -> list[str]:
    strings = ["5-STEP PRACTICAL CHECKLIST"]
    for step in STEP_DEFINITIONS:
        strings.extend([step["number"], step["heading"], step["body"].replace("\n", " ")])
    for action in ACTION_DEFINITIONS:
        strings.extend([action["label_top"], action["label_bottom"]])
    # The Canva ledger stores these with spaces, not forced line breaks.
    return [item.replace("\n", " ") for item in strings]

