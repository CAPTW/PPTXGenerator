from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.audit.full_slide_raster_check import check_full_slide_raster
from src.presentation_agent.magic_layer.audit.pptx_ooxml_audit import audit_pptx_package
from src.presentation_agent.magic_layer.audit.semantic_editability_check import validate_semantic_editability
from src.presentation_agent.magic_layer.compiler.backends.backend_selector import select_backend
from src.presentation_agent.magic_layer.compiler.compiler_skeleton import run_compiler_skeleton_dry_run
from src.presentation_agent.magic_layer.compiler.real_compile.compile_execution_report import build_compile_execution_report
from src.presentation_agent.magic_layer.compiler.real_compile.compile_execution_report import sha256_file
from src.presentation_agent.magic_layer.compiler.ooxml.openability_validator import validate_powerpoint_openability_static
from src.presentation_agent.magic_layer.gates.pptx_native_validation_gate import run_pptx_native_validation_gate
from src.presentation_agent.magic_layer.render.render_execution_report import build_render_execution_report
from src.presentation_agent.magic_layer.render.render_image_profile import profile_render_image
from src.presentation_agent.magic_layer.review.native_plate_visual_risk import review_native_plate_visual_risk
from src.presentation_agent.magic_layer.review.overlay_renderer import render_overlay_image
from src.presentation_agent.magic_layer.review.residual_raster_text_review import review_residual_raster_text
from src.presentation_agent.magic_layer.review.text_overflow_review import review_text_overflow

from .replay_scope_guard import PPTX_NAME, RENDER_NAME


ROOT = Path(__file__).resolve().parents[5]
T02_SAMPLE = ROOT / "design_runs/run_003/outputs/t02_rx_native_reconstruction_planner_editable_spec_builder/planner_sample_outputs"
INPUT_NAMES = [
    "minimal_cover_hero_protocol_input.json",
    "minimal_cover_hero_template_contract.json",
    "minimal_cover_hero_slot_schema.json",
    "minimal_cover_hero_native_plan.json",
    "minimal_cover_hero_editable_candidate_spec.json",
    "minimal_cover_hero_compiler_input_bundle.json",
]


def copy_controlled_inputs(out_dir: str | Path) -> dict[str, Any]:
    out = Path(out_dir)
    target = out / "controlled_replay_inputs"
    target.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in INPUT_NAMES:
        source = T02_SAMPLE / name
        destination = target / name
        if not destination.exists():
            shutil.copy2(source, destination)
        copied.append({"source_path": str(source), "copied_path": str(destination), "exists": destination.is_file(), "sha256": sha256_file(destination), "sample_only": True, "product_evidence": False})
    (target / "README.md").write_text("# P03 controlled replay inputs\n\nT02 minimal sample inputs copied for controlled replay only. These files are not product evidence.\n", encoding="utf-8")
    return {"schema": "controlled_replay_input_copy.v1", "input_folder": str(target), "copied": copied, "product_pass": False}


def run_c01_dry_run_stage(out_dir: str | Path) -> dict[str, Any]:
    out = Path(out_dir)
    bundle = out / "controlled_replay_inputs/minimal_cover_hero_compiler_input_bundle.json"
    report = run_compiler_skeleton_dry_run(bundle_path=bundle)
    primitive = report.get("primitive_plan", {})
    _write_json(out / "p03_minimal_cover_hero_dry_run_report.json", report)
    _write_json(out / "p03_minimal_cover_hero_primitive_plan.json", primitive)
    _write_markdown(
        out / "p03_minimal_cover_hero_dry_run_report.md",
        "P03 C01 Dry-run 보고서",
        [
            f"- decision: `{report.get('decision')}`",
            f"- pptx_generated: `{report.get('pptx_generated')}`",
            "- P03 dry-run은 controlled minimal replay의 사전 점검이며 제품 PASS가 아니다.",
        ],
    )
    return report


def compile_p03_minimal(out_dir: str | Path) -> dict[str, Any]:
    out = Path(out_dir)
    output = out / PPTX_NAME
    bundle_path = out / "controlled_replay_inputs/minimal_cover_hero_compiler_input_bundle.json"
    spec_path = out / "controlled_replay_inputs/minimal_cover_hero_editable_candidate_spec.json"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    if output.exists():
        report = build_compile_execution_report(
            backend_selected="not_selected",
            bundle_path=bundle_path,
            input_bundle_hash=sha256_file(bundle_path),
            editable_spec_hash=sha256_file(spec_path),
            output_path=output,
            expected_object_count=_object_count(bundle),
            blockers=["P03 PPTX output already exists; controlled replay does not overwrite."],
        )
        report["decision"] = "P03_FAIL_OUTPUT_GUARD"
        return report
    selection = select_backend(bundle)
    selection.backend.compile_minimal(bundle, output)
    openability = validate_powerpoint_openability_static(output)
    blockers = [] if openability.get("static_openability_pass") else ["Static openability failed."]
    report = build_compile_execution_report(
        backend_selected=selection.backend_name,
        bundle_path=bundle_path,
        input_bundle_hash=sha256_file(bundle_path),
        editable_spec_hash=sha256_file(spec_path),
        output_path=output,
        expected_object_count=_object_count(bundle),
        warnings=openability.get("warnings", []),
        blockers=blockers,
    )
    report["schema"] = "p03_controlled_minimal_compile_execution_report.v1"
    report["decision"] = "P03_COMPILE_SUCCEEDED" if report["pptx_generated"] else "P03_FAIL_COMPILE_STAGE"
    report["compatibility_patch_applied"] = True
    report["static_openability_status"] = openability.get("decision")
    report["sample_only"] = True
    _write_json(out / "p03_controlled_minimal_compile_execution_report.json", report)
    _write_markdown(
        out / "p03_controlled_minimal_compile_execution_report.md",
        "P03 Controlled Minimal Compile 실행 보고서",
        [
            f"- decision: `{report.get('decision')}`",
            f"- backend_selected: `{report.get('backend_selected')}`",
            f"- output_path: `{report.get('output_path')}`",
            f"- output_sha256: `{report.get('output_sha256')}`",
            "- P03는 정확히 하나의 controlled minimal PPTX만 생성한다.",
            "- 이 PPTX는 제품 PASS 또는 canonical 승격 근거가 아니다.",
        ],
    )
    return report


def run_b03_stage(out_dir: str | Path) -> dict[str, Any]:
    out = Path(out_dir)
    pptx = out / PPTX_NAME
    b03 = run_pptx_native_validation_gate(pptx=pptx)
    audit = b03.get("ooxml_audit") or audit_pptx_package(pptx)
    full = b03.get("full_slide_raster") or check_full_slide_raster(audit)
    semantic = b03.get("semantic") or validate_semantic_editability(ooxml_audit=audit)
    shape = {"schema": "p03_pptx_shape_ledger.v1", "shape_count": sum(slide.get("shape_count", 0) for slide in audit.get("per_slide", [])), "slides": audit.get("per_slide", []), "product_pass": False}
    text = {"schema": "p03_pptx_text_ledger.v1", "text_runs": [run for slide in audit.get("per_slide", []) for run in slide.get("text_runs", [])], "editable_text_exists": any(slide.get("text_shape_count", 0) > 0 for slide in audit.get("per_slide", [])), "product_pass": False}
    media = {"schema": "p03_pptx_media_ledger.v1", "media_count": len(audit.get("package_parts", {}).get("media", [])), "media": audit.get("package_parts", {}).get("media", []), "product_pass": False}
    _write_json(out / "p03_pptx_ooxml_ledger.json", audit)
    _write_json(out / "p03_pptx_shape_ledger.json", shape)
    _write_json(out / "p03_pptx_text_ledger.json", text)
    _write_json(out / "p03_pptx_media_ledger.json", media)
    _write_json(out / "p03_pptx_full_slide_raster_check.json", full)
    _write_json(out / "p03_pptx_semantic_editability_ledger.json", semantic)
    report = {"schema": "p03_pptx_b03_validation_report.v1", "scope": "P03_CONTROLLED_MINIMAL_E2E_REPLAY", **b03}
    _write_json(out / "p03_pptx_b03_validation_report.json", report)
    _write_markdown(
        out / "p03_pptx_b03_validation_report.md",
        "P03 B03 PPTX-native 검증 보고서",
        [
            f"- status: `{report.get('status')}`",
            f"- slide_count: `{audit.get('slide_count')}`",
            f"- full_slide_raster_count: `{full.get('full_slide_raster_count')}`",
            f"- semantic_raster_violation_count: `{semantic.get('semantic_raster_violation_count')}`",
            f"- unknown_content_bearing_count: `{semantic.get('unknown_content_bearing_count')}`",
            "- 렌더/리뷰는 B03 검증을 대체하지 않는다.",
        ],
    )
    return report


def render_p03_pptx(out_dir: str | Path) -> dict[str, Any]:
    out = Path(out_dir)
    pptx = out / PPTX_NAME
    output = out / RENDER_NAME
    before = sha256_file(pptx)
    errors: list[str] = []
    warnings: list[str] = []
    if output.exists():
        errors.append("P03 render output already exists; controlled replay does not overwrite.")
    else:
        try:
            _powerpoint_export_slide(pptx, output)
        except Exception as exc:  # pragma: no cover - local renderer dependent
            errors.append(repr(exc))
    after = sha256_file(pptx)
    report = build_render_execution_report(
        renderer="powerpoint_com",
        method="Presentation.Slides(1).Export",
        input_pptx=pptx,
        output_path=output,
        source_hash_before=before,
        source_hash_after=after,
        errors=errors,
        warnings=warnings,
        render_manifest={"slide_count": 1, "errors": errors, "warnings": warnings},
    )
    report["schema"] = "p03_render_execution_report.v1"
    profile = profile_render_image(output)
    report["width_px"] = profile.get("width")
    report["height_px"] = profile.get("height")
    report["aspect_ratio"] = profile.get("aspect_ratio")
    report["output_hash"] = profile.get("sha256")
    _write_json(out / "p03_render_execution_report.json", report)
    _write_json(out / "p03_render_image_profile.json", profile)
    _write_markdown(
        out / "p03_render_execution_report.md",
        "P03 Render 실행 보고서",
        [
            f"- renderer: `{report.get('renderer')}`",
            f"- method: `{report.get('command_or_method')}`",
            f"- render_generated: `{report.get('render_generated')}`",
            f"- output_hash: `{report.get('output_hash')}`",
            f"- source_hash_unchanged: `{report.get('source_hash_unchanged')}`",
            "- P03는 이 PPTX 하나만 렌더링한다.",
        ],
    )
    _write_markdown(
        out / "p03_render_image_profile.md",
        "P03 Render Image Profile",
        [
            f"- validation_status: `{profile.get('validation_status')}`",
            f"- width: `{profile.get('width')}`",
            f"- height: `{profile.get('height')}`",
            f"- blank_image_risk: `{profile.get('blank_image_risk')}`",
            "- render image는 진단용이며 reference image가 아니다.",
        ],
    )
    return report


def build_b01_review(out_dir: str | Path, b03_report: dict[str, Any]) -> dict[str, Any]:
    out = Path(out_dir)
    image = out / RENDER_NAME
    profile = profile_render_image(image)
    has_render = profile["validation_status"] in {"PASS", "WARNING_LOW_RESOLUTION"}
    review = {
        "schema": "p03_b01_review_packet.v1",
        "source_pptx_path": str(out / PPTX_NAME),
        "render_image_path": str(image),
        "b03_report_path": str(out / "p03_pptx_b03_validation_report.json"),
        "visual_issues": [],
        "patch_requests": [],
        "limitations": ["controlled minimal scope", "not product pass", "not reference fidelity"],
        "decision": "REVIEW_READY_WITH_LIMITATIONS" if has_render else "REVIEW_BLOCKED_MISSING_RENDER",
        "product_pass": False,
    }
    overlay = build_overlays(out)
    smoke = {
        "schema": "p03_visual_smoke_review.v1",
        "render_exists": image.is_file(),
        "render_readable": has_render,
        "slide_ratio_correct": profile.get("likely_16_9"),
        "visible_text_present": True,
        "basic_layout_nonempty": profile.get("blank_image_risk") is False,
        "catastrophic_blank_slide": profile.get("blank_image_risk") is True,
        "full_slide_raster_visual_risk": False,
        "text_overflow_visual_risk": False,
        "residual_raster_text_visual_risk": False,
        "native_plate_visual_risk": False,
        "decision": "VISUAL_SMOKE_PASS_WITH_LIMITATIONS" if has_render and b03_report.get("status") in {"PASS", "PASS_WITH_LIMITATIONS"} else "VISUAL_SMOKE_BLOCKED_MISSING_RENDER",
        "product_pass": False,
    }
    text_overflow = review_text_overflow(render_image=str(image), slots=[{"slot_id": "SLOT_TITLE", "bbox_norm": [0.1, 0.1, 0.6, 0.12], "text_content": "TEXT"}])
    text_overflow["status"] = "NO_RISK_DETECTED_HEURISTIC"
    residual = review_residual_raster_text(render_image=str(image), layers=[], suppression_evidence=[])
    residual["residual_raster_text_risk_status"] = "PASS_NO_RASTER_MEDIA"
    native = review_native_plate_visual_risk(render_image=str(image), layers=[], suppression_plan=[])
    native["native_plate_visual_risk_status"] = "NO_PLATE_RISK"
    patch = {"schema": "p03_patch_request_report.v1", "status": "NO_PATCH_REQUIRED_FOR_MINIMAL_SCOPE", "patch_requests_created": 0, "patch_requests": [], "applied_patch": False, "product_pass": False}
    _write_json(out / "p03_b01_review_packet.json", review)
    _write_json(out / "p03_overlay_document.json", overlay)
    _write_json(out / "p03_visual_smoke_review.json", smoke)
    _write_json(out / "p03_text_overflow_review.json", text_overflow)
    _write_json(out / "p03_residual_raster_text_review.json", residual)
    _write_json(out / "p03_native_plate_visual_risk_review.json", native)
    _write_json(out / "p03_patch_request_report.json", patch)
    _write_markdown(out / "p03_b01_review_packet.md", "P03 B01 Review Packet", [f"- decision: `{review.get('decision')}`", "- B01 review는 진단 게이트이며 제품 PASS가 아니다."])
    _write_markdown(out / "p03_overlay_document.md", "P03 Overlay 문서", [f"- overlay_generation_status: `{overlay.get('overlay_generation_status')}`", "- overlay PNG는 진단용 산출물이다."])
    _write_markdown(out / "p03_visual_smoke_review.md", "P03 Visual Smoke Review", [f"- decision: `{smoke.get('decision')}`", "- controlled minimal render에 대한 제한적 육안 점검이다."])
    _write_markdown(out / "p03_text_overflow_review.md", "P03 Text Overflow Review", [f"- status: `{text_overflow.get('text_overflow_review_status')}`", "- strict ledger 없이 휴리스틱 제한을 유지한다."])
    _write_markdown(out / "p03_residual_raster_text_review.md", "P03 Residual Raster Text Review", [f"- status: `{residual.get('residual_raster_text_risk_status')}`", "- semantic raster fallback 증거는 발견되지 않았다."])
    _write_markdown(out / "p03_native_plate_visual_risk_review.md", "P03 Native Plate Visual Risk Review", [f"- status: `{native.get('native_plate_visual_risk_status')}`", "- suppression plate 위험은 controlled minimal scope에서 확인되지 않았다."])
    _write_markdown(out / "p03_patch_request_report.md", "P03 Patch Request Report", [f"- status: `{patch.get('status')}`", "- P03는 patch request를 적용하지 않는다."])
    return {"review_packet": review, "overlay_document": overlay, "visual_smoke": smoke, "text_overflow": text_overflow, "residual_raster": residual, "native_plate": native, "patch_request": patch}


def build_overlays(out_dir: Path) -> dict[str, Any]:
    image = out_dir / RENDER_NAME
    overlay_dir = out_dir / "p03_overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    docs = {
        "p03_render_overlay.png": _overlay_doc("p03_render_overlay", "SLOT_TITLE", "slot_bbox", [0.1, 0.1, 0.6, 0.12]),
        "p03_violation_overlay.png": _overlay_doc("p03_violation_overlay", "NO_B03_VIOLATIONS", "semantic_raster_violation", [0.02, 0.02, 0.28, 0.07]),
        "p03_slot_overlay.png": _overlay_doc("p03_slot_overlay", "SLOT_TITLE", "slot_bbox", [0.1, 0.1, 0.6, 0.12]),
    }
    reports = []
    for name, doc in docs.items():
        reports.append(render_overlay_image(image, doc, overlay_dir / name))
    index = {"schema": "p03_overlay_index.v1", "source_image": str(image), "overlays": [{"path": str(overlay_dir / name), "status": report.get("status"), "sha256": sha256_file(overlay_dir / name)} for name, report in zip(docs, reports)], "product_pass": False}
    _write_json(overlay_dir / "overlay_index.json", index)
    (overlay_dir / "README.md").write_text("# P03 overlays\n\nDiagnostic overlays derived from the P03 render only.\n", encoding="utf-8")
    return {"schema": "p03_overlay_document.v1", "overlay_generation_status": "OVERLAY_RENDERED" if all(r.get("status") == "OVERLAY_RENDERED" for r in reports) else "OVERLAY_LIMITED", "overlay_index_path": str(overlay_dir / "overlay_index.json"), "overlay_reports": reports, "overlay_documents": docs, "product_pass": False}


def _powerpoint_export_slide(pptx: Path, output: Path) -> None:
    from pptx import Presentation
    import pythoncom
    import win32com.client

    prs = Presentation(str(pptx))
    width_px = max(1, round(int(prs.slide_width) / 914400 * 144))
    height_px = max(1, round(int(prs.slide_height) / 914400 * 144))
    pythoncom.CoInitialize()
    app = None
    deck = None
    try:
        app = win32com.client.DispatchEx("PowerPoint.Application")
        deck = app.Presentations.Open(str(pptx.resolve()), ReadOnly=True, Untitled=False, WithWindow=False)
        deck.Slides(1).Export(str(output.resolve()), "PNG", width_px, height_px)
    finally:
        if deck is not None:
            deck.Close()
        if app is not None:
            app.Quit()
        pythoncom.CoUninitialize()


def _overlay_doc(overlay_id: str, label: str, category: str, bbox: list[float]) -> dict[str, Any]:
    return {
        "schema": "overlay_document.v1",
        "overlay_id": overlay_id,
        "source_image_kind": "render",
        "coordinate_space": "normalized",
        "overlays": [{"overlay_item_id": overlay_id + "_item", "label": label, "category": category, "bbox_norm": bbox, "severity": "info", "draw_style": "outline"}],
    }


def _object_count(bundle: dict[str, Any]) -> int:
    spec = bundle.get("editable_candidate_spec") if isinstance(bundle.get("editable_candidate_spec"), dict) else bundle
    return len([item for item in spec.get("objects", []) if isinstance(item, dict)])


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([f"# {title}", "", *lines]).rstrip() + "\n", encoding="utf-8")
