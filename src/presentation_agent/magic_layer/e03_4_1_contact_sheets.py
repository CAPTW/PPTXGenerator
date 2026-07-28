"""Contact sheets for E03.4.1 SVG PowerPoint renderability patch."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

try:
    import cairosvg
except Exception:  # pragma: no cover
    cairosvg = None


CONTACT_NAMES = (
    "e03_4_fixture_before_after_contact_sheet.png",
    "v7_vs_v7_1_icon_library_contact_sheet.png",
    "v7_1_light_dark_icon_contact_sheet.png",
    "v7_1_16_24_32_size_contact_sheet.png",
    "v7_1_cell_visibility_overlay_contact_sheet.png",
    "v7_1_failed_icons_contact_sheet.png",
)


def build_e03_4_1_contact_sheets(
    output_root: Path,
    *,
    previous_fixture_render: Path,
    curated_v7_manifest: dict[str, Any],
    curated_v7_1_manifest: dict[str, Any],
    themed_manifest: dict[str, Any],
    fixture_report: dict[str, Any],
    cell_visibility: dict[str, Any],
) -> dict[str, Any]:
    render_dir = output_root / "renders"
    render_dir.mkdir(parents=True, exist_ok=True)
    _before_after_sheet(
        render_dir / "e03_4_fixture_before_after_contact_sheet.png",
        previous_fixture_render,
        Path(fixture_report.get("contact_sheet_path") or ""),
    )
    _v7_vs_v7_1_sheet(render_dir / "v7_vs_v7_1_icon_library_contact_sheet.png", curated_v7_manifest, curated_v7_1_manifest)
    _light_dark_sheet(render_dir / "v7_1_light_dark_icon_contact_sheet.png", themed_manifest)
    _copy_or_text(
        Path(fixture_report.get("contact_sheet_path") or ""),
        render_dir / "v7_1_16_24_32_size_contact_sheet.png",
        "v7.1 fixture render contact sheet missing",
    )
    _copy_or_text(
        output_root / "qa" / "v7_1_cell_visibility_overlay_contact_sheet.png",
        render_dir / "v7_1_cell_visibility_overlay_contact_sheet.png",
        "cell visibility overlay unavailable",
    )
    _failed_icons_sheet(render_dir / "v7_1_failed_icons_contact_sheet.png", cell_visibility)
    return {
        "schema_name": "e03_4_1_contact_sheet_manifest",
        "status": "passed" if all((render_dir / name).exists() for name in CONTACT_NAMES) else "failed",
        "paths": {name.removesuffix(".png"): (render_dir / name).as_posix() for name in CONTACT_NAMES},
    }


def _before_after_sheet(output: Path, before: Path, after: Path) -> None:
    sheet = Image.new("RGB", (1280, 420), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((24, 16), "E03.4 before", fill="#F8FAFC", font=font)
    draw.text((660, 16), "E03.4.1 after", fill="#F8FAFC", font=font)
    _paste_image(sheet, before, 24, 48, 590, 330)
    _paste_image(sheet, after, 660, 48, 590, 330)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _v7_vs_v7_1_sheet(output: Path, v7: dict[str, Any], v7_1: dict[str, Any]) -> None:
    roles = v7_1.get("roles", [])[:66]
    v7_by_role = {row["role_id"]: row for row in v7.get("roles", [])}
    cols = 4
    cell_w, cell_h = 270, 94
    sheet = Image.new("RGB", (cols * cell_w, max(1, ((len(roles) + cols - 1) // cols)) * cell_h), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, row in enumerate(roles):
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h
        role = row["role_id"]
        draw.rectangle((x, y, x + cell_w, y + cell_h), fill="#111827", outline="#334155")
        draw.text((x + 8, y + 8), role[:26], fill="#F8FAFC", font=font)
        _paste_svg(sheet, Path(v7_by_role.get(role, {}).get("svg_path") or ""), x + 92, y + 36)
        _paste_svg(sheet, Path(row["svg_path"]), x + 174, y + 36)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _light_dark_sheet(output: Path, themed: dict[str, Any]) -> None:
    rows = list(themed.get("variants_by_role", {}).items())[:66]
    cols = 4
    cell_w, cell_h = 250, 94
    sheet = Image.new("RGB", (cols * cell_w, max(1, ((len(rows) + cols - 1) // cols)) * cell_h), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, (role, variants) in enumerate(rows):
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h
        draw.rectangle((x, y, x + cell_w // 2, y + cell_h), fill="#FFFFFF", outline="#CBD5E1")
        draw.rectangle((x + cell_w // 2, y, x + cell_w, y + cell_h), fill="#071018", outline="#334155")
        draw.text((x + 6, y + 8), role[:22], fill="#0F172A", font=font)
        draw.text((x + cell_w // 2 + 6, y + 8), role[:22], fill="#F8FAFC", font=font)
        _paste_svg(sheet, Path(variants["light"]), x + 48, y + 38)
        _paste_svg(sheet, Path(variants["dark"]), x + cell_w // 2 + 48, y + 38)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _failed_icons_sheet(output: Path, cell_visibility: dict[str, Any]) -> None:
    failed = [row for row in cell_visibility.get("rows", []) if not row.get("visible")]
    if not failed:
        _text_sheet(output, "No failed icon cells", [f"cell_count: {cell_visibility.get('cell_count')}", "blank_icon_cell_count: 0"])
        return
    _text_sheet(output, "Failed icon cells", [f"{row.get('role_id')} {row.get('size_px')} {row.get('background')} {row.get('failure')}" for row in failed[:30]])


def _copy_or_text(source: Path, output: Path, message: str) -> None:
    if source.exists():
        image = Image.open(source).convert("RGB")
        image.save(output)
    else:
        _text_sheet(output, "Missing Source", [message])


def _text_sheet(output: Path, title: str, rows: list[str]) -> None:
    sheet = Image.new("RGB", (980, 360), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((24, 24), title, fill="#F8FAFC", font=font)
    y = 64
    for row in rows:
        draw.text((24, y), row[:140], fill="#F5A623", font=font)
        y += 24
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _paste_image(sheet: Image.Image, path: Path, x: int, y: int, max_w: int, max_h: int) -> None:
    if not path.exists():
        return
    image = Image.open(path).convert("RGB")
    image.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
    sheet.paste(image, (x, y))


def _paste_svg(sheet: Image.Image, svg_path: Path, x: int, y: int) -> None:
    if cairosvg is None or not svg_path.exists():
        return
    temp = svg_path.with_suffix(".e03_4_1_tmp.png")
    try:
        cairosvg.svg2png(url=svg_path.as_posix(), write_to=temp.as_posix(), output_width=42, output_height=42)
        image = Image.open(temp).convert("RGBA")
        sheet.paste(image, (x, y), image)
    finally:
        temp.unlink(missing_ok=True)
