"""E00-RX artifact family and write-policy helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping


class ArtifactGovernanceError(AssertionError):
    """Raised when a path violates the E00-RX artifact governance lock."""


PROTECTED_CANONICAL = {
    "outputs/editable_template_spec.final.json",
    "outputs/golden_template_masters.pptx",
    "outputs/final_deck_large_premium.pptx",
}

ACTIVE_E00_RX_ROOT = "design_runs/run_002/outputs/magic_layer_engine_e00_rx_goal_artifact_governance_lock/"
FUTURE_ACTIVE_ROOTS = (
    "design_runs/run_002/outputs/magic_layer_engine_e01_rx_single_reference_gate/",
    "design_runs/run_002/outputs/magic_layer_engine_e02_rx_4core_template_conversion/",
    "design_runs/benchmarks/canva_magic_layer/",
)


def classify_artifact_path(path: str | Path) -> str:
    normalized = _normalize(path)
    lower = normalized.lower()
    if normalized in PROTECTED_CANONICAL:
        return "PROTECTED_CANONICAL"
    if lower.startswith(ACTIVE_E00_RX_ROOT.lower()):
        return "ACTIVE_E00_RX"
    if any(lower.startswith(root.lower()) for root in FUTURE_ACTIVE_ROOTS):
        if "canva_magic_layer" in lower:
            return "MAGIC_LAYER_BENCHMARK"
        if "e01" in lower:
            return "FUTURE_E01_SINGLE_REFERENCE_GATE"
        if "e02" in lower:
            return "FUTURE_E02_CORE_TEMPLATE_GATE"
    if lower.startswith("src/") or lower.startswith("scripts/") or lower.startswith("tests/"):
        return "ACTIVE_CORE"
    if lower.startswith("design_runs/run_002/outputs/repo_failure_audit_r00x_exhaustive/"):
        return "R00X_AUDIT"
    if lower.startswith("design_runs/run_002/outputs/repo_failure_audit_r00/"):
        return "R00_AUDIT"
    if "d07" in lower and ("source" in lower or "bound" in lower):
        return "D07_SOURCE_BOUND_ROUTE_PROOF"
    if "d07" in lower and ("visual" in lower or "asset" in lower):
        return "D07_VISUAL_ASSET_ROUTE_PROOF"
    if "render" in lower or "contact_sheet" in lower:
        return "OLD_RENDER_OUTPUTS"
    if lower.endswith((".png", ".jpg", ".jpeg", ".webp")) and (
        lower.startswith("outputs/") or lower.startswith("design_runs/")
    ):
        return "GENERATED_IMAGE_FLOOD"
    if lower.endswith((".pptx", ".bin")):
        return "UNKNOWN_BINARY_OR_IMAGE"
    return "UNKNOWN_REQUIRES_MANUAL_REVIEW"


def is_active_workspace_path(path: str | Path) -> bool:
    family = classify_artifact_path(path)
    return family in {
        "ACTIVE_CORE",
        "ACTIVE_E00_RX",
        "FUTURE_E01_SINGLE_REFERENCE_GATE",
        "FUTURE_E02_CORE_TEMPLATE_GATE",
        "MAGIC_LAYER_BENCHMARK",
        "PROTECTED_CANONICAL",
    }


def assert_write_allowed(path: str | Path) -> bool:
    normalized = _normalize(path)
    family = classify_artifact_path(path)
    if normalized in PROTECTED_CANONICAL:
        raise ArtifactGovernanceError(f"Protected canonical artifact is read-only: {normalized}")
    if family in {"R00_AUDIT", "R00X_AUDIT", "OLD_RENDER_OUTPUTS", "GENERATED_IMAGE_FLOOD", "UNKNOWN_BINARY_OR_IMAGE"}:
        raise ArtifactGovernanceError(f"Path is not writable in E00-RX policy: {normalized} ({family})")
    if family == "UNKNOWN_REQUIRES_MANUAL_REVIEW":
        raise ArtifactGovernanceError(f"Unknown path requires manual review before write: {normalized}")
    return True


def assert_protected_artifacts_unchanged(pre: Mapping[str, Any], post: Mapping[str, Any]) -> bool:
    pre_rows = _artifact_rows(pre)
    post_rows = _artifact_rows(post)
    missing = sorted(PROTECTED_CANONICAL - set(pre_rows) | PROTECTED_CANONICAL - set(post_rows))
    changed = [
        path
        for path in sorted(PROTECTED_CANONICAL & set(pre_rows) & set(post_rows))
        if str(pre_rows[path].get("sha256", "")).upper() != str(post_rows[path].get("sha256", "")).upper()
        or int(pre_rows[path].get("size_bytes", -1)) != int(post_rows[path].get("size_bytes", -2))
    ]
    if missing or changed:
        raise ArtifactGovernanceError(f"Protected artifact check failed. missing={missing}, changed={changed}")
    return True


def _artifact_rows(report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows = report.get("protected_artifacts") if isinstance(report, Mapping) else None
    if not isinstance(rows, list):
        return {}
    return {str(row.get("path", "")).replace("\\", "/"): row for row in rows if row.get("path")}


def _normalize(path: str | Path) -> str:
    text = str(path).replace("\\", "/")
    marker = "PPTXlocal/"
    if marker in text:
        text = text.split(marker, 1)[1]
    return text.lstrip("./")
