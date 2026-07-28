"""Contact sheet rendering for E03.4 icon foundation outputs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

try:
    import cairosvg
except Exception:  # pragma: no cover
    cairosvg = None


CONTACT_SHEET_NAMES = (
    "p0_p1_icon_role_taxonomy_contact_sheet.png",
    "v6_audit_contact_sheet.png",
    "contaminated_crop_rejection_contact_sheet.png",
    "generic_placeholder_rejection_contact_sheet.png",
    "manual_svg_backlog_contact_sheet.png",
    "authored_svg_v7_contact_sheet.png",
    "curated_v6_vs_v7_contact_sheet.png",
    "icon_distinctiveness_contact_sheet.png",
    "small_size_legibility_contact_sheet.png",
    "icon_regression_fixture_contact_sheet.png",
)


def build_e03_4_contact_sheets(
    output_root: Path,
    *,
    taxonomy: dict[str, Any],
    audit: dict[str, Any],
    contaminated: dict[str, Any],
    placeholders: dict[str, Any],
    backlog: dict[str, Any],
    authored_quality: dict[str, Any],
    curated_manifest: dict[str, Any],
    distinctiveness: dict[str, Any],
    legibility: dict[str, Any],
    fixture: dict[str, Any],
    v6_root: Path,
) -> dict[str, Any]:
    render_dir = output_root / "renders"
    render_dir.mkdir(parents=True, exist_ok=True)
    _role_sheet(render_dir / "p0_p1_icon_role_taxonomy_contact_sheet.png", taxonomy.get("roles", []), "P0/P1 Icon Role Taxonomy")
    _audit_sheet(render_dir / "v6_audit_contact_sheet.png", audit.get("role_audits", []), "Curated v6 Audit")
    _text_sheet(render_dir / "contaminated_crop_rejection_contact_sheet.png", "Contaminated Crop Rejection", _summary_lines(contaminated))
    _text_sheet(render_dir / "generic_placeholder_rejection_contact_sheet.png", "Generic Placeholder Rejection", _summary_lines(placeholders))
    _role_sheet(render_dir / "manual_svg_backlog_contact_sheet.png", backlog.get("backlog_items", []), "Manual SVG Backlog")
    _svg_sheet(render_dir / "authored_svg_v7_contact_sheet.png", authored_quality.get("passed_icons", []), "Authored SVG v7")
    _v6_v7_sheet(render_dir / "curated_v6_vs_v7_contact_sheet.png", curated_manifest.get("roles", []), v6_root)
    _text_sheet(render_dir / "icon_distinctiveness_contact_sheet.png", "Icon Distinctiveness", _summary_lines(distinctiveness))
    _text_sheet(render_dir / "small_size_legibility_contact_sheet.png", "Small Size Legibility", _summary_lines(legibility))
    _regression_sheet(render_dir / "icon_regression_fixture_contact_sheet.png", fixture)
    return {
        "schema_name": "e03_4_contact_sheet_manifest",
        "status": "passed" if all((render_dir / name).exists() for name in CONTACT_SHEET_NAMES) else "failed",
        "paths": {name.removesuffix(".png"): (render_dir / name).as_posix() for name in CONTACT_SHEET_NAMES},
    }


def _summary_lines(report: dict[str, Any]) -> list[str]:
    lines = []
    for key, value in report.items():
        if isinstance(value, (str, int, float, bool)):
            lines.append(f"{key}: {value}")
    return lines[:18]


def _text_sheet(output: Path, title: str, rows: list[str]) -> None:
    sheet = Image.new("RGB", (1100, 440), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((24, 24), title, fill="#F8FAFC", font=font)
    y = 64
    for row in rows:
        draw.text((24, y), row[:150], fill="#F5A623", font=font)
        y += 24
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _role_sheet(output: Path, rows: list[dict[str, Any]], title: str) -> None:
    cols = 4
    cell_w, cell_h = 280, 72
    sheet = Image.new("RGB", (cols * cell_w, max(1, ((len(rows) + cols - 1) // cols)) * cell_h), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, row in enumerate(rows[:96]):
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h
        draw.rectangle((x, y, x + cell_w, y + cell_h), fill="#111827", outline="#334155")
        role = row.get("role_id") or row.get("role") or ""
        draw.text((x + 8, y + 8), str(role)[:32], fill="#F8FAFC", font=font)
        draw.text((x + 8, y + 28), str(row.get("priority", ""))[:34], fill="#F5A623", font=font)
        draw.text((x + 8, y + 47), str(row.get("family", row.get("status", "")))[:34], fill="#9EC4C8", font=font)
    draw.text((8, 2), title[:80], fill="#F8FAFC", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _audit_sheet(output: Path, rows: list[dict[str, Any]], title: str) -> None:
    cols = 4
    cell_w, cell_h = 260, 104
    sheet = Image.new("RGB", (cols * cell_w, max(1, ((len(rows) + cols - 1) // cols)) * cell_h), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, row in enumerate(rows[:96]):
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h
        fill = "#1F2937" if row.get("status") == "accepted" else "#3B1212"
        draw.rectangle((x, y, x + cell_w, y + cell_h), fill=fill, outline="#334155")
        draw.text((x + 8, y + 8), str(row.get("role_id", ""))[:28], fill="#F8FAFC", font=font)
        draw.text((x + 8, y + 26), str(row.get("status", ""))[:24], fill="#F5A623", font=font)
        _paste_svg(sheet, Path(row.get("svg_path") or ""), x + 190, y + 42)
    draw.text((8, 2), title[:80], fill="#F8FAFC", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _svg_sheet(output: Path, rows: list[dict[str, Any]], title: str) -> None:
    cols = 5
    cell_w, cell_h = 210, 96
    sheet = Image.new("RGB", (cols * cell_w, max(1, ((len(rows) + cols - 1) // cols)) * cell_h), "#F8FAFC")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, row in enumerate(rows[:96]):
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h
        draw.rectangle((x, y, x + cell_w, y + cell_h), fill="#FFFFFF", outline="#CBD5E1")
        draw.text((x + 8, y + 8), str(row.get("role_id", row.get("role", "")))[:28], fill="#0F172A", font=font)
        _paste_svg(sheet, Path(row.get("svg_path") or ""), x + 78, y + 38)
    draw.text((8, 2), title[:80], fill="#0F172A", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _v6_v7_sheet(output: Path, roles: list[dict[str, Any]], v6_root: Path) -> None:
    cols = 4
    cell_w, cell_h = 260, 104
    sheet = Image.new("RGB", (cols * cell_w, max(1, ((len(roles) + cols - 1) // cols)) * cell_h), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, row in enumerate(roles[:96]):
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h
        role = row["role_id"]
        draw.rectangle((x, y, x + cell_w, y + cell_h), fill="#111827", outline="#334155")
        draw.text((x + 8, y + 8), role[:28], fill="#F8FAFC", font=font)
        _paste_svg(sheet, v6_root / f"{role}.svg", x + 70, y + 42)
        _paste_svg(sheet, Path(row["svg_path"]), x + 158, y + 42)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _regression_sheet(output: Path, fixture: dict[str, Any]) -> None:
    source = Path(fixture.get("fixture_render_path") or "")
    if source.exists():
        image = Image.open(source).convert("RGB")
        image.thumbnail((1280, 720), Image.Resampling.LANCZOS)
        image.save(output)
        return
    source = Path(fixture.get("fixture_preview_path") or "")
    if source.exists():
        image = Image.open(source).convert("RGB")
        image.thumbnail((1280, 720), Image.Resampling.LANCZOS)
        image.save(output)
        return
    _text_sheet(output, "Icon Regression Fixture", _summary_lines(fixture))


def _paste_svg(sheet: Image.Image, svg_path: Path, x: int, y: int) -> None:
    if cairosvg is None or not svg_path.exists():
        return
    temp = svg_path.with_suffix(".e03_4_contact_tmp.png")
    try:
        cairosvg.svg2png(url=svg_path.as_posix(), write_to=temp.as_posix(), output_width=44, output_height=44)
        image = Image.open(temp).convert("RGBA")
        sheet.paste(Image.new("RGB", image.size, "#F8FAFC"), (x, y))
        sheet.paste(image, (x, y), image)
    finally:
        temp.unlink(missing_ok=True)
