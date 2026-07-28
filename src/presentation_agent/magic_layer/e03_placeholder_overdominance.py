"""Placeholder dominance checks for E03 visual quality."""

from __future__ import annotations

from collections import Counter
from typing import Any


PLACEHOLDER_FRAGMENTS = (
    "editable slot",
    "title placeholder",
    "subtitle placeholder",
    "source / footer placeholder",
    "footer placeholder",
    "placeholder",
)


def evaluate_placeholder_overdominance(
    slide_records: list[dict[str, Any]],
    *,
    warn_ratio: float = 0.45,
    fail_ratio: float = 0.72,
    repeated_fail_count: int = 24,
) -> dict[str, Any]:
    text_values: list[str] = []
    for slide in slide_records:
        text_values.extend(str(value).strip() for value in slide.get("text_values", []) if str(value).strip())
    placeholder_values = [value for value in text_values if is_placeholder_text(value)]
    repeated = Counter(placeholder_values)
    repeated_count = sum(count for count in repeated.values() if count > 1)
    total = len(text_values)
    ratio = round(len(placeholder_values) / total, 4) if total else 0.0
    failures: list[str] = []
    warnings: list[str] = []
    if ratio >= fail_ratio:
        failures.append("placeholder_text_ratio_too_high")
    elif ratio >= warn_ratio:
        warnings.append("placeholder_text_ratio_high")
    if repeated_count >= repeated_fail_count:
        failures.append("repeated_placeholder_string_count_too_high")
    elif repeated_count:
        warnings.append("repeated_placeholder_strings_present")
    if any(value.lower() == "editable slot" for value in placeholder_values):
        warnings.append("generic_editable_slot_label_present")
    return {
        "schema_name": "placeholder_overdominance_report",
        "status": "failed" if failures else ("warning" if warnings else "passed"),
        "text_run_count": total,
        "placeholder_text_count": len(placeholder_values),
        "placeholder_text_ratio": ratio,
        "repeated_placeholder_string_count": repeated_count,
        "repeated_placeholder_strings": dict(sorted(repeated.items())),
        "failures": sorted(set(failures)),
        "warnings": sorted(set(warnings)),
        "canva_parity_claimed": False,
    }


def is_placeholder_text(value: str) -> bool:
    normalized = " ".join(value.lower().split())
    if normalized == "slot":
        return True
    return any(fragment in normalized for fragment in PLACEHOLDER_FRAGMENTS)
