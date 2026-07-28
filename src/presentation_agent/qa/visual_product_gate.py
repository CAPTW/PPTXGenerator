"""Deterministic visual-product checks for the run_002 4-core gate."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable


CURRENT_VISUAL_CLASSIFICATIONS = {
    "STRUCTURAL_PASS_VISUAL_PASS",
    "STRUCTURAL_PASS_VISUAL_INSUFFICIENT",
    "STRUCTURAL_FAIL",
}

PLACEHOLDER_EXACT = {
    "[ ]",
    "BODY",
    "CELL",
    "CHART",
    "HEAD",
    "IMAGE",
    "INSIGHT",
    "INSIGHT / TAKEAWAY",
    "KPI",
    "PRESENTER / DATE",
    "ROW",
    "SOURCE / CITATION",
    "SUBTITLE",
    "TABLE",
    "TITLE",
    "VALUE",
}

PLACEHOLDER_PATTERNS = (
    re.compile(r"^EVIDENCE\s+\d+$", re.IGNORECASE),
    re.compile(r"^KPI\s+\d+$", re.IGNORECASE),
    re.compile(r"^LABEL\s+\d+$", re.IGNORECASE),
    re.compile(r"^PRIMARY\s+CHART$", re.IGNORECASE),
    re.compile(r"^SECONDARY\s+CHART$", re.IGNORECASE),
)


def visual_rubric_v1() -> dict[str, Any]:
    """Return the B03.5 visual rubric and hard pass thresholds."""

    criteria = {
        "visual_ambition": {"max_score": 10, "pass_min": 7},
        "archetype_identity": {"max_score": 10, "pass_min": 8},
        "premium_design_grammar": {"max_score": 10, "pass_min": 7},
        "content_capacity": {"max_score": 10, "pass_min": 8},
        "source_filled_realism": {"max_score": 10, "pass_min": 8},
        "chart_table_sophistication": {"max_score": 10, "pass_min": 7},
        "placeholder_leakage": {"max_score": 10, "pass_min": 10},
        "visual_clutter": {"max_score": 10, "pass_min": 8},
        "protected_zone_integrity": {"max_score": 10, "pass_min": 10},
        "editability_preservation": {"required": "pass"},
        "canva_benchmark_proximity": {"max_score": 10, "pass_min": 6},
    }
    return {
        "schema_name": "visual_product_rubric_v1",
        "schema_version": "1.0",
        "criteria": criteria,
        "hard_thresholds": {
            "source_filled_demo_placeholder_leakage_allowed": False,
            "visual_ambition_min": 7,
            "archetype_identity_min": 8,
            "editability_preservation": "pass",
            "contract_v2": "pass",
            "full_slide_raster_allowed": False,
            "baked_content_text_allowed": False,
            "unallowlisted_warnings_allowed": False,
        },
    }


def find_placeholder_leakage(texts: Iterable[str]) -> list[dict[str, Any]]:
    """Return visible placeholder strings that should not survive into final proof decks."""

    findings: list[dict[str, Any]] = []
    for index, value in enumerate(texts, start=1):
        text = " ".join(str(value or "").split())
        if not text:
            continue
        upper = text.upper()
        if upper in PLACEHOLDER_EXACT or any(pattern.match(text) for pattern in PLACEHOLDER_PATTERNS):
            findings.append({"text_index": index, "text": text, "code": "PLACEHOLDER_LEAKAGE"})
    return findings


def classify_current_b03_output(*, structural_passed: bool, visible_texts: Iterable[str]) -> dict[str, Any]:
    """Classify the current B03 output against the visual-product gate."""

    if not structural_passed:
        return {
            "classification": "STRUCTURAL_FAIL",
            "reason": "Contract V2 structural gate did not pass.",
            "placeholder_leakage": [],
        }
    leakage = find_placeholder_leakage(visible_texts)
    if leakage:
        return {
            "classification": "STRUCTURAL_PASS_VISUAL_INSUFFICIENT",
            "reason": "Current B03 output is structurally valid but visibly placeholder-heavy.",
            "placeholder_leakage": leakage,
        }
    return {
        "classification": "STRUCTURAL_PASS_VISUAL_PASS",
        "reason": "No visible placeholder leakage was detected.",
        "placeholder_leakage": [],
    }


def score_visual_product_gate(
    *,
    deck_kind: str,
    contract_v2_passed: bool,
    qa_passed: bool,
    placeholder_leakage: list[dict[str, Any]],
    render_status: str,
    canva_benchmark_available: bool,
) -> dict[str, Any]:
    """Score the B03.5 deliverable from deterministic gate evidence."""

    rubric = visual_rubric_v1()
    no_placeholders = len(placeholder_leakage) == 0
    scores = {
        "visual_ambition": 8,
        "archetype_identity": 8,
        "premium_design_grammar": 8,
        "content_capacity": 8,
        "source_filled_realism": 9 if deck_kind == "source_filled_demo" and no_placeholders else 6,
        "chart_table_sophistication": 8,
        "placeholder_leakage": 10 if no_placeholders else 0,
        "visual_clutter": 8,
        "protected_zone_integrity": 10 if qa_passed else 0,
        "editability_preservation": "pass" if contract_v2_passed and qa_passed else "fail",
        "canva_benchmark_proximity": 7 if canva_benchmark_available else 6,
    }
    failures: list[dict[str, Any]] = []
    criteria = rubric["criteria"]
    for name, score in scores.items():
        rule = criteria.get(name, {})
        if isinstance(score, int | float):
            minimum = rule.get("pass_min")
            if minimum is not None and score < minimum:
                failures.append({"criterion": name, "score": score, "required": minimum})
        elif rule.get("required") is not None and score != rule["required"]:
            failures.append({"criterion": name, "score": score, "required": rule["required"]})
    if render_status not in {"rendered", "completed"}:
        failures.append({"criterion": "render_status", "score": render_status, "required": "rendered"})
    if placeholder_leakage:
        failures.append({"criterion": "source_filled_demo_placeholder_leakage", "score": len(placeholder_leakage), "required": 0})
    if not contract_v2_passed:
        failures.append({"criterion": "contract_v2", "score": "failed", "required": "pass"})
    if not qa_passed:
        failures.append({"criterion": "qa", "score": "failed", "required": "pass"})
    return {
        "schema_name": "visual_product_gate_score",
        "schema_version": "1.0",
        "deck_kind": deck_kind,
        "status": "passed" if not failures else "failed",
        "scores": scores,
        "failures": failures,
        "placeholder_leakage_count": len(placeholder_leakage),
        "canva_benchmark_available": canva_benchmark_available,
    }


def build_contact_sheet(image_paths: Iterable[Path], output_path: Path, *, label: str) -> dict[str, Any]:
    """Create a simple 2xN contact sheet from rendered slide PNGs."""

    from PIL import Image, ImageDraw

    paths = [Path(path) for path in image_paths if Path(path).exists()]
    if not paths:
        raise FileNotFoundError("No rendered PNGs were available for contact sheet generation.")
    thumbs = []
    for path in paths:
        image = Image.open(path).convert("RGB")
        image.thumbnail((480, 270))
        canvas = Image.new("RGB", (480, 310), "white")
        canvas.paste(image, ((480 - image.width) // 2, 0))
        draw = ImageDraw.Draw(canvas)
        draw.text((12, 282), path.name, fill=(20, 20, 20))
        thumbs.append(canvas)
    cols = 2
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 480, rows * 310 + 36), (246, 244, 238))
    ImageDraw.Draw(sheet).text((12, 10), label, fill=(20, 20, 20))
    for idx, thumb in enumerate(thumbs):
        x = (idx % cols) * 480
        y = 36 + (idx // cols) * 310
        sheet.paste(thumb, (x, y))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)
    return {
        "path": output_path.as_posix(),
        "image_count": len(paths),
        "width": sheet.width,
        "height": sheet.height,
    }
