from __future__ import annotations

from pathlib import Path
from typing import Any

from .replay_lineage_compare import compare_with_p02_lineage
from .replay_report import build_stage_execution_report, write_json, write_markdown
from .replay_scope_guard import PPTX_NAME, RENDER_NAME, validate_replay_scope
from .stage_executor import (
    build_b01_review,
    compile_p03_minimal,
    copy_controlled_inputs,
    render_p03_pptx,
    run_b03_stage,
    run_c01_dry_run_stage,
)
from .stage_result import stage_result


def run_controlled_replay(sample_id: str, out_dir: str | Path) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    scope = validate_replay_scope(sample_id=sample_id, mode="CONTROLLED_REPLAY_MINIMAL", out_dir=out)
    write_json(out / "controlled_replay_scope_guard_report.json", scope)
    write_markdown(
        out / "controlled_replay_scope_guard_report.md",
        "P03 Controlled Replay Scope Guard",
        [
            f"- decision: `{scope.get('decision')}`",
            f"- allowed: `{scope.get('allowed')}`",
            "- P03는 controlled minimal sample 하나만 실행한다.",
        ],
    )
    results: list[dict[str, Any]] = []
    if not scope["allowed"]:
        return {"schema": "controlled_replay_run.v1", "decision": "P03_FAIL_REPLAY_SCOPE_GUARD", "scope_guard": scope, "stage_results": results, "product_pass": False}

    results.append(stage_result("A01_REGISTRY_CLAIM_GUARD", "IMPORTED", limitations=["governance imported"]))
    copied = copy_controlled_inputs(out)
    if not all(item["exists"] for item in copied["copied"]):
        results.append(stage_result("T02_NATIVE_RECONSTRUCTION_PLANNER", "FAIL", errors=["missing copied inputs"]))
        return _finish("P03_BLOCKED_MISSING_MINIMAL_SAMPLE_INPUTS", scope, results, copied=copied)
    results.append(stage_result("T02_NATIVE_RECONSTRUCTION_PLANNER", "PASS_WITH_LIMITATIONS", evidence_paths=[copied["input_folder"]], limitations=["minimal sample copied"]))

    dry = run_c01_dry_run_stage(out)
    if dry.get("decision") not in {"DRY_RUN_READY", "DRY_RUN_READY_WITH_WARNINGS"}:
        results.append(stage_result("C01_COMPILER_DRY_RUN", "FAIL", evidence_paths=[str(out / "p03_minimal_cover_hero_dry_run_report.json")], errors=[dry.get("decision", "unknown")]))
        return _finish("P03_FAIL_C01_DRY_RUN_STAGE", scope, results, copied=copied, dry_run=dry)
    results.append(stage_result("C01_COMPILER_DRY_RUN", "PASS_WITH_LIMITATIONS", evidence_paths=[str(out / "p03_minimal_cover_hero_dry_run_report.json")]))

    compile_report = compile_p03_minimal(out)
    if not compile_report.get("pptx_generated"):
        results.append(stage_result("C02B_COMPATIBLE_COMPILE", "FAIL", errors=compile_report.get("blockers", [])))
        return _finish("P03_FAIL_COMPILE_STAGE", scope, results, copied=copied, dry_run=dry, compile_report=compile_report)
    results.append(stage_result("C02B_COMPATIBLE_COMPILE", "PASS_WITH_LIMITATIONS", evidence_paths=[str(out / PPTX_NAME)]))

    b03 = run_b03_stage(out)
    if b03.get("status") not in {"PASS", "PASS_WITH_LIMITATIONS"}:
        results.append(stage_result("B03_PPTX_NATIVE_VALIDATION", "FAIL", errors=b03.get("failures", [])))
        return _finish("P03_FAIL_B03_VALIDATION_STAGE", scope, results, copied=copied, dry_run=dry, compile_report=compile_report, b03=b03)
    results.append(stage_result("B03_PPTX_NATIVE_VALIDATION", "PASS_WITH_LIMITATIONS", evidence_paths=[str(out / "p03_pptx_b03_validation_report.json")]))

    render = render_p03_pptx(out)
    if not render.get("render_generated"):
        results.append(stage_result("C03A_STYLE_CONTROLLED_RENDER", "FAIL", errors=render.get("stdout_stderr_summary", {}).get("errors", [])))
        return _finish("P03_FAIL_RENDER_STAGE", scope, results, copied=copied, dry_run=dry, compile_report=compile_report, b03=b03, render=render)
    results.append(stage_result("C03A_STYLE_CONTROLLED_RENDER", "PASS_WITH_LIMITATIONS", evidence_paths=[str(out / RENDER_NAME)]))

    review = build_b01_review(out, b03)
    if review["review_packet"].get("decision") not in {"REVIEW_READY", "REVIEW_READY_WITH_LIMITATIONS"}:
        results.append(stage_result("B01_REVIEW_PACKET", "FAIL"))
        return _finish("P03_FAIL_B01_REVIEW_STAGE", scope, results, copied=copied, dry_run=dry, compile_report=compile_report, b03=b03, render=render, review=review)
    results.append(stage_result("B01_REVIEW_PACKET", "PASS_WITH_LIMITATIONS", evidence_paths=[str(out / "p03_b01_review_packet.json")]))

    input_hashes = {item["copied_path"]: item["sha256"] for item in copied["copied"]}
    lineage = compare_with_p02_lineage(
        p03_pptx=out / PPTX_NAME,
        p03_render=out / RENDER_NAME,
        input_hashes=input_hashes,
        dry_run_decision=dry.get("decision"),
        b03_status=b03.get("status"),
        review_status=review["review_packet"].get("decision"),
    )
    results.append(stage_result("CLAIM_BOUNDARY_CHECK", "PASS_WITH_LIMITATIONS", limitations=lineage.get("limitations", [])))
    write_json(out / "p03_compare_with_p02_lineage_report.json", lineage)
    write_markdown(
        out / "p03_compare_with_p02_lineage_report.md",
        "P03 / P02 Lineage 비교 보고서",
        [
            f"- status: `{lineage.get('status')}`",
            f"- p03_pptx_hash: `{lineage.get('p03_pptx_hash')}`",
            f"- p03_render_hash: `{lineage.get('p03_render_hash')}`",
            "- hash 차이가 있으면 controlled limitation으로 이월하며 제품 PASS로 해석하지 않는다.",
        ],
    )
    decision = "P03_PASS_WITH_LIMITATIONS_READY_FOR_C04" if lineage.get("status") != "LINEAGE_MISMATCH" else "P03_FAIL_LINEAGE_COMPARE"
    return _finish(decision, scope, results, copied=copied, dry_run=dry, compile_report=compile_report, b03=b03, render=render, review=review, lineage=lineage)


def _finish(decision: str, scope: dict[str, Any], results: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
    run = {"schema": "controlled_replay_run.v1", "decision": decision, "scope_guard": scope, "stage_results": results, "product_pass": False, **kwargs}
    out_path = None
    for key in ("copied", "compile_report", "render"):
        value = kwargs.get(key)
        if isinstance(value, dict):
            candidate = value.get("input_folder") or value.get("output_path")
            if candidate:
                out_path = Path(candidate).resolve().parent
                if out_path.name == "controlled_replay_inputs":
                    out_path = out_path.parent
                break
    if out_path is not None:
        execution = build_stage_execution_report(run)
        write_json(out_path / "controlled_replay_stage_execution_report.json", execution)
        write_json(out_path / "controlled_replay_stage_results.json", {"schema": "controlled_replay_stage_results.v1", "stage_results": results, "product_pass": False})
        write_markdown(out_path / "controlled_replay_stage_execution_report.md", "P03 Stage 실행 보고서", [f"- decision: `{decision}`", f"- stage_count: `{len(results)}`", "- downstream stage는 upstream failure 시 중단된다."])
        write_markdown(out_path / "controlled_replay_stage_results.md", "P03 Stage 결과", [f"- stage_count: `{len(results)}`", "- 모든 stage 결과는 controlled minimal scope로 제한된다."])
    return run
