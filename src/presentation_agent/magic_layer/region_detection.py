"""Deterministic visual region proposal for Magic Layer D01."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageFilter, ImageOps

from .image_asset import load_rgb


@dataclass
class RegionProposal:
    proposal_id: str
    bbox_px: list[int]
    source: str
    reason: str
    confidence: float
    features: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def color_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])


def dominant_corner_color(image: Image.Image) -> tuple[int, int, int]:
    w, h = image.size
    points = [
        (2, 2),
        (w - 3, 2),
        (2, h - 3),
        (w - 3, h - 3),
        (w // 2, h - 3),
    ]
    colors = [image.getpixel(p) for p in points]
    return tuple(int(sum(c[i] for c in colors) / len(colors)) for i in range(3))


def connected_components(mask: list[list[bool]], min_pixels: int = 20) -> list[tuple[int, int, int, int, int]]:
    height = len(mask)
    width = len(mask[0]) if height else 0
    seen = [[False] * width for _ in range(height)]
    components: list[tuple[int, int, int, int, int]] = []
    for y in range(height):
        row = mask[y]
        for x in range(width):
            if not row[x] or seen[y][x]:
                continue
            stack = [(x, y)]
            seen[y][x] = True
            min_x = max_x = x
            min_y = max_y = y
            count = 0
            while stack:
                cx, cy = stack.pop()
                count += 1
                min_x = min(min_x, cx)
                max_x = max(max_x, cx)
                min_y = min(min_y, cy)
                max_y = max(max_y, cy)
                for nx in (cx - 1, cx, cx + 1):
                    for ny in (cy - 1, cy, cy + 1):
                        if nx < 0 or ny < 0 or nx >= width or ny >= height or seen[ny][nx] or not mask[ny][nx]:
                            continue
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            if count >= min_pixels:
                components.append((min_x, min_y, max_x + 1, max_y + 1, count))
    return components


def iou(a: list[int], b: list[int]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix1 = max(ax, bx)
    iy1 = max(ay, by)
    ix2 = min(ax + aw, bx + bw)
    iy2 = min(ay + ah, by + bh)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if not inter:
        return 0.0
    area = aw * ah + bw * bh - inter
    return inter / area if area else 0.0


def merge_duplicate_proposals(proposals: list[RegionProposal]) -> list[RegionProposal]:
    kept: list[RegionProposal] = []
    for proposal in sorted(proposals, key=lambda p: (p.bbox_px[2] * p.bbox_px[3]), reverse=True):
        if any(iou(proposal.bbox_px, other.bbox_px) > 0.72 for other in kept):
            continue
        kept.append(proposal)
    return list(reversed(kept))


def detect_regions(image_path: Path, *, reference_id: str, archetype_hint: str = "unknown") -> list[RegionProposal]:
    image = load_rgb(image_path)
    width, height = image.size
    proposals: list[RegionProposal] = [
        RegionProposal(
            proposal_id="p_background_base",
            bbox_px=[0, 0, width, height],
            source="rule_based",
            reason="canvas background base; no crop accepted",
            confidence=0.99,
            features={"area_ratio": 1.0},
        )
    ]
    bg = dominant_corner_color(image)
    max_w = 420
    scale = max_w / width if width > max_w else 1.0
    small = image.resize((int(width * scale), int(height * scale)), Image.Resampling.BILINEAR)
    sw, sh = small.size
    diff_mask: list[list[bool]] = []
    for y in range(sh):
        row: list[bool] = []
        for x in range(sw):
            pixel = small.getpixel((x, y))
            row.append(color_distance(pixel, bg) > 55)
        diff_mask.append(row)
    components = connected_components(diff_mask, min_pixels=max(12, int(sw * sh * 0.00018)))
    idx = 1
    for x1, y1, x2, y2, count in components:
        x = max(0, int(x1 / scale) - 4)
        y = max(0, int(y1 / scale) - 4)
        w = min(width - x, int((x2 - x1) / scale) + 8)
        h = min(height - y, int((y2 - y1) / scale) + 8)
        area_ratio = (w * h) / (width * height)
        if area_ratio < 0.00025 or area_ratio > 0.78:
            continue
        aspect = w / h if h else 0
        proposals.append(
            RegionProposal(
                proposal_id=f"p_cv_{idx:03d}",
                bbox_px=[x, y, w, h],
                source="auto_cv",
                reason="foreground color connected component",
                confidence=min(0.88, 0.42 + area_ratio * 6 + min(count / 5000, 0.24)),
                features={"area_ratio": round(area_ratio, 5), "aspect_ratio": round(aspect, 3), "component_pixels": count},
            )
        )
        idx += 1

    edge = ImageOps.autocontrast(image.convert("L").filter(ImageFilter.FIND_EDGES))
    edge_small = edge.resize((sw, sh), Image.Resampling.BILINEAR)
    edge_mask: list[list[bool]] = []
    for y in range(sh):
        row = []
        for x in range(sw):
            row.append(edge_small.getpixel((x, y)) > 42)
        edge_mask.append(row)
    for x1, y1, x2, y2, count in connected_components(edge_mask, min_pixels=max(20, int(sw * sh * 0.00028)))[:60]:
        x = max(0, int(x1 / scale) - 3)
        y = max(0, int(y1 / scale) - 3)
        w = min(width - x, int((x2 - x1) / scale) + 6)
        h = min(height - y, int((y2 - y1) / scale) + 6)
        area_ratio = (w * h) / (width * height)
        if area_ratio < 0.0002 or area_ratio > 0.6:
            continue
        proposals.append(
            RegionProposal(
                proposal_id=f"p_edge_{idx:03d}",
                bbox_px=[x, y, w, h],
                source="auto_cv",
                reason="edge-map connected component",
                confidence=min(0.72, 0.35 + area_ratio * 5),
                features={"area_ratio": round(area_ratio, 5), "edge_pixels": count},
            )
        )
        idx += 1

    heuristics = [
        ("p_rule_title_zone", [int(width * 0.035), int(height * 0.035), int(width * 0.52), int(height * 0.18)], "title-like top protected zone", 0.48),
        ("p_rule_footer_strip", [int(width * 0.025), int(height * 0.885), int(width * 0.95), int(height * 0.075)], "bottom source/footer strip heuristic", 0.68),
    ]
    if "cover" in archetype_hint:
        heuristics.append(("p_rule_hero_visual", [int(width * 0.05), int(height * 0.13), int(width * 0.36), int(height * 0.68)], "cover hero visual field heuristic", 0.62))
    if any(token in archetype_hint for token in ("dashboard", "table", "matrix")):
        heuristics.append(("p_rule_data_region", [int(width * 0.08), int(height * 0.22), int(width * 0.72), int(height * 0.58)], "data/table/chart region heuristic", 0.58))
    for proposal_id, bbox, reason, confidence in heuristics:
        proposals.append(RegionProposal(proposal_id=proposal_id, bbox_px=bbox, source="rule_based", reason=reason, confidence=confidence, features={"area_ratio": round((bbox[2] * bbox[3]) / (width * height), 5)}))

    deduped = merge_duplicate_proposals(proposals)
    for i, proposal in enumerate(deduped, start=1):
        proposal.proposal_id = f"{reference_id}_proposal_{i:03d}"
    return deduped[:80]
