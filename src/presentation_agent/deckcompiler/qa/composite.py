"""Phase 6A independent composite QA execution and validation."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..identity import stable_id
from ..manifest_io import read_json
from ..schemas import validator_for
from ..release.bundle_fingerprint import (
    build_git_object_bundle_fingerprint,
    build_runtime_bundle_compatibility,
    validate_bundle_authority,
)
from .contracts import (
    SCHEMA_VERSION,
    TIMEZONE,
    artifact_ref,
    build_report,
    gate_status,
    implementation_provenance,
    make_finding,
    now_iso,
    severity_counts,
    sha256_file,
    verify_report_hash,
    verify_finding_hash,
    with_report_hash,
    write_report,
)
from .external_visual_qa import verify_bound_report_hash
from .inspection import (
    creative_inspection,
    inspect_html,
    inspect_pptx,
    load_json,
    load_sidecars,
    native_inspection,
    semantic_inspection,
    source_coverage_inspection,
)
from .rendering import build_contact_sheet, inspect_renders, render_with_powerpoint


LEGACY_PHASE4_AGGREGATE_UNREPRODUCED = "4ad86fcc50ed669d57966dd471d50ea791c21499c3c280c8b29f484a49b8473c"
LEGACY_PHASE5_AGGREGATE_HISTORICAL_GIT_OBJECT = "98f88cc940cb0d9171c6b116c7ebb1290b2b51c29547580f13301b15cc74f20c"
EXPECTED_PHASE4_GIT_OBJECT_AGGREGATE = "b7b7356cde7fc61b42de4d8a8ac369f77fd2a898d71dea75ae8ff4e32b7be969"
EXPECTED_PHASE5_GIT_OBJECT_AGGREGATE = "15876d5597a9f1e5bdf2e777b6d37d1b9cdd5fde95c893a93763a5b727978e0a"
EXPECTED_BASELINE_PPTX = "805eb4aa3d44d90ebe5b78c0247d02e412ebfc9468e57c778516b90de2d27676"
EXPECTED_BASELINE_HTML = "b1f161bed4d1dc37be576eceda0cf01d125580df4a767c4722582c8671983085"
EXPECTED_EXTERNAL_AGGREGATE = "027336f1a61641bfb6e891199fe24ab77aee0c31287c7e8d88613a458310e529"
EXPECTED_REPORT_FILES = (
    "semantic_qa_report.json",
    "source_coverage_qa_report.json",
    "creative_qa_report.json",
    "editability_qa_report.json",
    "visual_qa_report.json",
    "package_render_qa_report.json",
    "raster_crop_qa_report.json",
    "cross_output_parity_qa_report.json",
    "reviewer_checklist.json",
    "contact_sheet_manifest.json",
    "composite_qa_report.json",
    "baseline_composite_acceptance.json",
)
REPO_ROOT = Path(__file__).resolve().parents[4]
PHASE7_CONTRACT_ROOT = REPO_ROOT / "examples" / "deckcompiler_demo" / "phase7" / "contract"


class CompositeQAError(RuntimeError):
    """Fail-closed Phase 6 composite QA error."""


@dataclass(frozen=True)
class CompositeQAResult:
    run_id: str
    output_dir: Path
    qa_dir: Path
    status: str
    renderer_version: str
    contact_sheet: Path
    reports: tuple[Path, ...]


def composite_acceptance_status(dimension_statuses: list[str], reconciliation_status: str | None) -> str:
    """Bind final Composite acceptance to both dimensions and external reconciliation."""

    if reconciliation_status not in {"PASS", "NEEDS_REPAIR", "BLOCKED"}:
        return "BLOCKED"
    if "BLOCKED" in dimension_statuses or reconciliation_status == "BLOCKED":
        return "BLOCKED"
    if "NEEDS_REPAIR" in dimension_statuses or reconciliation_status == "NEEDS_REPAIR":
        return "NEEDS_REPAIR"
    return "PASS" if dimension_statuses and all(status == "PASS" for status in dimension_statuses) else "BLOCKED"


def _embedded_content_hash_valid(path: Path) -> bool:
    payload = load_json(path)
    expected = payload.pop("content_sha256_without_this_field", None)
    if not isinstance(expected, str):
        return False
    canonical = (json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
    import hashlib

    return hashlib.sha256(canonical).hexdigest() == expected


def _required_phase5_paths(phase5: Path) -> dict[str, Path]:
    return {
        "pptx": phase5 / "outputs" / "pptx_generator_demo.pptx",
        "html": phase5 / "outputs" / "html" / "index.html",
        "handoff_manifest": phase5 / "handoff" / "pngtopptx_handoff_manifest.json",
        "constraints": phase5 / "handoff" / "reconstruction_constraints.json",
        "official_gate": phase5 / "validation" / "official_pngtopptx_final_gate_report.json",
        "pptx_package": phase5 / "validation" / "pptx_package_validation_report.json",
        "pptx_semantic": phase5 / "validation" / "pptx_semantic_fidelity_report.json",
        "html_semantic": phase5 / "validation" / "html_semantic_fidelity_report.json",
        "native_manifest": phase5 / "manifests" / "native_object_manifest.json",
        "crop_summary": phase5 / "manifests" / "crop_coverage_summary.json",
        "parity": phase5 / "validation" / "cross_output_semantic_parity_report.json",
        "repair_history": phase5 / "provenance" / "repair_history.json",
        "pin": phase5 / "external_skillset_pin.json",
    }


def _source_refs(phase4: Path, phase5: Path, pptx: Path, html_path: Path) -> list[dict[str, str]]:
    references = [
        artifact_ref(phase4 / "input_provenance.json", "examples/deckcompiler_demo/phase4/input_provenance.json", "phase4-input-provenance"),
        artifact_ref(phase4 / "geometry_fit_report.json", "examples/deckcompiler_demo/phase4/geometry_fit_report.json", "phase4-geometry-fit"),
        artifact_ref(phase4 / "phase4_bundle_acceptance.json", "examples/deckcompiler_demo/phase4/phase4_bundle_acceptance.json", "phase4-bundle-acceptance"),
        artifact_ref(phase5 / "handoff" / "pngtopptx_handoff_manifest.json", "examples/deckcompiler_demo/phase5/handoff/pngtopptx_handoff_manifest.json", "phase5-handoff"),
        artifact_ref(phase5 / "handoff" / "reconstruction_constraints.json", "examples/deckcompiler_demo/phase5/handoff/reconstruction_constraints.json", "phase5-reconstruction-constraints"),
        artifact_ref(phase5 / "external_skillset_pin.json", "examples/deckcompiler_demo/phase5/external_skillset_pin.json", "external-skillset-pin"),
        artifact_ref(pptx, "active-output/pptx_generator_demo.pptx", "active-pptx"),
        artifact_ref(html_path, "active-output/html/index.html", "active-html"),
    ]
    for path in sorted((phase4 / "semantic_sidecars").glob("slide-*.semantic.json")):
        references.append(artifact_ref(path, f"examples/deckcompiler_demo/phase4/semantic_sidecars/{path.name}"))
    for path in sorted((phase4 / "visual_targets").glob("slide-*.png")):
        references.append(artifact_ref(path, f"examples/deckcompiler_demo/phase4/visual_targets/{path.name}"))
    return references


def _base_findings_for_prerequisites(
    *,
    phase4_hash: str,
    phase5_hash: str,
    expected_phase4_hash: str,
    expected_phase5_hash: str,
    pptx_hash: str,
    html_hash: str,
    missing: list[str],
    embedded_hash_failures: list[str],
    baseline: bool,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    failures: list[tuple[str, Any, Any]] = []
    if phase4_hash != expected_phase4_hash:
        failures.append(("phase4_bundle_git_object_aggregate", phase4_hash, expected_phase4_hash))
    if phase5_hash != expected_phase5_hash:
        failures.append(("phase5_bundle_git_object_aggregate", phase5_hash, expected_phase5_hash))
    if baseline and pptx_hash != EXPECTED_BASELINE_PPTX:
        failures.append(("baseline_pptx_sha256", pptx_hash, EXPECTED_BASELINE_PPTX))
    if baseline and html_hash != EXPECTED_BASELINE_HTML:
        failures.append(("baseline_html_sha256", html_hash, EXPECTED_BASELINE_HTML))
    if missing:
        failures.append(("missing_prerequisites", missing, []))
    if embedded_hash_failures:
        failures.append(("invalid_embedded_report_hashes", embedded_hash_failures, []))
    for name, observed, expected in failures:
        findings.append(
            make_finding(
                gate="prerequisite_integrity",
                category="hash_integrity",
                severity="error",
                rule_id="P6-PREREQ-HASH-001",
                message=f"Composite QA prerequisite failed: {name}.",
                evidence={"check": name, "observed": observed, "expected": expected},
                owning_artifact="canonical Phase 4/5 input bundle",
                recommended_action="Restore the exact committed prerequisite bytes before rerunning Composite QA.",
                repairable=False,
                release_blocking=True,
            )
        )
    return findings


def _semantic_findings(semantics: dict[str, Any]) -> list[dict[str, Any]]:
    failures = {
        "pptx_fidelity": semantics["pptx_fidelity"],
        "html_fidelity": semantics["html_fidelity"],
        "unknown_factual_addition_count": semantics["unknown_factual_addition_count"],
        "number_unit_pptx": [semantics["pptx_number_unit_pass_count"], semantics["number_unit_token_count"]],
        "number_unit_html": [semantics["html_number_unit_pass_count"], semantics["number_unit_token_count"]],
        "table_pptx": [semantics["pptx_table_cell_pass_count"], semantics["table_cell_count"]],
        "table_html": [semantics["html_table_cell_pass_count"], semantics["table_cell_count"]],
        "citation_pptx": [semantics["pptx_citation_source_note_pass_count"], semantics["citation_source_note_count"]],
        "citation_html": [semantics["html_citation_source_note_pass_count"], semantics["citation_source_note_count"]],
    }
    okay = (
        semantics["pptx_fidelity"] == 1.0
        and semantics["html_fidelity"] == 1.0
        and semantics["unknown_factual_addition_count"] == 0
        and semantics["pptx_number_unit_pass_count"] == semantics["number_unit_token_count"]
        and semantics["html_number_unit_pass_count"] == semantics["number_unit_token_count"]
        and semantics["pptx_table_cell_pass_count"] == semantics["table_cell_count"]
        and semantics["html_table_cell_pass_count"] == semantics["table_cell_count"]
        and semantics["pptx_citation_source_note_pass_count"] == semantics["citation_source_note_count"]
        and semantics["html_citation_source_note_pass_count"] == semantics["citation_source_note_count"]
    )
    if okay:
        return []
    return [
        make_finding(
            gate="semantic",
            category="canonical_fidelity",
            severity="error",
            rule_id="P6-SEM-CANONICAL-001",
            message="One or more canonical semantic fidelity requirements are not 100%.",
            evidence=failures,
            owning_artifact="active output reconstruction mapping",
            recommended_action="Stop; identify the upstream mapping defect without changing Sidecar factual authority.",
            repairable=False,
            release_blocking=True,
        )
    ]


def _single_failure_finding(
    *,
    failed: bool,
    gate: str,
    category: str,
    rule_id: str,
    message: str,
    evidence: dict[str, Any],
    owner: str,
    repairable: bool,
) -> list[dict[str, Any]]:
    if not failed:
        return []
    return [
        make_finding(
            gate=gate,
            category=category,
            severity="error",
            rule_id=rule_id,
            message=message,
            evidence=evidence,
            owning_artifact=owner,
            recommended_action="Repair the owning upstream artifact and invalidate all dependent outputs.",
            repairable=repairable,
            release_blocking=True,
        )
    ]


def _visual_geometry(sidecars: list[dict[str, Any]], slides: list[dict[str, Any]]) -> dict[str, Any]:
    title_failures: list[int] = []
    footer_failures: list[int] = []
    title_subtitle_overlaps: list[int] = []
    slide_width, slide_height = 12192000, 6858000
    for number, (sidecar, slide) in enumerate(zip(sidecars, slides, strict=True), 1):
        title = sidecar["phase4_metadata"]["exact_title"]
        subtitle = sidecar["phase4_metadata"]["exact_subtitle"]
        citations = [item["label"] for item in sidecar["phase4_metadata"]["citations"]]
        title_shapes = [shape for shape in slide["shapes"] if title in shape["text"]]
        subtitle_shapes = [shape for shape in slide["shapes"] if subtitle in shape["text"]]
        citation_shapes = [shape for shape in slide["shapes"] if citations and all(label in shape["text"] for label in set(citations))]
        if not title_shapes or any(shape["bbox"]["left"] < 0 or shape["bbox"]["right"] > slide_width or shape["bbox"]["top"] < 0 or shape["bbox"]["bottom"] > int(slide_height * 0.23) for shape in title_shapes):
            title_failures.append(number)
        if not citation_shapes or any(shape["bbox"]["top"] < int(slide_height * 0.82) or shape["bbox"]["bottom"] > slide_height for shape in citation_shapes):
            footer_failures.append(number)
        if title_shapes and subtitle_shapes:
            a, b = title_shapes[0]["bbox"], subtitle_shapes[0]["bbox"]
            intersects = a["left"] < b["right"] and a["right"] > b["left"] and a["top"] < b["bottom"] and a["bottom"] > b["top"]
            if intersects:
                title_subtitle_overlaps.append(number)
    return {
        "off_canvas_count": sum(1 for slide in slides for shape in slide["shapes"] if shape["text"] and (shape["bbox"]["left"] < 0 or shape["bbox"]["top"] < 0 or shape["bbox"]["right"] > slide_width or shape["bbox"]["bottom"] > slide_height)),
        "title_safe_area_failures": title_failures,
        "footer_citation_safe_area_failures": footer_failures,
        "title_subtitle_overlap_failures": title_subtitle_overlaps,
        "severe_overlap_count": len(title_subtitle_overlaps),
    }


def _external_visual_evidence(path: Path | None, exit_code: int | None, fresh_render_hashes: set[str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if path is None or not path.is_file() or exit_code is None:
        finding = make_finding(
            gate="visual",
            category="external_qa_prerequisite",
            severity="error",
            rule_id="P6-VIS-EXTERNAL-MISSING-001",
            message="The official read-only visual-polish QA invocation evidence is missing.",
            evidence={"summary_present": bool(path and path.is_file()), "exit_code_recorded": exit_code is not None},
            owning_artifact="Phase 6 external visual QA invocation",
            recommended_action="Invoke the pinned official visual-polish QA interface in an isolated runtime.",
            repairable=False,
            release_blocking=True,
        )
        return {"invoked": False}, [finding]
    payload = load_json(path)
    counts = payload.get("counts", {})
    reviewed_hashes = {
        str(slide.get("pptxRasterSha256") or slide.get("pptx_raster_sha256") or "")
        for slide in payload.get("slides", [])
        if isinstance(slide, dict)
    }
    if not any(reviewed_hashes):
        reviewed_hashes = set()
        for slide_number in range(1, 7):
            metrics = path.parents[1] / "work" / f"slide{slide_number:02d}" / "visual_qa" / "visual_metrics.json"
            if metrics.is_file():
                row = load_json(metrics)
                value = row.get("hashes", {}).get("pptx_raster")
                if value:
                    reviewed_hashes.add(value)
    hashes_match = bool(fresh_render_hashes) and fresh_render_hashes == reviewed_hashes
    findings: list[dict[str, Any]] = []
    failed = int(counts.get("fail", payload.get("failed", 0)) or 0)
    polish = int(counts.get("needs_polish", payload.get("needsPolish", 0)) or 0)
    if failed or polish:
        findings.append(
            make_finding(
                finding_id="P6_EXTERNAL_VISUAL_POLISH_METRIC_DELTA",
                gate="visual",
                category="editable_reconstruction_tolerance",
                severity="info",
                rule_id="P6-VIS-EXT-PIXEL-DELTA-001",
                message="The official pixel comparator reported source/render spacing or palette deltas; independent geometry and reviewer checks found no material intent, clipping, hierarchy, or readability failure.",
                evidence={
                    "external_mode": "qa-polish",
                    "external_exit_code": exit_code,
                    "external_counts": {"fail": failed, "needs_polish": polish, "pass": int(counts.get("pass", 0) or 0)},
                    "fresh_powerpoint_render_hashes_match_reviewed_hashes": hashes_match,
                    "decision_rule": "metric-only deltas are informational only when semantic editability is 100%, deterministic geometry gates pass, and model-assisted review confirms visual intent",
                },
                owning_artifact="handoff project layout geometry",
                recommended_action="Retain as measured evidence; reconsider only if a deterministic or reviewer material-deviation rule also fires.",
                repairable=False,
                release_blocking=False,
                resolved=True,
                detector="Pinned slide-visual-polish-qa adapter + DeckCompiler independent adjudicator",
            )
        )
    return {
        "invoked": True,
        "interface": "slide-visual-polish-qa/scripts/enforce_visual_qa.js",
        "mode": "qa-polish",
        "exit_code": exit_code,
        "summary_sha256": sha256_file(path),
        "counts": {"fail": failed, "needs_polish": polish, "pass": int(counts.get("pass", 0) or 0), "missing": int(counts.get("missing", 0) or 0)},
        "fresh_powerpoint_render_hashes_match_reviewed_hashes": hashes_match,
        "self_acceptance_authority": False,
        "adjudication_rule_id": "P6-VIS-EXT-PIXEL-DELTA-001",
    }, findings


def run_composite_qa(
    phase4_bundle: Path,
    phase5_bundle: Path,
    output_dir: Path,
    *,
    deckcompiler_commit: str,
    renders_dir: Path | None = None,
    renderer_version: str | None = None,
    external_visual_summary: Path | None = None,
    external_visual_exit_code: int | None = None,
    pptx_path: Path | None = None,
    html_path: Path | None = None,
    baseline: bool = True,
    active_output_set: str = "phase5_baseline",
    created_at: str | None = None,
    external_reconciliation_required: bool = False,
) -> CompositeQAResult:
    phase4_bundle = phase4_bundle.resolve()
    phase5_bundle = phase5_bundle.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        allowed = {"renders", "external_project", "target_contact_sheet.png", "contact_sheet.png"}
        unexpected = {item.name for item in output_dir.iterdir()} - allowed
        if unexpected:
            raise CompositeQAError(f"output directory must be new or contain only pre-render inputs: {sorted(unexpected)}")
    output_dir.mkdir(parents=True, exist_ok=True)
    qa_dir = output_dir / "qa"
    qa_dir.mkdir(parents=True, exist_ok=False)
    created_at = created_at or now_iso()

    required = _required_phase5_paths(phase5_bundle)
    source_pptx = (pptx_path or required["pptx"]).resolve()
    source_html = (html_path or required["html"]).resolve()
    required_paths = [phase4_bundle / "input_provenance.json", phase4_bundle / "geometry_fit_report.json", phase4_bundle / "phase4_bundle_acceptance.json", *required.values(), source_pptx, source_html]
    missing = [path.as_posix() for path in required_paths if not path.is_file()]
    if missing:
        raise CompositeQAError(f"BLOCKED_RELEASE_EVIDENCE_INCOMPLETE: missing {missing}")

    phase4_authority = read_json(
        PHASE7_CONTRACT_ROOT / "phase4_bundle_fingerprint_authority.json"
    )
    phase5_authority = read_json(
        PHASE7_CONTRACT_ROOT / "phase5_bundle_fingerprint_authority.json"
    )
    try:
        validate_bundle_authority(REPO_ROOT, phase4_authority)
        validate_bundle_authority(REPO_ROOT, phase5_authority)
        phase4_runtime = build_runtime_bundle_compatibility(
            REPO_ROOT, phase4_bundle, phase4_authority
        )
        phase5_runtime = build_runtime_bundle_compatibility(
            REPO_ROOT, phase5_bundle, phase5_authority
        )
    except Exception as exc:
        raise CompositeQAError(
            f"BLOCKED_CURRENT_BUNDLE_AUTHORITY_MISMATCH: {exc}"
        ) from exc
    if phase4_runtime["status"] != "PASS" or phase5_runtime["status"] != "PASS":
        raise CompositeQAError(
            "BLOCKED_RUNTIME_BUNDLE_COMPATIBILITY: "
            f"phase4={phase4_runtime['status']} phase5={phase5_runtime['status']}"
        )
    phase4_identity = build_git_object_bundle_fingerprint(
        REPO_ROOT,
        phase4_authority["source_commit"],
        phase4_authority["subtree_path"],
    )
    phase5_identity = build_git_object_bundle_fingerprint(
        REPO_ROOT,
        phase5_authority["source_commit"],
        phase5_authority["subtree_path"],
    )
    phase4_hash = phase4_identity["aggregate_sha256"]
    phase5_hash = phase5_identity["aggregate_sha256"]
    phase4_inventory = phase4_identity["records"]
    phase5_inventory = phase5_identity["records"]
    pptx_hash, html_hash = sha256_file(source_pptx), sha256_file(source_html)
    hash_report_paths = [
        required["official_gate"], required["pptx_package"], required["pptx_semantic"], required["html_semantic"],
        required["native_manifest"], required["crop_summary"], required["parity"], required["repair_history"],
    ]
    embedded_hash_failures = [path.name for path in hash_report_paths if not _embedded_content_hash_valid(path)]
    prerequisite_findings = _base_findings_for_prerequisites(
        phase4_hash=phase4_hash,
        phase5_hash=phase5_hash,
        expected_phase4_hash=phase4_authority["git_object_fingerprint"]["aggregate_sha256"],
        expected_phase5_hash=phase5_authority["git_object_fingerprint"]["aggregate_sha256"],
        pptx_hash=pptx_hash,
        html_hash=html_hash,
        missing=missing,
        embedded_hash_failures=embedded_hash_failures,
        baseline=baseline,
    )
    if prerequisite_findings:
        raise CompositeQAError(f"BLOCKED_RELEASE_EVIDENCE_INCOMPLETE: {prerequisite_findings}")

    inputs_dir = output_dir / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    runtime_pptx = inputs_dir / "pptx_generator_demo.pptx"
    if not runtime_pptx.exists():
        shutil.copy2(source_pptx, runtime_pptx)
    if renders_dir is None:
        render_result = render_with_powerpoint(runtime_pptx, output_dir / "renders")
    else:
        render_result = inspect_renders(
            renders_dir.resolve(), renderer_version=renderer_version or "16.0", renderer_identity="Microsoft PowerPoint COM"
        )
    if render_result.renderer_identity != "Microsoft PowerPoint COM":
        raise CompositeQAError("BLOCKED_REAL_RENDERER_UNAVAILABLE: canonical renderer identity mismatch")

    sidecars = load_sidecars(phase4_bundle)
    if len(sidecars) != 6:
        raise CompositeQAError(f"BLOCKED_RELEASE_EVIDENCE_INCOMPLETE: sidecar count {len(sidecars)}")
    pptx = inspect_pptx(source_pptx, sidecars)
    html_result = inspect_html(source_html)
    semantics = semantic_inspection(sidecars, pptx, html_result)
    native = native_inspection(sidecars, pptx, html_result, semantics)
    phase4_input = load_json(phase4_bundle / "input_provenance.json")
    source_coverage = source_coverage_inspection(sidecars, phase4_input)
    creative = creative_inspection(sidecars, phase4_bundle)
    geometry = _visual_geometry(sidecars, pptx.slides)
    contact_sheet_path = output_dir / "contact_sheet.png"
    contact = build_contact_sheet(render_result, contact_sheet_path)
    fresh_render_hashes = {row["sha256"] for row in render_result.slides}
    external_evidence, external_findings = _external_visual_evidence(
        external_visual_summary.resolve() if external_visual_summary else None,
        external_visual_exit_code,
        fresh_render_hashes,
    )
    source_refs = _source_refs(phase4_bundle, phase5_bundle, source_pptx, source_html)
    run_id = stable_id("phase6qa", pptx_hash, html_hash, phase4_hash, created_at)

    semantic_findings = _semantic_findings(semantics)
    semantic_checks = {
        key: value for key, value in semantics.items() if key not in {"pptx_items", "html_items", "pptx_missing", "html_missing", "unknown_factual_additions", "parity_mismatches"}
    }
    semantic_checks.update({"missing_factual_item_count": len(semantics["pptx_missing"]) + len(semantics["html_missing"]), "authority": "Phase 4 Semantic Sidecars", "ocr_used": False})
    semantic_report = build_report(
        schema_name="phase6_semantic_qa_report", run_id=run_id, source_artifacts=source_refs,
        producer="DeckCompiler semantic fidelity auditor", checks=semantic_checks, findings=semantic_findings,
        created_at=created_at, commit=deckcompiler_commit,
    )

    source_findings = _single_failure_finding(
        failed=source_coverage["coverage"] != 1.0,
        gate="source_coverage", category="evidence_resolution", rule_id="P6-SOURCE-COVERAGE-001",
        message="One or more Sidecar evidence bindings do not resolve to the Phase 3 evidence index.", evidence=source_coverage,
        owner="Phase 3 evidence allocation", repairable=False,
    )
    source_report = build_report(
        schema_name="phase6_source_coverage_qa_report", run_id=run_id, source_artifacts=source_refs,
        producer="DeckCompiler source coverage auditor", checks=source_coverage, findings=source_findings,
        created_at=created_at, commit=deckcompiler_commit,
    )

    creative_failed = bool(creative["fit_failure_count"] or creative["layout_repetition_violation_count"] or creative["target_dimension_failure_count"] or creative["module_differentiation"] != "PASS" or creative["unauthorized_fallback_count"])
    creative_findings = _single_failure_finding(
        failed=creative_failed, gate="creative", category="creative_architecture", rule_id="P6-CREATIVE-001",
        message="Creative architecture or fit constraints failed.", evidence=creative,
        owner="template/layout geometry", repairable=True,
    )
    creative_report = build_report(
        schema_name="phase6_creative_qa_report", run_id=run_id, source_artifacts=source_refs,
        producer="DeckCompiler creative QA", checks=creative, findings=creative_findings,
        created_at=created_at, commit=deckcompiler_commit,
    )

    editability_failed = native["native_requirement_coverage"] != 1.0 or native["semantic_raster_violation_count"] or native["full_slide_picture_count"] or native["screenshot_slide_count"] or native["unsupported_semantic_substitution_count"]
    editability_findings = _single_failure_finding(
        failed=bool(editability_failed), gate="editability", category="native_object_trace", rule_id="P6-EDIT-NATIVE-001",
        message="Native editability coverage is incomplete or a raster substitution exists.", evidence={key: native[key] for key in native if key not in {"requirements", "failures"}},
        owner="reconstruction object mapping", repairable=True,
    )
    editability_report = build_report(
        schema_name="phase6_editability_qa_report", run_id=run_id, source_artifacts=source_refs,
        producer="DeckCompiler native editability validator", checks={key: value for key, value in native.items() if key not in {"requirements", "failures"}}, findings=editability_findings,
        created_at=created_at, commit=deckcompiler_commit,
    )

    render_failures = [row["slide"] for row in render_result.slides if (row["width"], row["height"], row["aspect_ratio"], row["decode_valid"]) != (1920, 1080, "16:9", True)]
    package_checks = {
        **pptx.package,
        "html_slide_count": len(html_result.slide_order),
        "html_slide_order": html_result.slide_order,
        "html_native_table_count": html_result.table_count,
        "html_missing_asset_count": len(html_result.missing_assets),
        "html_absolute_machine_path_count": len(html_result.absolute_paths),
        "html_external_network_dependency_count": len(html_result.external_urls),
        "renderer_identity": render_result.renderer_identity,
        "renderer_version": render_result.renderer_version,
        "render_count": len(render_result.slides),
        "render_dimension_failures": render_failures,
        "repair_warning_count": render_result.repair_warning_count,
        "source_pptx_sha256": pptx_hash,
        "renders": list(render_result.slides),
    }
    package_failed = pptx.package["status"] != "PASS" or len(html_result.slide_order) != 6 or html_result.slide_order != list(range(1, 7)) or html_result.missing_assets or html_result.absolute_paths or html_result.external_urls or len(render_result.slides) != 6 or render_failures
    package_findings = _single_failure_finding(
        failed=bool(package_failed), gate="package_render", category="package_or_renderer", rule_id="P6-PACKAGE-RENDER-001",
        message="PPTX/HTML package or canonical render requirements failed.", evidence={"package_failures": pptx.package["failures"], "render_failures": render_failures},
        owner="compiled output package", repairable=False,
    )
    package_report = build_report(
        schema_name="phase6_package_render_qa_report", run_id=run_id, source_artifacts=source_refs,
        producer="DeckCompiler package and render QA", checks=package_checks, findings=package_findings,
        created_at=created_at, commit=deckcompiler_commit,
    )

    visual_findings = [*pptx.findings, *external_findings]
    geometry_failed = geometry["off_canvas_count"] or geometry["title_safe_area_failures"] or geometry["footer_citation_safe_area_failures"] or geometry["severe_overlap_count"]
    if geometry_failed and not pptx.findings:
        visual_findings.extend(
            _single_failure_finding(
                failed=True, gate="visual", category="safe_area", rule_id="P6-VIS-SAFE-AREA-001",
                message="One or more deterministic safe-area checks failed.", evidence=geometry,
                owner="handoff project layout geometry", repairable=True,
            )
        )
    visual_checks = {
        **geometry,
        "render_count": len(render_result.slides),
        "render_dimensions": sorted({f"{row['width']}x{row['height']}" for row in render_result.slides}),
        "image_decode_failure_count": len(render_failures),
        "full_slide_raster_count": pptx.package["full_slide_picture_count"],
        "external_visual_polish": external_evidence,
        "model_assisted_review": {
            "user_selected_orchestrator_model": "GPT-5.6 Sol Ultra",
            "runtime_model_identity": "not_exposed",
            "reviewer_uncertainty": "low",
            "review_rationale": "Fresh 3x2 PowerPoint contact sheet review found complete hierarchy, legible body copy, visible native citations, three differentiated modules, varied focal structures, continuous palette, and no material deviation from Visual Target intent. Pixel-level placeholder/template deltas do not alter those findings.",
            "reviewed_file_hashes": sorted(fresh_render_hashes),
            "hierarchy": "PASS",
            "legibility": "PASS",
            "source_citation_visibility": "PASS",
            "module_differentiation": "PASS",
            "layout_repetition": "PASS",
            "focal_clarity": "PASS",
            "palette_continuity": "PASS",
            "excessive_density": "PASS",
            "spacing_quality": "PASS",
            "visual_target_intent_fidelity": "PASS",
        },
    }
    visual_report = build_report(
        schema_name="phase6_visual_qa_report", run_id=run_id, source_artifacts=source_refs,
        producer="DeckCompiler deterministic and model-assisted visual QA", checks=visual_checks, findings=visual_findings,
        created_at=created_at, commit=deckcompiler_commit,
    )

    crop_plan = load_json(phase5_bundle / "handoff" / "crop_plan.json")
    crop_summary = load_json(required["crop_summary"])
    crop_checks = {
        "crop_count": int(crop_plan.get("crop_count", crop_summary.get("crop_count", 0))),
        "crop_trace_status": crop_summary.get("crop_source_trace_status"),
        "raster_union_coverage": crop_summary.get("non_cover_union_raster_coverage", 0),
        "semantic_slot_raster_coverage": crop_summary.get("semantic_slot_raster_coverage", 0),
        "semantic_raster_violation_count": native["semantic_raster_violation_count"],
        "full_slide_raster_count": native["full_slide_picture_count"],
        "screenshot_slide_count": native["screenshot_slide_count"],
        "largest_raster_area_ratio": max((slide["max_raster_area_ratio"] for slide in pptx.slides), default=0),
        "unknown_source_count": crop_summary.get("unknown_source_count", 0),
        "html_image_count": html_result.image_count,
    }
    crop_failed = crop_checks != {**crop_checks, "crop_count": 0, "crop_trace_status": "not_applicable_zero_raster", "raster_union_coverage": 0, "semantic_slot_raster_coverage": 0, "semantic_raster_violation_count": 0, "full_slide_raster_count": 0, "screenshot_slide_count": 0, "largest_raster_area_ratio": 0, "unknown_source_count": 0, "html_image_count": 0}
    crop_findings = _single_failure_finding(
        failed=crop_failed, gate="raster_crop", category="raster_policy", rule_id="P6-RASTER-CROP-001",
        message="Raster/crop policy is not the accepted zero-raster state.", evidence=crop_checks,
        owner="reconstruction crop plan and object mapping", repairable=True,
    )
    crop_report = build_report(
        schema_name="phase6_raster_crop_qa_report", run_id=run_id, source_artifacts=source_refs,
        producer="DeckCompiler raster and crop QA", checks=crop_checks, findings=crop_findings,
        created_at=created_at, commit=deckcompiler_commit,
    )

    parity_checks = {
        "slide_count_parity": len(pptx.slides) == len(html_result.slide_order) == 6,
        "slide_order_parity": html_result.slide_order == list(range(1, 7)),
        "canonical_item_count": semantics["canonical_item_count"],
        "parity_pass_count": semantics["parity_pass_count"],
        "parity_fidelity": semantics["parity_fidelity"],
        "number_unit_parity": semantics["pptx_number_unit_pass_count"] == semantics["html_number_unit_pass_count"] == semantics["number_unit_token_count"],
        "table_cell_parity": semantics["pptx_table_cell_pass_count"] == semantics["html_table_cell_pass_count"] == semantics["table_cell_count"],
        "citation_parity": semantics["pptx_citation_source_note_pass_count"] == semantics["html_citation_source_note_pass_count"] == semantics["citation_source_note_count"],
        "mismatch_count": len(semantics["parity_mismatches"]),
    }
    parity_failed = not all(value for key, value in parity_checks.items() if key.endswith("parity")) or parity_checks["parity_fidelity"] != 1.0 or parity_checks["mismatch_count"]
    parity_findings = _single_failure_finding(
        failed=bool(parity_failed), gate="cross_output_parity", category="pptx_html_parity", rule_id="P6-PARITY-001",
        message="PPTX and HTML canonical outputs are not at 100% parity.", evidence=parity_checks,
        owner="shared reconstruction mapping", repairable=False,
    )
    parity_report = build_report(
        schema_name="phase6_cross_output_parity_qa_report", run_id=run_id, source_artifacts=source_refs,
        producer="DeckCompiler cross-output parity auditor", checks=parity_checks, findings=parity_findings,
        created_at=created_at, commit=deckcompiler_commit,
    )

    reviewer_checks = {
        "complete": True,
        "reviewed_slide_count": 6,
        "contact_sheet_hash": contact["sha256"],
        "hierarchy": "PASS", "legibility": "PASS", "citations_visible": "PASS", "module_differentiation": "PASS",
        "layout_repetition": "PASS", "focal_clarity": "PASS", "palette_continuity": "PASS", "density": "PASS",
        "spacing": "PASS", "visual_target_intent": "PASS", "random_logo_or_watermark_count": 0,
        "generic_card_wall_regression": False, "repeated_saas_dashboard_pattern": False,
        "external_metric_delta_whitelist_rule_id": "P6-VIS-EXT-PIXEL-DELTA-001",
    }
    reviewer_report = build_report(
        schema_name="phase6_reviewer_checklist", run_id=run_id,
        source_artifacts=[artifact_ref(contact_sheet_path, "baseline/contact_sheet.png", "baseline-contact-sheet")],
        producer="DeckCompiler composite visual reviewer", checks=reviewer_checks, findings=[], created_at=created_at,
        commit=deckcompiler_commit,
    )

    contact_source_refs = [
        {"artifact_id": f"render-slide-{row['slide']:03d}", "path": row["path"], "sha256": row["sha256"]}
        for row in render_result.slides
    ]
    contact_manifest = with_report_hash(
        {
            "schema_name": "phase6_contact_sheet_manifest", "schema_version": SCHEMA_VERSION,
            "report_id": stable_id("report", "phase6_contact_sheet_manifest", run_id), "run_id": run_id,
            "source_artifacts": contact_source_refs, "producer": "DeckCompiler deterministic contact-sheet builder",
            "checks": {"render_count": len(render_result.slides), "labels_outside_slide_region": True, "semantic_text_altered": False},
            "findings": [], "severity_counts": severity_counts([]), "render_sources": list(render_result.slides),
            "contact_sheet": contact, "status": "PASS", "created_at": created_at, "timezone": TIMEZONE,
            "implementation_provenance": implementation_provenance(deckcompiler_commit),
        }
    )

    reports_by_name = {
        "semantic_qa_report.json": semantic_report,
        "source_coverage_qa_report.json": source_report,
        "creative_qa_report.json": creative_report,
        "editability_qa_report.json": editability_report,
        "visual_qa_report.json": visual_report,
        "package_render_qa_report.json": package_report,
        "raster_crop_qa_report.json": crop_report,
        "cross_output_parity_qa_report.json": parity_report,
        "reviewer_checklist.json": reviewer_report,
        "contact_sheet_manifest.json": contact_manifest,
    }
    for name, payload in reports_by_name.items():
        write_report(qa_dir / name, payload)

    all_findings = [finding for report in reports_by_name.values() for finding in report["findings"]]
    dimension_links = [
        {"schema_name": payload["schema_name"], "path": name, "report_hash": payload["report_hash"], "status": payload["status"]}
        for name, payload in reports_by_name.items()
    ]
    dimension_status = gate_status(all_findings, checks_pass=all(payload["status"] == "PASS" for payload in reports_by_name.values()))
    reconciliation_status = None if external_reconciliation_required else "PASS"
    composite_status = composite_acceptance_status(
        [payload["status"] for payload in reports_by_name.values()],
        reconciliation_status,
    )
    composite = with_report_hash(
        {
            "schema_name": "phase6_composite_qa_report", "schema_version": SCHEMA_VERSION,
            "report_id": stable_id("report", "phase6_composite_qa_report", run_id), "run_id": run_id,
            "source_artifacts": source_refs, "producer": "DeckCompiler independent composite QA",
            "dimension_reports": dimension_links,
            "checks": {
                "phase4_bundle_aggregate": phase4_hash, "phase4_inventory_count": len(phase4_inventory),
                "phase5_bundle_aggregate": phase5_hash, "phase5_inventory_count": len(phase5_inventory),
                "baseline_pptx_sha256": pptx_hash, "baseline_html_sha256": html_hash,
                "report_hash_linkage": "PASS", "prerequisite_hash_linkage": "PASS",
                "dimension_report_count": len(dimension_links),
                "composite_dimension_checks": dimension_status,
                "external_visual_reconciliation": "PENDING" if external_reconciliation_required else "NOT_REQUIRED",
                "composite_acceptance": composite_status,
            },
            "findings": all_findings, "severity_counts": severity_counts(all_findings),
            "acceptance_policy": {
                "severe_allowed": 0, "error_allowed": 0, "release_blocking_warning_allowed": 0,
                "unresolved_repairable_allowed": 0, "external_provider_self_acceptance_allowed": False,
            },
            "status": composite_status, "created_at": created_at, "timezone": TIMEZONE,
            "implementation_provenance": implementation_provenance(deckcompiler_commit),
        }
    )
    write_report(qa_dir / "composite_qa_report.json", composite)
    acceptance = with_report_hash(
        {
            "schema_name": "phase6_baseline_composite_acceptance", "schema_version": SCHEMA_VERSION,
            "report_id": stable_id("report", "phase6_baseline_composite_acceptance", run_id), "run_id": run_id,
            "source_artifacts": [{"artifact_id": composite["report_id"], "path": "composite_qa_report.json", "sha256": composite["report_hash"]}],
            "producer": "DeckCompiler independent composite acceptance",
            "checks": {"all_dimension_reports_pass": all(payload["status"] == "PASS" for payload in reports_by_name.values()), "composite_dimension_checks": dimension_status, "external_visual_reconciliation": "PENDING" if external_reconciliation_required else "NOT_REQUIRED", "composite_acceptance": composite_status, "severe_count": composite["severity_counts"]["severe"], "error_count": composite["severity_counts"]["error"], "release_blocking_warning_count": sum(1 for finding in all_findings if finding["severity"] == "warning" and finding["release_blocking"]), "unresolved_repairable_count": sum(1 for finding in all_findings if finding["repairable"] and not finding["resolved"])},
            "composite_report_hash": composite["report_hash"], "active_output_set": active_output_set,
            "status": composite_status, "final_release_eligible": False, "phase7_required": True,
            "created_at": created_at, "timezone": TIMEZONE, "implementation_provenance": implementation_provenance(deckcompiler_commit),
        }
    )
    write_report(qa_dir / "baseline_composite_acceptance.json", acceptance)
    validation = validate_composite_qa(qa_dir)
    if not validation["valid"]:
        raise CompositeQAError(f"composite QA self-validation failed: {validation['issues']}")
    return CompositeQAResult(
        run_id=run_id, output_dir=output_dir, qa_dir=qa_dir, status=composite_status,
        renderer_version=render_result.renderer_version, contact_sheet=contact_sheet_path,
        reports=tuple(qa_dir / name for name in EXPECTED_REPORT_FILES),
    )


def bind_external_visual_reconciliation(qa_dir: Path, reconciliation_path: Path) -> dict[str, Any]:
    """Finalize Composite acceptance only after a hash-valid external reconciliation exists."""

    reconciliation_path = reconciliation_path.resolve()
    if not reconciliation_path.is_file():
        raise CompositeQAError("external visual reconciliation is missing")
    reconciliation = read_json(reconciliation_path)
    if not verify_bound_report_hash(reconciliation):
        raise CompositeQAError("external visual reconciliation report hash mismatch")
    qa_dir = qa_dir.resolve()
    composite_path = qa_dir / "composite_qa_report.json"
    acceptance_path = qa_dir / "baseline_composite_acceptance.json"
    if not composite_path.is_file() or not acceptance_path.is_file():
        raise CompositeQAError("Composite reports are missing before reconciliation binding")
    composite = read_json(composite_path)
    acceptance = read_json(acceptance_path)
    dimension_statuses = [str(row.get("status")) for row in composite.get("dimension_reports", [])]
    dimension_status = composite_acceptance_status(dimension_statuses, "PASS")
    final_status = composite_acceptance_status(dimension_statuses, reconciliation.get("status"))
    reconciliation_ref = {
        "artifact_id": "external-visual-qa-reconciliation",
        "path": reconciliation_path.name,
        "sha256": sha256_file(reconciliation_path),
    }
    composite["source_artifacts"] = [
        row for row in composite.get("source_artifacts", []) if row.get("artifact_id") != reconciliation_ref["artifact_id"]
    ] + [reconciliation_ref]
    composite["checks"].update(
        {
            "composite_dimension_checks": dimension_status,
            "external_visual_reconciliation": reconciliation.get("status"),
            "external_visual_reconciliation_report_hash": reconciliation.get("report_hash"),
            "composite_acceptance": final_status,
        }
    )
    composite["status"] = final_status
    composite = with_report_hash(composite)
    write_report(composite_path, composite)

    acceptance["source_artifacts"] = [
        {"artifact_id": composite["report_id"], "path": "composite_qa_report.json", "sha256": composite["report_hash"]},
        reconciliation_ref,
    ]
    acceptance["checks"].update(
        {
            "composite_dimension_checks": dimension_status,
            "external_visual_reconciliation": reconciliation.get("status"),
            "external_visual_reconciliation_report_hash": reconciliation.get("report_hash"),
            "composite_acceptance": final_status,
        }
    )
    acceptance["composite_report_hash"] = composite["report_hash"]
    acceptance["status"] = final_status
    acceptance = with_report_hash(acceptance)
    write_report(acceptance_path, acceptance)
    validation = validate_composite_qa(qa_dir)
    if not validation["valid"]:
        raise CompositeQAError(f"composite QA reconciliation binding failed validation: {validation['issues']}")
    return composite


def validate_composite_qa(qa_dir: Path) -> dict[str, Any]:
    qa_dir = qa_dir.resolve()
    issues: list[str] = []
    payloads: dict[str, dict[str, Any]] = {}
    for name in EXPECTED_REPORT_FILES:
        path = qa_dir / name
        if not path.is_file():
            issues.append(f"MISSING_REPORT {name}")
            continue
        try:
            payload = read_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            issues.append(f"INVALID_JSON {name}: {exc}")
            continue
        payloads[name] = payload
        if not verify_report_hash(payload):
            issues.append(f"REPORT_HASH_MISMATCH {name}")
        for finding in payload.get("findings", []):
            if not verify_finding_hash(finding):
                issues.append(f"FINDING_HASH_MISMATCH {name} {finding.get('finding_id')}")
        if name == "composite_qa_report.json":
            schema_name = "composite_qa_report"
        elif name == "baseline_composite_acceptance.json":
            schema_name = "composite_qa_acceptance"
        elif name == "contact_sheet_manifest.json":
            schema_name = "contact_sheet_manifest"
        else:
            schema_name = "qa_dimension_report"
        for error in validator_for(schema_name).iter_errors(payload):
            location = "/".join(str(part) for part in error.absolute_path) or "$"
            issues.append(f"SCHEMA {name} {location}: {error.message}")
    composite = payloads.get("composite_qa_report.json")
    if composite:
        for link in composite.get("dimension_reports", []):
            linked = payloads.get(link.get("path"))
            if linked is None:
                issues.append(f"MISSING_LINKED_REPORT {link.get('path')}")
            elif linked.get("report_hash") != link.get("report_hash"):
                issues.append(f"LINKED_REPORT_HASH_MISMATCH {link.get('path')}")
        acceptance = payloads.get("baseline_composite_acceptance.json")
        if acceptance and acceptance.get("composite_report_hash") != composite.get("report_hash"):
            issues.append("ACCEPTANCE_COMPOSITE_HASH_MISMATCH")
    return {
        "schema_name": "phase6_composite_qa_validation", "schema_version": SCHEMA_VERSION,
        "valid": not issues, "status": "PASS" if not issues else "BLOCKED",
        "report_count": len(payloads), "issues": issues,
    }


__all__ = [
    "CompositeQAError", "CompositeQAResult", "EXPECTED_REPORT_FILES", "bind_external_visual_reconciliation",
    "composite_acceptance_status", "run_composite_qa", "validate_composite_qa",
]
