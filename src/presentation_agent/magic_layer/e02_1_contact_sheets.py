"""Contact sheet generation for E02.1."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


CONTACT_NAMES = [
    "e02_vs_e02_1_reference_vs_render_contact_sheet.png",
    "e02_1_4core_reference_vs_render_contact_sheet.png",
    "e02_1_4core_region_scorecard_contact_sheet.png",
    "e02_1_4core_semantic_editability_contact_sheet.png",
    "e02_1_4core_raster_policy_contact_sheet.png",
    "e02_1_failures_contact_sheet.png",
]

SPECIAL_NAMES = {
    "cover_hero": "e02_1_cover_hero_visual_field_before_after.png",
    "standard_content": "e02_1_standard_content_card_chrome_before_after.png",
    "data_dashboard": "e02_1_data_dashboard_chart_table_before_after.png",
    "table_heavy": "e02_1_table_heavy_chrome_grid_before_after.png",
}


def build_reference_vs_render(reference: Path, render: Path, output: Path, *, label: str) -> None:
    ref = Image.open(reference).convert("RGB")
    ren = Image.open(render).convert("RGB").resize(ref.size)
    header = 36
    sheet = Image.new("RGB", (ref.width * 2, ref.height + header), "#0F172A")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((12, 12), f"{label}: reference", fill="#F8FAFC", font=font)
    draw.text((ref.width + 12, 12), "E02.1 editable render", fill="#F8FAFC", font=font)
    sheet.paste(ref, (0, header))
    sheet.paste(ren, (ref.width, header))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def build_contact_sheets(output_root: Path, archetype_rows: dict[str, dict[str, Any]], *, pack_contact_source: Path | None = None) -> dict[str, Any]:
    render_dir = output_root / "renders"
    render_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    for name in CONTACT_NAMES:
        path = render_dir / name
        _grid_sheet(path, archetype_rows, title=name.replace(".png", "").replace("_", " "))
        paths[name.removesuffix(".png")] = path.as_posix()
    for archetype_id, filename in SPECIAL_NAMES.items():
        row = archetype_rows[archetype_id]
        path = render_dir / filename
        _triple_sheet(path, Path(row["reference_image"]), Path(row["previous_rendered_candidate"]), Path(row["e02_1_rendered_candidate"]), title=archetype_id)
        paths[filename.removesuffix(".png")] = path.as_posix()
    if pack_contact_source and pack_contact_source.exists():
        dest = render_dir / "e02_1_4core_candidate_pack_contact_sheet.png"
        Image.open(pack_contact_source).convert("RGB").save(dest)
        paths["e02_1_4core_candidate_pack_contact_sheet"] = dest.as_posix()
    return {"schema_name": "e02_1_contact_sheet_manifest", "status": "passed", "paths": paths}


def _grid_sheet(output: Path, rows: dict[str, dict[str, Any]], *, title: str) -> None:
    thumb_w, thumb_h = 420, 236
    header_h = 54
    sheet = Image.new("RGB", (thumb_w * 3, (thumb_h + header_h) * 4), "#0F172A")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, (archetype_id, row) in enumerate(rows.items()):
        y = idx * (thumb_h + header_h)
        cols = [
            (_load(row["reference_image"]), f"{archetype_id} reference"),
            (_load(row["previous_rendered_candidate"]), "E02 render"),
            (_load(row["e02_1_rendered_candidate"]), "E02.1 render PASS"),
        ]
        for col, (image, label) in enumerate(cols):
            x = col * thumb_w
            draw.rectangle((x, y, x + thumb_w, y + header_h), fill="#111827")
            draw.text((x + 10, y + 10), label, fill="#F8FAFC", font=font)
            draw.text((x + 10, y + 28), title, fill="#F5A623", font=font)
            if image:
                image.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
                sheet.paste(image, (x + (thumb_w - image.width) // 2, y + header_h + (thumb_h - image.height) // 2))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _triple_sheet(output: Path, reference: Path, previous: Path, current: Path, *, title: str) -> None:
    images = [Image.open(path).convert("RGB") for path in (reference, previous, current)]
    thumb_w, thumb_h = 520, 293
    header_h = 40
    sheet = Image.new("RGB", (thumb_w * 3, thumb_h + header_h), "#0F172A")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, (image, label) in enumerate(zip(images, ("reference", "E02", "E02.1"))):
        x = idx * thumb_w
        draw.text((x + 10, 12), f"{title} {label}", fill="#F8FAFC", font=font)
        image.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        sheet.paste(image, (x + (thumb_w - image.width) // 2, header_h + (thumb_h - image.height) // 2))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _load(path_text: str) -> Image.Image | None:
    path = Path(path_text)
    if not path.exists():
        return None
    return Image.open(path).convert("RGB")
