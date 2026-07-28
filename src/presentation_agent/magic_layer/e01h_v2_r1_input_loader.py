"""Input loading helpers for the isolated E01H-V2-R1 repair run."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.e01h_v2_r1_report import read_json


REQUIRED_CASE_FILES = [
    "reference_image.png",
    "source_layer_truth.json",
]


def discover_r1_validation_cases(e01h_v2_dir: str | Path) -> list[dict[str, Any]]:
    root = Path(e01h_v2_dir) / "validation_cases"
    cases = []
    for case_dir in sorted(root.iterdir()) if root.exists() else []:
        if not case_dir.is_dir():
            continue
        truth = read_json(case_dir / "source_layer_truth.json")
        cases.append(
            {
                "case_id": case_dir.name,
                "source_dir": case_dir,
                "reference_pdf": case_dir / "reference.pdf",
                "reference_image": case_dir / "reference_image.png",
                "source_layer_truth": truth,
                "requires_chart": _has_role(truth, "chart"),
                "requires_table": _has_role(truth, "table"),
                "missing_required_files": [name for name in REQUIRED_CASE_FILES if not (case_dir / name).exists()],
            }
        )
    return cases


def stage_r1_case_inputs(case: dict[str, Any], output_dir: str | Path) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    staged = dict(case)
    for name in ["reference.pdf", "reference_image.png", "source_layer_truth.json"]:
        source = Path(case["source_dir"]) / name
        if source.exists():
            shutil.copy2(source, output / name)
    staged["case_dir"] = output
    staged["reference_pdf"] = output / "reference.pdf"
    staged["reference_image"] = output / "reference_image.png"
    staged["source_layer_truth"] = read_json(output / "source_layer_truth.json")
    return staged


def validate_r1_prerequisites(
    e01h_v2_dir: str | Path,
    qa_dir: str | Path,
    pdfb02_dir: str | Path,
) -> dict[str, Any]:
    e01h_v2 = Path(e01h_v2_dir)
    qa = Path(qa_dir)
    pdfb02 = Path(pdfb02_dir)
    required = [
        e01h_v2 / "e01h_v2_final_decision.json",
        e01h_v2 / "e01h_v2_engine_policy.json",
        e01h_v2 / "default_strategy_policy.json",
        e01h_v2 / "pdf_signal_integration_policy.json",
        e01h_v2 / "visual_backplate_policy_v2.json",
        e01h_v2 / "semantic_native_policy_v2.json",
        e01h_v2 / "style_preservation_policy.json",
        e01h_v2 / "clone_substitution_restriction_policy.json",
        qa / "e01h_v2_qa_final_decision.json",
        qa / "e01h_v2_repair_requirements.json",
        qa / "e02h_v2_readiness_after_e01h_v2_qa.json",
        pdfb02 / "pdfb02_final_decision.json",
        pdfb02 / "canva_plus_conversion_methodology_update_v2.json",
        pdfb02 / "strategy_discrimination_report.json",
        pdfb02 / "pdf_extraction_signal_value_report.json",
    ]
    missing = [path.as_posix() for path in required if not path.exists()]
    e01_decision = read_json(e01h_v2 / "e01h_v2_final_decision.json").get("decision")
    qa_decision = read_json(qa / "e01h_v2_qa_final_decision.json").get("decision")
    pdfb02_decision = read_json(pdfb02 / "pdfb02_final_decision.json").get("decision")
    passed = (
        not missing
        and e01_decision == "E01H_V2_PASS_READY_FOR_E02H_V2_GENERALIZATION"
        and qa_decision == "E01H_V2_QA_LOCK_E02H_V2_BASELINE_SHORTCUT_DETECTED"
        and pdfb02_decision == "PDFB02_PASS_READY_FOR_E01H_V2_CONVERSION_ENGINE"
    )
    return {
        "schema_name": "e01h_v2_r1_prerequisite_report",
        "status": "passed" if passed else "failed",
        "missing_inputs": missing,
        "e01h_v2_decision": e01_decision,
        "e01h_v2_qa_decision": qa_decision,
        "pdfb02_decision": pdfb02_decision,
        "canva_parity_claimed": False,
    }


def _has_role(truth: dict[str, Any], role: str) -> bool:
    return any(obj.get("semantic_role") == role for obj in truth.get("table_chart_objects", []))
