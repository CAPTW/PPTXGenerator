"""Contact sheets for E03.2.1 icon library expansion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cairosvg
from PIL import Image, ImageDraw, ImageFont


CONTACT_NAMES = (
    "observed_icon_inventory_contact_sheet.png",
    "existing_library_matches_contact_sheet.png",
    "missing_icon_backlog_contact_sheet.png",
    "generated_svg_contact_sheet.png",
    "observed_crop_vs_generated_svg_contact_sheet.png",
    "curated_v2_vs_v3_contact_sheet.png",
    "icon_role_coverage_contact_sheet.png",
)


def build_e03_2_1_contact_sheets(
    output_root: Path,
    *,
    inventory: dict[str, Any],
    match_report: dict[str, Any],
    backlog: dict[str, Any],
    quality_report: dict[str, Any],
    coverage: dict[str, Any],
    v2_root: Path,
    v3_root: Path,
) -> dict[str, Any]:
    render_dir = output_root / "renders"
    render_dir.mkdir(parents=True, exist_ok=True)
    _crop_grid(render_dir / "observed_icon_inventory_contact_sheet.png", inventory["icons"], "Observed semantic icon inventory")
    _match_grid(render_dir / "existing_library_matches_contact_sheet.png", match_report["decisions"])
    _crop_grid(render_dir / "missing_icon_backlog_contact_sheet.png", _backlog_as_icons(backlog["items"]), "Missing icon backlog")
    _svg_grid(render_dir / "generated_svg_contact_sheet.png", quality_report["icons"], "Generated SVGs")
    _crop_svg_grid(render_dir / "observed_crop_vs_generated_svg_contact_sheet.png", quality_report["icons"])
    _v2_v3_grid(render_dir / "curated_v2_vs_v3_contact_sheet.png", coverage["roles"], v2_root, v3_root)
    _coverage_grid(render_dir / "icon_role_coverage_contact_sheet.png", coverage["roles"])
    return {
        "schema_name": "e03_2_1_contact_sheet_manifest",
        "status": "passed" if all((render_dir / name).exists() for name in CONTACT_NAMES) else "failed",
        "paths": {name.removesuffix(".png"): (render_dir / name).as_posix() for name in CONTACT_NAMES},
    }


def _crop_grid(output: Path, icons: list[dict[str, Any]], title: str) -> None:
    thumb = 92
    header = 34
    cols = 12
    rows = max(1, (min(len(icons), 96) + cols - 1) // cols)
    sheet = Image.new("RGB", (cols * thumb, rows * (thumb + header)), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, icon in enumerate(icons[:96]):
        x = (idx % cols) * thumb
        y = (idx // cols) * (thumb + header)
        draw.rectangle((x, y, x + thumb, y + header), fill="#111827")
        draw.text((x + 3, y + 3), icon.get("likely_role", "")[:14], fill="#F5A623", font=font)
        draw.text((x + 3, y + 17), icon.get("priority", "")[:10], fill="#9EC4C8", font=font)
        image = _load(Path(icon.get("normalized_crop_path") or icon.get("source_crop_path", "")))
        if image:
            image.thumbnail((thumb, thumb), Image.Resampling.LANCZOS)
            sheet.paste(image, (x + (thumb - image.width) // 2, y + header + (thumb - image.height) // 2))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _match_grid(output: Path, decisions: list[dict[str, Any]]) -> None:
    thumb_w, thumb_h = 210, 112
    cols = 4
    rows = max(1, (min(len(decisions), 48) + cols - 1) // cols)
    sheet = Image.new("RGB", (cols * thumb_w, rows * thumb_h), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, decision in enumerate(decisions[:48]):
        x = (idx % cols) * thumb_w
        y = (idx // cols) * thumb_h
        draw.rectangle((x, y, x + thumb_w, y + thumb_h), fill="#111827")
        draw.text((x + 6, y + 6), decision["likely_role"][:24], fill="#F8FAFC", font=font)
        draw.text((x + 6, y + 22), decision["classification"][:28], fill="#F5A623", font=font)
        image = _load(Path(decision["normalized_crop_path"]))
        if image:
            image.thumbnail((70, 70), Image.Resampling.LANCZOS)
            sheet.paste(image, (x + 6, y + 38))
        draw.text((x + 86, y + 48), f"score {decision['shape_similarity_proxy']}", fill="#9EC4C8", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _svg_grid(output: Path, icons: list[dict[str, Any]], title: str) -> None:
    thumb = 112
    cols = 8
    rows = max(1, (max(1, len(icons)) + cols - 1) // cols)
    sheet = Image.new("RGB", (cols * thumb, rows * thumb), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, icon in enumerate(icons):
        x = (idx % cols) * thumb
        y = (idx // cols) * thumb
        draw.rectangle((x, y, x + thumb, y + thumb), fill="#111827")
        draw.text((x + 4, y + 4), Path(icon["svg_path"]).stem[:15], fill="#F5A623", font=font)
        image = _load(Path(icon["preview_path"]))
        if image:
            image.thumbnail((78, 78), Image.Resampling.LANCZOS)
            sheet.paste(image, (x + (thumb - image.width) // 2, y + 28))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _crop_svg_grid(output: Path, icons: list[dict[str, Any]]) -> None:
    cell_w, cell_h = 190, 104
    cols = 4
    rows = max(1, (max(1, len(icons)) + cols - 1) // cols)
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, icon in enumerate(icons):
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h
        draw.rectangle((x, y, x + cell_w, y + cell_h), fill="#111827")
        draw.text((x + 5, y + 4), icon["likely_role"][:20], fill="#F5A623", font=font)
        crop = _load(Path(icon["source_crop_path"]))
        preview = _load(Path(icon["preview_path"]))
        for col, image in enumerate((crop, preview)):
            if image:
                image.thumbnail((76, 76), Image.Resampling.LANCZOS)
                sheet.paste(image, (x + 8 + col * 88, y + 24))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _v2_v3_grid(output: Path, roles: list[dict[str, Any]], v2_root: Path, v3_root: Path) -> None:
    rows = roles[:48]
    cell_w, cell_h = 180, 96
    cols = 4
    sheet = Image.new("RGB", (cols * cell_w, max(1, ((len(rows) + cols - 1) // cols)) * cell_h), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, row in enumerate(rows):
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h
        draw.rectangle((x, y, x + cell_w, y + cell_h), fill="#111827")
        draw.text((x + 5, y + 4), row["role"][:22], fill="#F8FAFC", font=font)
        _paste_svg(sheet, v2_root / f"{row['role']}.svg", x + 12, y + 28)
        _paste_svg(sheet, v3_root / f"{row['role']}.svg", x + 96, y + 28)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _coverage_grid(output: Path, roles: list[dict[str, Any]]) -> None:
    cell_w, cell_h = 220, 42
    rows = len(roles)
    sheet = Image.new("RGB", (cell_w * 2, max(1, rows) * cell_h), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, role in enumerate(roles):
        x = (idx % 2) * cell_w
        y = (idx // 2) * cell_h
        color = "#22C55E" if role["covered"] else "#EF4444"
        draw.rectangle((x, y, x + cell_w, y + cell_h), fill="#111827")
        draw.text((x + 6, y + 6), role["role"][:28], fill="#F8FAFC", font=font)
        draw.text((x + 6, y + 22), f"{role['priority']} {role['source_kind']}"[:34], fill=color, font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _backlog_as_icons(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "likely_role": item["likely_role"],
            "priority": item["priority"],
            "source_crop_path": item["source_crop_path"],
            "normalized_crop_path": item["source_crop_path"],
        }
        for item in items
    ]


def _paste_svg(sheet: Image.Image, svg_path: Path, x: int, y: int) -> None:
    if not svg_path.exists():
        return
    temp = svg_path.with_suffix(".tmp.png")
    cairosvg.svg2png(url=svg_path.as_posix(), write_to=temp.as_posix(), output_width=48, output_height=48)
    image = Image.open(temp).convert("RGBA")
    sheet.paste(Image.new("RGB", image.size, "#F8FAFC"), (x, y))
    sheet.paste(image, (x, y), image)
    temp.unlink(missing_ok=True)


def _load(path: Path) -> Image.Image | None:
    if not path.exists():
        return None
    return Image.open(path).convert("RGB")
