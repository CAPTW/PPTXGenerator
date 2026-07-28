"""Z-order estimation for Magic Layer D01."""

from __future__ import annotations

from typing import Any


Z_PRIORITY = {
    "background_base": 0,
    "decorative_texture": 10,
    "hero_visual_field": 20,
    "image_frame": 25,
    "shadow_or_glow": 30,
    "card_panel": 40,
    "chart_region": 45,
    "table_region": 45,
    "matrix_region": 45,
    "crop_mask_frame": 50,
    "accent_line": 55,
    "connector": 58,
    "technical_overlay": 60,
    "source_footer_strip": 70,
    "icon_region": 80,
    "body_text_region": 85,
    "subtitle_text_region": 88,
    "title_text_region": 90,
    "unknown": 35,
}


def overlap_ratio(a: list[int], b: list[int]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix1 = max(ax, bx)
    iy1 = max(ay, by)
    ix2 = min(ax + aw, bx + bw)
    iy2 = min(ay + ah, by + bh)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    smaller = min(aw * ah, bw * bh)
    return inter / smaller if smaller else 0.0


def estimate_z_order(layers: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    enriched = []
    for layer in layers:
        x, y, w, h = layer["bbox_px"]
        area = w * h
        priority = Z_PRIORITY.get(layer["layer_type"], 35)
        score = priority - min(area / 1_000_000, 6) + (y / 100_000)
        enriched.append((score, layer))
    ordered = [layer for _score, layer in sorted(enriched, key=lambda item: item[0])]
    unresolved = []
    for idx, layer in enumerate(ordered):
        layer["z_order"] = idx
    for i, a in enumerate(ordered):
        for b in ordered[i + 1 :]:
            if overlap_ratio(a["bbox_px"], b["bbox_px"]) > 0.55 and abs(Z_PRIORITY.get(a["layer_type"], 35) - Z_PRIORITY.get(b["layer_type"], 35)) < 8:
                unresolved.append({"layer_a": a["layer_id"], "layer_b": b["layer_id"], "reason": "high overlap with similar semantic priority"})
    report = {
        "status": "passed" if not unresolved else "passed_with_unresolved_overlaps",
        "z_order_confidence": round(max(0.45, 1 - len(unresolved) / max(1, len(ordered))), 3),
        "unresolved_overlaps": unresolved,
    }
    return ordered, report
