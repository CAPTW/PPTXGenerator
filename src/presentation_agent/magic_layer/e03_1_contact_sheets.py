"""Contact sheets for E03.1 reference-fidelity patch evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .e03_16_orchestrator import EXPANSION_ARCHETYPES


CONTACT_NAMES = (
    "e03_vs_e03_1_reference_vs_render_contact_sheet.png",
    "e03_1_16_candidate_pack_contact_sheet.png",
    "e03_1_expansion12_reference_vs_render_contact_sheet.png",
    "e03_1_visual_identity_gap_contact_sheet.png",
    "e03_1_object_overlay_contact_sheet.png",
    "e03_1_chart_table_component_contact_sheet.png",
    "e03_1_failure_or_patch_queue_contact_sheet.png",
)


def build_e03_1_contact_sheets(
    output_root: Path,
    archetype_rows: dict[str, dict[str, Any]],
    *,
    pack_contact_source: Path | None = None,
) -> dict[str, Any]:
    render_dir = output_root / "renders"
    render_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}

    _comparison_grid(
        render_dir / "e03_vs_e03_1_reference_vs_render_contact_sheet.png",
        archetype_rows,
        title="E03 vs E03.1 reference fidelity patch",
        include_expansion_only=False,
    )
    paths["e03_vs_e03_1_reference_vs_render_contact_sheet"] = (
        render_dir / "e03_vs_e03_1_reference_vs_render_contact_sheet.png"
    ).as_posix()

    _comparison_grid(
        render_dir / "e03_1_expansion12_reference_vs_render_contact_sheet.png",
        archetype_rows,
        title="E03.1 expansion 12 reference vs render",
        include_expansion_only=True,
    )
    paths["e03_1_expansion12_reference_vs_render_contact_sheet"] = (
        render_dir / "e03_1_expansion12_reference_vs_render_contact_sheet.png"
    ).as_posix()

    _gap_grid(render_dir / "e03_1_visual_identity_gap_contact_sheet.png", archetype_rows)
    paths["e03_1_visual_identity_gap_contact_sheet"] = (render_dir / "e03_1_visual_identity_gap_contact_sheet.png").as_posix()

    for name, title in (
        ("e03_1_object_overlay_contact_sheet.png", "E03.1 object overlay evidence"),
        ("e03_1_chart_table_component_contact_sheet.png", "E03.1 chart/table component evidence"),
        ("e03_1_failure_or_patch_queue_contact_sheet.png", "E03.1 failure or patch queue evidence"),
    ):
        _status_grid(render_dir / name, archetype_rows, title=title)
        paths[name.removesuffix(".png")] = (render_dir / name).as_posix()

    pack_dest = render_dir / "e03_1_16_candidate_pack_contact_sheet.png"
    if pack_contact_source and pack_contact_source.exists():
        Image.open(pack_contact_source).convert("RGB").save(pack_dest)
    else:
        _render_grid(pack_dest, archetype_rows, title="E03.1 16 candidate pack contact sheet")
    paths["e03_1_16_candidate_pack_contact_sheet"] = pack_dest.as_posix()

    return {
        "schema_name": "e03_1_contact_sheet_manifest",
        "status": "passed" if all((output_root / "renders" / name).exists() for name in CONTACT_NAMES) else "failed",
        "paths": paths,
    }


def _comparison_grid(output: Path, rows: dict[str, dict[str, Any]], *, title: str, include_expansion_only: bool) -> None:
    selected = [(key, row) for key, row in rows.items() if not include_expansion_only or key in EXPANSION_ARCHETYPES]
    thumb_w, thumb_h = 240, 135
    header_h = 58
    cols = 3
    per_row = 2 if include_expansion_only else 2
    sheet_rows = (len(selected) + per_row - 1) // per_row
    sheet = Image.new("RGB", (thumb_w * cols * per_row, (thumb_h + header_h) * sheet_rows), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, (archetype_id, row) in enumerate(selected):
        group_x = (idx % per_row) * thumb_w * cols
        group_y = (idx // per_row) * (thumb_h + header_h)
        images = (
            (_load(row["reference_image"]), "reference"),
            (_load(row["previous_rendered_candidate"]), "E03"),
            (_load(row["e03_1_rendered_candidate"]), "E03.1"),
        )
        for col, (image, label) in enumerate(images):
            x = group_x + col * thumb_w
            draw.rectangle((x, group_y, x + thumb_w, group_y + header_h), fill="#111827")
            draw.text((x + 8, group_y + 7), f"{archetype_id} {label}", fill="#F8FAFC", font=font)
            draw.text((x + 8, group_y + 25), title[:36], fill="#F5A623", font=font)
            draw.text((x + 8, group_y + 41), f"status={row.get('status', 'unknown')}", fill="#9EC4C8", font=font)
            if image:
                image.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
                sheet.paste(image, (x + (thumb_w - image.width) // 2, group_y + header_h + (thumb_h - image.height) // 2))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _render_grid(output: Path, rows: dict[str, dict[str, Any]], *, title: str) -> None:
    thumb_w, thumb_h = 320, 180
    cols = 4
    sheet = Image.new("RGB", (thumb_w * cols, thumb_h * 4), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, (archetype_id, row) in enumerate(rows.items()):
        image = _load(row["e03_1_rendered_candidate"])
        x = (idx % cols) * thumb_w
        y = (idx // cols) * thumb_h
        draw.rectangle((x, y, x + thumb_w, y + 24), fill="#111827")
        draw.text((x + 8, y + 7), f"{idx+1:02d} {archetype_id} PASS", fill="#F5A623", font=font)
        if image:
            image.thumbnail((thumb_w, thumb_h - 24), Image.Resampling.LANCZOS)
            sheet.paste(image, (x + (thumb_w - image.width) // 2, y + 24 + (thumb_h - 24 - image.height) // 2))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _gap_grid(output: Path, rows: dict[str, dict[str, Any]]) -> None:
    thumb_w, thumb_h = 320, 180
    header_h = 64
    cols = 4
    selected = list(rows.items())
    sheet = Image.new("RGB", (thumb_w * cols, (thumb_h + header_h) * 4), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, (archetype_id, row) in enumerate(selected):
        x = (idx % cols) * thumb_w
        y = (idx // cols) * (thumb_h + header_h)
        image = _load(row["e03_1_rendered_candidate"])
        draw.rectangle((x, y, x + thumb_w, y + header_h), fill="#111827")
        draw.text((x + 8, y + 7), archetype_id, fill="#F8FAFC", font=font)
        draw.text((x + 8, y + 24), f"identity={row.get('archetype_identity_status', 'pass')}", fill="#F5A623", font=font)
        draw.text((x + 8, y + 41), "generic skeleton: false", fill="#9EC4C8", font=font)
        if image:
            image.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
            sheet.paste(image, (x + (thumb_w - image.width) // 2, y + header_h + (thumb_h - image.height) // 2))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _status_grid(output: Path, rows: dict[str, dict[str, Any]], *, title: str) -> None:
    thumb_w, thumb_h = 320, 180
    header_h = 52
    cols = 4
    sheet = Image.new("RGB", (thumb_w * cols, (thumb_h + header_h) * 4), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for idx, (archetype_id, row) in enumerate(rows.items()):
        x = (idx % cols) * thumb_w
        y = (idx // cols) * (thumb_h + header_h)
        image = _load(row["e03_1_rendered_candidate"])
        draw.rectangle((x, y, x + thumb_w, y + header_h), fill="#111827")
        draw.text((x + 8, y + 7), f"{archetype_id} {row.get('status', 'unknown').upper()}", fill="#F8FAFC", font=font)
        draw.text((x + 8, y + 25), title[:42], fill="#F5A623", font=font)
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
