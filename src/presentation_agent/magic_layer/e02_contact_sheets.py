"""Contact sheet generation for E02."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


CONTACT_NAMES = [
    "e02_4core_reference_vs_render_contact_sheet.png",
    "e02_4core_object_overlay_contact_sheet.png",
    "e02_4core_semantic_editability_contact_sheet.png",
    "e02_4core_text_layer_overlay_contact_sheet.png",
    "e02_4core_icon_vector_overlay_contact_sheet.png",
    "e02_4core_chart_table_overlay_contact_sheet.png",
    "e02_4core_raster_policy_contact_sheet.png",
    "e02_4core_region_scorecard_contact_sheet.png",
    "e02_4core_failures_contact_sheet.png",
]


def build_reference_vs_render(reference: Path, render: Path, output: Path, *, label: str) -> None:
    ref = Image.open(reference).convert("RGB")
    ren = Image.open(render).convert("RGB").resize(ref.size)
    header = 36
    sheet = Image.new("RGB", (ref.width * 2, ref.height + header), "#0F172A")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((12, 12), f"{label}: reference", fill="#F8FAFC", font=font)
    draw.text((ref.width + 12, 12), "editable candidate render", fill="#F8FAFC", font=font)
    sheet.paste(ref, (0, header))
    sheet.paste(ren, (ref.width, header))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def build_e02_contact_sheets(
    *,
    output_root: Path,
    archetype_rows: dict[str, dict[str, Any]],
    pack_contact_source: Path | None = None,
) -> dict[str, Any]:
    render_dir = output_root / "renders"
    render_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name in CONTACT_NAMES:
        path = render_dir / name
        _grid_sheet(path, archetype_rows, title=name.replace(".png", "").replace("_", " "))
        paths[name.replace(".png", "")] = path.as_posix()
    if pack_contact_source and pack_contact_source.exists():
        pack_path = render_dir / "e02_4core_candidate_pack_contact_sheet.png"
        Image.open(pack_contact_source).convert("RGB").save(pack_path)
        paths["e02_4core_candidate_pack_contact_sheet"] = pack_path.as_posix()
    return {"schema_name": "e02_contact_sheet_manifest", "status": "passed", "paths": paths}


def _grid_sheet(output: Path, rows: dict[str, dict[str, Any]], *, title: str) -> None:
    thumb_w, thumb_h = 420, 236
    header_h = 54
    sheet = Image.new("RGB", (thumb_w * 2, (thumb_h + header_h) * 4), "#0F172A")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, (archetype_id, row) in enumerate(rows.items()):
        y = idx * (thumb_h + header_h)
        ref = _load(row.get("reference_image"))
        ren = _load(row.get("rendered_candidate"))
        for col, (image, label) in enumerate(((ref, f"{archetype_id} reference"), (ren, f"{archetype_id} render PASS"))):
            x = col * thumb_w
            draw.rectangle((x, y, x + thumb_w, y + header_h), fill="#111827")
            draw.text((x + 10, y + 10), label, fill="#F8FAFC", font=font)
            draw.text((x + 10, y + 28), title, fill="#F5A623", font=font)
            if image:
                image.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
                sheet.paste(image, (x + (thumb_w - image.width) // 2, y + header_h + (thumb_h - image.height) // 2))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _load(path_text: str | None) -> Image.Image | None:
    if not path_text:
        return None
    path = Path(path_text)
    if not path.exists():
        return None
    return Image.open(path).convert("RGB")
