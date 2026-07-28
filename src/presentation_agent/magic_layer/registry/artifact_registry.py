from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .path_classifier import (
    PROTECTED_ARTIFACTS,
    classify_artifact_family,
    is_manual_review_path,
    is_protected_artifact,
    is_quarantined_path,
    normalize_path,
)


ACTIVE_SCAN_ROOTS = [
    "src",
    "scripts",
    "tests",
    "repo_state",
    "design_runs/run_003/fixtures",
    "design_runs/run_003/outputs/a01_rx_artifact_registry_claim_verification_cli",
    "design_runs/run_003/outputs/b03_rx_pptx_native_validation_cli_hardening",
    "design_runs/run_003/outputs/e01p_rx_psd_like_layer_mask_selection_protocol",
    "design_runs/run_003/outputs/b01_rx_render_review_workbench",
    "design_runs/run_003/outputs/t01_rx_template_contract_slot_schema_hardening",
    "design_runs/run_003/outputs/t02_rx_native_reconstruction_planner_editable_spec_builder",
    "design_runs/run_003/outputs/c01_rx_contract_aware_pptx_compiler_skeleton_dry_run",
    "design_runs/run_003/outputs/c02_rx_controlled_minimal_pptx_compile",
    "design_runs/run_003/outputs/c03_rx_controlled_render_b01_review_minimal_pptx",
    "design_runs/benchmarks/canva_magic_layer",
]
ACTIVE_SCAN_FILES = ["package.json", "package-lock.json", "pyproject.toml", "README.md", "AGENTS.md"]


@dataclass
class ArtifactRecord:
    artifact_id: str
    path: str
    normalized_path: str = ""
    exists: bool = True
    kind: str = "UNKNOWN"
    family: str = "UNKNOWN_ACTIVE_FILE"
    role: str = "unknown"
    evidence_class: str = "UNKNOWN_NOT_EVIDENCE"
    product_relevance: str = "not_product_evidence"
    stage_id: str | None = None
    run_id: str | None = None
    source_stage: str | None = None
    active_status: str = "active"
    protected_status: str = "not_protected"
    quarantine_status: str = "not_quarantined"
    manual_review_status: str = "not_manual_review"
    sha256: str | None = None
    size_bytes: int | None = None
    dependencies: list[str] = field(default_factory=list)
    claims_supported: list[str] = field(default_factory=list)
    claims_blocked: list[str] = field(default_factory=list)
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.normalized_path:
            self.normalized_path = normalize_path(self.path)


class ArtifactRegistry:
    def __init__(self, records: Iterable[ArtifactRecord] | None = None) -> None:
        self.records: list[ArtifactRecord] = list(records or [])

    def add(self, record: ArtifactRecord) -> None:
        self.records.append(record)

    def by_path(self, path: str | Path) -> ArtifactRecord | None:
        normalized = normalize_path(path)
        for record in self.records:
            if record.normalized_path == normalized:
                return record
        return None

    def classify_path(self, path: str | Path, repo_state: dict[str, Any] | None = None) -> ArtifactRecord:
        return classify_path(path, Path.cwd(), repo_state or {})

    def to_dict(self) -> dict[str, Any]:
        return {"schema_name": "artifact_registry.v1", "records": [asdict(record) for record in self.records]}


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _kind(path: str, is_dir: bool = False) -> str:
    if is_dir:
        return "FIXTURE" if "fixtures" in path else "DOC"
    suffix = Path(path).suffix.lower()
    if suffix == ".py":
        return "SOURCE_CODE" if path.startswith(("src/", "scripts/")) else "TEST_CODE" if path.startswith("tests/") else "SOURCE_CODE"
    if suffix == ".json":
        return "JSON_LEDGER"
    if suffix == ".md":
        return "DOC"
    if suffix == ".pptx":
        return "PPTX"
    if suffix == ".png":
        return "REFERENCE_IMAGE" if "reference_image" in path else "RENDER"
    if path in {"package.json", "pyproject.toml"}:
        return "CONFIG"
    return "UNKNOWN"


def _evidence_for_family(family: str) -> tuple[str, str, list[str], list[str]]:
    if family == "PROTECTED_CANONICAL":
        return "HISTORICAL_REFERENCE", "protected_canonical_not_new_product_evidence", [], ["CLAIM_CANONICAL_PROMOTION"]
    if family == "R01_FAILURE_ANALYSIS_CONTEXT":
        return "GOVERNANCE_EVIDENCE", "failure_analysis_context", ["CLAIM_ROUTE_PROOF"], ["CLAIM_PRODUCT_SUCCESS"]
    if family == "E01_FAIL_FIXTURE":
        return "DIAGNOSTIC_PROOF", "known_fail_fixture", ["CLAIM_SEMANTIC_EDITABILITY"], ["CLAIM_PRODUCT_SUCCESS"]
    if family == "E01B_PASS_FIXTURE":
        return "REGRESSION_FIXTURE", "bounded_regression_fixture", ["CLAIM_MAGIC_LAYER_PLUS"], ["CLAIM_TEMPLATE_PACK_READINESS", "CLAIM_SCALEOUT_READINESS"]
    if family == "E02_4CORE_PASS_FIXTURE":
        return "REGRESSION_FIXTURE", "bounded_regression_fixture", ["CLAIM_TEMPLATE_USABILITY", "CLAIM_SEMANTIC_EDITABILITY"], ["CLAIM_SOURCE_BOUND_READINESS", "CLAIM_SCALEOUT_READINESS"]
    if family == "CANVA_BENCHMARK_FIXTURE":
        return "BENCHMARK_EVIDENCE", "comparison_benchmark_only", ["CLAIM_CANVA_PARITY"], ["CLAIM_PRODUCT_SUCCESS"]
    if family.startswith("MANUAL_REVIEW"):
        return "MANUAL_REVIEW_NOT_EVIDENCE", "manual_review_debt", [], ["ALL_PRODUCT_CLAIMS"]
    if family.endswith("_QUARANTINED"):
        return "QUARANTINED_NOT_ACTIVE", "quarantined_not_active", [], ["ALL_PRODUCT_CLAIMS"]
    if family == "ACTIVE_CORE":
        return "GOVERNANCE_EVIDENCE", "implementation_surface", [], []
    return "UNKNOWN_NOT_EVIDENCE", "not_product_evidence", [], ["CLAIM_PRODUCT_SUCCESS"]


def classify_path(path: str | Path, root: Path, repo_state: dict[str, Any]) -> ArtifactRecord:
    normalized = normalize_path(path)
    full = Path(normalized)
    if not full.is_absolute():
        full = root / normalized
    exists = full.exists()
    family = classify_artifact_family(normalized, repo_state)
    evidence_class, product_relevance, supported, blocked = _evidence_for_family(family)
    quarantine = "quarantined" if is_quarantined_path(normalized, repo_state) or family.endswith("_QUARANTINED") else "not_quarantined"
    manual = "PENDING_MANUAL_REVIEW" if is_manual_review_path(normalized, repo_state) or family.startswith("MANUAL_REVIEW") else "not_manual_review"
    protected = "protected_canonical" if is_protected_artifact(normalized) else "not_protected"
    return ArtifactRecord(
        artifact_id=normalized.replace("/", "__").replace(":", ""),
        path=normalized,
        normalized_path=normalized,
        exists=exists,
        kind="PROTECTED_CANONICAL" if normalized in PROTECTED_ARTIFACTS else _kind(normalized, full.is_dir()),
        family=family,
        role="fixture" if "FIXTURE" in family else "protected" if protected != "not_protected" else "implementation_or_report",
        evidence_class=evidence_class,
        product_relevance=product_relevance,
        stage_id=_stage_from_path(normalized),
        run_id="run_003" if "run_003" in normalized else None,
        source_stage=_stage_from_path(normalized),
        active_status="excluded" if quarantine == "quarantined" else "active",
        protected_status=protected,
        quarantine_status=quarantine,
        manual_review_status=manual,
        sha256=_sha256(full),
        size_bytes=full.stat().st_size if full.is_file() else None,
        claims_supported=supported,
        claims_blocked=blocked,
        notes="A01 registry classification; product evidence requires explicit active registration.",
    )


def _stage_from_path(path: str) -> str | None:
    for token in ("e01b", "e01", "e02", "e03", "e04", "d07", "d08", "c11"):
        if token in path.lower():
            return token.upper()
    return None


def load_repo_state(root: Path) -> dict[str, Any]:
    state: dict[str, Any] = {"manual_review_paths": [], "quarantine_folder": ""}
    state_dir = root / "repo_state"
    for name in [
        "current_objective",
        "active_workspace_policy",
        "artifact_family_registry",
        "artifact_claim_policy",
        "product_evidence_policy",
        "scaleout_lock_policy",
        "manual_review_registry",
        "quarantine_registry",
    ]:
        path = state_dir / f"{name}.json"
        if path.is_file():
            state[name] = json.loads(path.read_text(encoding="utf-8"))
    manual = state.get("manual_review_registry", {}).get("items", [])
    state["manual_review_paths"] = [item.get("path") for item in manual if item.get("path")]
    quarantine = state.get("quarantine_registry", {}).get("quarantine_folder_path")
    if quarantine:
        state["quarantine_folder"] = quarantine
    return state


def scan_active_workspace(root: Path, policy: dict[str, Any] | None = None) -> ArtifactRegistry:
    repo_state = policy or load_repo_state(root)
    registry = ArtifactRegistry()
    for protected in sorted(PROTECTED_ARTIFACTS):
        registry.add(classify_path(protected, root, repo_state))
    for file_name in ACTIVE_SCAN_FILES:
        if (root / file_name).exists():
            registry.add(classify_path(file_name, root, repo_state))
    for root_name in ACTIVE_SCAN_ROOTS:
        scan_root = root / root_name
        if not scan_root.exists():
            continue
        for item in scan_root.rglob("*"):
            if item.is_dir() or "__pycache__" in item.parts or ".git" in item.parts or "node_modules" in item.parts:
                continue
            normalized = normalize_path(item.relative_to(root))
            if is_quarantined_path(normalized, repo_state):
                continue
            registry.add(classify_path(normalized, root, repo_state))
    for manual_path in repo_state.get("manual_review_paths", []):
        registry.add(classify_path(manual_path, root, repo_state))
    return registry


def write_registry(registry: ArtifactRegistry, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_registry(path: Path) -> ArtifactRegistry:
    data = json.loads(path.read_text(encoding="utf-8"))
    return ArtifactRegistry(ArtifactRecord(**record) for record in data.get("records", []))


def summarize_registry(registry: ArtifactRegistry) -> dict[str, Any]:
    def count_if(field: str, value: str) -> int:
        return sum(1 for record in registry.records if getattr(record, field) == value)

    return {
        "total_records": len(registry.records),
        "product_evidence_count": count_if("evidence_class", "PRODUCT_EVIDENCE"),
        "route_proof_count": count_if("evidence_class", "ROUTE_PROOF"),
        "audit_evidence_count": count_if("evidence_class", "AUDIT_EVIDENCE"),
        "governance_evidence_count": count_if("evidence_class", "GOVERNANCE_EVIDENCE"),
        "manual_review_count": count_if("evidence_class", "MANUAL_REVIEW_NOT_EVIDENCE"),
        "quarantined_count": count_if("evidence_class", "QUARANTINED_NOT_ACTIVE"),
        "unknown_not_evidence_count": count_if("evidence_class", "UNKNOWN_NOT_EVIDENCE"),
        "protected_count": count_if("protected_status", "protected_canonical"),
        "fixture_count": sum(1 for record in registry.records if "FIXTURE" in record.family),
    }
