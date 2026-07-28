from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .native_plate_visual_risk import review_native_plate_visual_risk
from .overlay_renderer import render_overlay_image, write_overlay_json
from .overlay_schema import validate_overlay_document
from .patch_request import create_patch_request_from_issue
from .residual_raster_text_review import review_residual_raster_text
from .review_packet import build_review_packet_for_group
from .text_overflow_review import review_text_overflow


FIXTURE_NAMES = ["e01_semantic_raster_fail", "e01b_single_reference_pass", "e02_4core_pass", "canva_benchmark"]


def build_packet(artifact_group: str | Path, out_dir: str | Path | None = None) -> dict[str, Any]:
    packet = build_review_packet_for_group(artifact_group)
    if out_dir:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "review_packet.json").write_text(json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (out / "review_packet.md").write_text(_packet_md(packet), encoding="utf-8")
    return packet


def render_overlay_from_json(image: str | Path, overlay_json: str | Path, out_png: str | Path) -> dict[str, Any]:
    document = json.loads(Path(overlay_json).read_text(encoding="utf-8"))
    return render_overlay_image(image, document, out_png)


def create_patch_request(review_packet_json: str | Path, issue_id: str, out_path: str | Path | None = None) -> dict[str, Any]:
    packet = json.loads(Path(review_packet_json).read_text(encoding="utf-8"))
    request = create_patch_request_from_issue(packet, issue_id)
    if out_path:
        target = Path(out_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(request, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return request


def validate_review_fixture_root(fixtures_root: str | Path, out_dir: str | Path | None = None) -> dict[str, Any]:
    root = Path(fixtures_root)
    packets = {}
    for name in FIXTURE_NAMES:
        packets[name] = build_review_packet_for_group(root / name, fixture_name=name)
    overall = "PASS_WITH_FIXTURE_LIMITATIONS" if packets["e01b_single_reference_pass"]["decision"] == "REVIEW_BLOCKED_MISSING_INPUT" else "PASS"
    report = {
        "schema": "review_fixture_check_report.v1",
        "fixtures_root": str(root),
        "overall_status": overall,
        "fixtures": packets,
        "default_render_performed": False,
        "e03_e04_d08_unlocked": False,
    }
    if out_dir:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "review_fixture_check_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (out / "review_fixture_check_report.md").write_text(
            "\n".join(
                [
                    "# B01 fixture 리뷰 점검",
                    "",
                    f"- 전체 상태: `{overall}`",
                    f"- E01B 상태: `{packets['e01b_single_reference_pass']['decision']}`",
                    "- B01 fixture-check는 기본 렌더링을 수행하지 않는다.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
    return report


def overlay_document_from_packet(packet: dict[str, Any], source_image: str | None = None) -> dict[str, Any]:
    items = []
    for issue in packet.get("visual_issues", []):
        if not issue.get("bbox_norm"):
            continue
        items.append(
            {
                "overlay_item_id": f"overlay_{issue['issue_id']}",
                "issue_id": issue["issue_id"],
                "object_id": issue.get("object_id"),
                "layer_id": issue.get("layer_id"),
                "slot_id": issue.get("slot_id"),
                "label": issue.get("issue_type"),
                "category": _category_for_issue(issue.get("issue_type")),
                "bbox_norm": issue.get("bbox_norm"),
                "severity": issue.get("severity", "warning"),
                "draw_style": "crosshatch" if issue.get("severity") == "fatal" else "outline",
                "message": issue.get("description", ""),
                "evidence_paths": issue.get("evidence_paths", []),
            }
        )
    doc = {
        "schema": "overlay_document.v1",
        "overlay_id": f"{packet.get('packet_id')}_overlay",
        "source_image_path": source_image,
        "source_image_kind": "render",
        "canvas_width_px": 0,
        "canvas_height_px": 0,
        "coordinate_space": "normalized",
        "overlays": items,
        "legend": {"fatal": "blocks product pass", "warning": "manual review or future patch"},
        "provenance": {"source": "B01 review packet"},
        "warnings": [],
    }
    validate_overlay_document(doc)
    return doc


def write_packet_outputs(packet: dict[str, Any], out_json: str | Path, out_md: str | Path, overlay_dir: str | Path | None = None) -> dict[str, Any]:
    json_path = Path(out_json)
    md_path = Path(out_md)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(_packet_md(packet), encoding="utf-8")
    overlay_report = {"status": "OVERLAY_NOT_REQUESTED"}
    if overlay_dir:
        selected = _selected_image(packet)
        overlay = overlay_document_from_packet(packet, selected)
        overlay_path = Path(overlay_dir) / "overlay_document.json"
        write_overlay_json(overlay_path, overlay)
        if selected and overlay["overlays"]:
            overlay_report = render_overlay_image(selected, overlay, Path(overlay_dir) / "review_overlay.png")
        else:
            overlay_report = {"status": "OVERLAY_JSON_ONLY", "reason": "missing selected image or drawable overlay items"}
        index = {"schema": "overlay_index.v1", "overlay_documents": [str(overlay_path)], "render_reports": [overlay_report]}
        Path(overlay_dir).mkdir(parents=True, exist_ok=True)
        (Path(overlay_dir) / "overlay_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (Path(overlay_dir) / "README.md").write_text("# B01 오버레이 산출물\n\n진단용 오버레이 산출물만 포함한다. 원본 fixture 이미지는 수정하지 않았다.\n", encoding="utf-8")
    return overlay_report


def run_review_policies(packet: dict[str, Any]) -> dict[str, Any]:
    selected = _selected_image(packet)
    layers = _load_layers(packet.get("graph_sources", []))
    return {
        "text_overflow": review_text_overflow(render_image=selected, slots=[]),
        "residual_raster_text": review_residual_raster_text(render_image=selected, layers=layers, suppression_evidence=[]),
        "native_plate_visual_risk": review_native_plate_visual_risk(render_image=selected, layers=layers, suppression_plan=[]),
    }


def _packet_md(packet: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {packet.get('fixture_name', packet.get('packet_id'))} 리뷰 패킷",
            "",
            f"- 결정: `{packet.get('decision')}`",
            f"- 리뷰 범위: `{packet.get('review_scope')}`",
            f"- 제품 PASS 허용: `{packet.get('product_pass_allowed')}`",
            f"- 시각 이슈 수: `{len(packet.get('visual_issues', []))}`",
            f"- 패치 요청 수: `{len(packet.get('patch_requests', []))}`",
            "B01 review PASS는 제품 PASS가 아니며, patch request는 적용된 패치가 아니다.",
        ]
    ) + "\n"


def _selected_image(packet: dict[str, Any]) -> str | None:
    for source in packet.get("render_sources", []):
        if source.get("selected_review_image"):
            return source["selected_review_image"]
    return None


def _category_for_issue(issue_type: str | None) -> str:
    mapping = {
        "semantic_raster_text": "semantic_raster_violation",
        "residual_raster_text": "residual_raster_text_risk",
        "text_overflow": "text_overflow_risk",
        "unknown_content_bearing": "unknown_content_bearing",
        "full_slide_raster": "full_slide_raster_risk",
        "native_plate_flatness": "native_plate_visual_risk",
    }
    return mapping.get(str(issue_type), "patch_target")


def _load_layers(paths: list[str]) -> list[dict[str, Any]]:
    layers: list[dict[str, Any]] = []
    for item in paths:
        path = Path(item)
        if not path.is_file() or "layer_manifest" not in path.name.lower():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        layers.extend(data.get("layers", []))
    return layers
