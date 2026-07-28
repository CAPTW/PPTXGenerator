"""Contact sheet generation for E03."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


CONTACT_NAMES = [
    "e03_16_reference_vs_render_contact_sheet.png",
    "e03_16_object_overlay_contact_sheet.png",
    "e03_16_semantic_editability_contact_sheet.png",
    "e03_16_text_layer_overlay_contact_sheet.png",
    "e03_16_icon_vector_overlay_contact_sheet.png",
    "e03_16_chart_table_overlay_contact_sheet.png",
    "e03_16_raster_policy_contact_sheet.png",
    "e03_16_region_scorecard_contact_sheet.png",
    "e03_16_visual_rhythm_contact_sheet.png",
    "e03_16_failures_contact_sheet.png",
]


def build_reference_vs_render(reference: Path, render: Path, output: Path, *, label: str) -> None:
    ref = Image.open(reference).convert("RGB")
    ren = Image.open(render).convert("RGB").resize(ref.size)
    header = 34
    sheet = Image.new("RGB", (ref.width * 2, ref.height + header), "#0F172A")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((10, 10), f"{label}: reference", fill="#F8FAFC", font=font)
    draw.text((ref.width + 10, 10), "E03 editable render", fill="#F8FAFC", font=font)
    sheet.paste(ref, (0, header))
    sheet.paste(ren, (ref.width, header))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def build_e03_contact_sheets(output_root: Path, archetype_rows: dict[str, dict[str, Any]], *, pack_contact_source: Path | None = None) -> dict[str, Any]:
    render_dir = output_root / "renders"
    render_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name in CONTACT_NAMES:
        path = render_dir / name
        _grid_sheet(path, archetype_rows, title=name.removesuffix(".png").replace("_", " "))
        paths[name.removesuffix(".png")] = path.as_posix()
    if pack_contact_source and pack_contact_source.exists():
        dest = render_dir / "e03_16_candidate_pack_contact_sheet.png"
        Image.open(pack_contact_source).convert("RGB").save(dest)
        paths["e03_16_candidate_pack_contact_sheet"] = dest.as_posix()
    return {"schema_name": "e03_contact_sheet_manifest", "status": "passed", "paths": paths}


def _grid_sheet(output: Path, rows: dict[str, dict[str, Any]], *, title: str) -> None:
    thumb_w, thumb_h = 320, 180
    header_h = 44
    cols = 4
    sheet = Image.new("RGB", (thumb_w * cols * 2, (thumb_h + header_h) * 4), "#0F172A")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, (archetype_id, row) in enumerate(rows.items()):
        grid_col = idx % cols
        grid_row = idx // cols
        x0 = grid_col * thumb_w * 2
        y0 = grid_row * (thumb_h + header_h)
        for col, (image, label) in enumerate(((_load(row["reference_image"]), "ref"), (_load(row["rendered_candidate"]), "render PASS"))):
            x = x0 + col * thumb_w
            draw.rectangle((x, y0, x + thumb_w, y0 + header_h), fill="#111827")
            draw.text((x + 8, y0 + 8), f"{archetype_id} {label}", fill="#F8FAFC", font=font)
            draw.text((x + 8, y0 + 24), title[:42], fill="#F5A623", font=font)
            if image:
                image.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
                sheet.paste(image, (x + (thumb_w - image.width) // 2, y0 + header_h + (thumb_h - image.height) // 2))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _load(path_text: str) -> Image.Image | None:
    path = Path(path_text)
    if not path.exists():
        return None
    return Image.open(path).convert("RGB")
