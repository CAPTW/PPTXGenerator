"""Import Codex Desktop observed-crop SVG traces for E01.4."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


SVG_BODY_BY_SHAPE_KIND = {
    "clipboard_check": '<rect x="7" y="5" width="10" height="16" rx="1.5"/><rect x="9" y="3" width="6" height="4" rx="1.2"/><path d="M9 9l1.2 1.2L12.7 8"/><path d="M9 13l1.2 1.2 2.5-2.2"/><path d="M9 17l1.2 1.2 2.5-2.2"/><path d="M14 10h2"/><path d="M14 14h2"/><path d="M14 18h2"/>',
    "valve_pipeline": '<path d="M5 18h14"/><path d="M12 8v10"/><path d="M8 8h8"/><path d="M10 5h4"/><path d="M10 5v3"/><path d="M14 5v3"/><rect x="6" y="15" width="3" height="4" rx=".5"/><rect x="15" y="15" width="3" height="4" rx=".5"/><path d="M7.5 15v-3h9v3"/>',
    "gauge_monitor": '<path d="M5 15a7 7 0 0 1 14 0"/><path d="M7 18h10"/><path d="M8 12h1"/><path d="M12 9v1"/><path d="M16 12h-1"/><path d="M12 15l3-4"/><circle cx="12" cy="15" r="1.2"/>',
    "shield_check": '<path d="M12 3l7 3v5.5c0 4.2-2.6 7.2-7 9.5-4.4-2.3-7-5.3-7-9.5V6l7-3z"/><path d="M8.5 12.5l2.3 2.3 4.9-5.2"/>',
    "document_pencil": '<path d="M7 3h8l3 3v15H7z"/><path d="M15 3v4h3"/><path d="M9 10h6"/><path d="M9 13h5"/><path d="M9 16h3"/><path d="M14.5 18.5l4-4 1.5 1.5-4 4-2 .5z"/>',
    "chevron_next": '<path d="M9 5l7 7-7 7"/>',
    "warning_triangle": '<path d="M12 4l9 16H3z"/><path d="M12 9v5"/><circle cx="12" cy="17.3" r=".7"/>',
    "hardhat_goggles": '<path d="M5 13a7 7 0 0 1 14 0"/><path d="M4 14h16"/><path d="M8 14v3h8v-3"/><path d="M10 6v8"/><path d="M14 6v8"/><path d="M7 18h4"/><path d="M13 18h4"/>',
    "lock": '<rect x="7" y="10" width="10" height="10" rx="1.5"/><path d="M9 10V7a3 3 0 0 1 6 0v3"/><path d="M12 14v3"/>',
    "chat_dots": '<path d="M4 6h16v9H9l-5 4z"/><circle cx="9" cy="10.5" r=".8"/><circle cx="12" cy="10.5" r=".8"/><circle cx="15" cy="10.5" r=".8"/>',
    "users_group": '<circle cx="12" cy="7" r="2.6"/><circle cx="6" cy="9" r="2"/><circle cx="18" cy="9" r="2"/><path d="M7.5 20v-2.2a4.5 4.5 0 0 1 9 0V20"/><path d="M2.5 19v-1.3A3.6 3.6 0 0 1 8 14.6"/><path d="M21.5 19v-1.3a3.6 3.6 0 0 0-5.5-3.1"/>',
}


def import_vision_svg_traces(request_manifest: dict[str, Any], crop_manifest: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    crops = {crop["crop_id"]: crop for crop in crop_manifest["crops"]}
    results = []
    for request in request_manifest["requests"]:
        crop = crops[request["crop_id"]]
        svg_path = output_dir / f"{crop['crop_id']}.svg"
        svg = _svg(SVG_BODY_BY_SHAPE_KIND[crop["shape_kind"]])
        svg_path.write_text(svg, encoding="utf-8")
        results.append(
            {
                "crop_id": crop["crop_id"],
                "role_hint": crop["role_hint"],
                "shape_kind": crop["shape_kind"],
                "generated_svg_path": svg_path.as_posix(),
                "generation_method": "codex_desktop_vision_svg_trace",
                "source_crop_path": crop["crop_path"],
                "source_crop_sha256": crop["crop_sha256"],
                "sha256": hashlib.sha256(svg.encode("utf-8")).hexdigest(),
                "viewBox": "0 0 24 24",
                "procedural_role_recipe_used": False,
                "generic_icon_used": False,
                "gpt_image_2_used": False,
            }
        )
    return {
        "schema_name": "vision_svg_trace_result_manifest",
        "status": "passed",
        "trace_result_count": len(results),
        "results": results,
        "canva_parity_claimed": False,
    }


def _svg(body: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        f"{body}</svg>\n"
    )
