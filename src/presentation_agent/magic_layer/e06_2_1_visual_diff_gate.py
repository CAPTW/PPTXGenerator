"""Visual diff gates for E06.2.1 style/content fidelity."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat


def build_contract_first_recompile_v2_render_diff_report(baseline_dir: Path, v2_dir: Path, *, prefix: str = "v2") -> dict[str, Any]:
    rows = []
    failures = 0
    for idx in range(1, 17):
        baseline = baseline_dir / f"slide-{idx:03d}.png"
        candidate = v2_dir / f"{prefix}-{idx:03d}.png"
        if not baseline.exists() or not candidate.exists():
            rows.append({"slide_number": idx, "status": "missing_render", "mean_delta": None})
            failures += 1
            continue
        before = Image.open(baseline).convert("RGB").resize((640, 360))
        after = Image.open(candidate).convert("RGB").resize((640, 360))
        stat = ImageStat.Stat(ImageChops.difference(before, after))
        mean_delta = sum(stat.mean) / 3
        status = "passed" if mean_delta <= 12.0 else "failed"
        if status != "passed":
            failures += 1
        rows.append({"slide_number": idx, "status": status, "mean_delta": round(mean_delta, 3)})
    return {
        "schema_name": "contract_first_recompile_v2_render_diff_report",
        "status": "passed" if failures == 0 else "failed",
        "rendered_slide_count": sum(1 for row in rows if row["status"] != "missing_render"),
        "render_diff_verdict": "passed" if failures == 0 else "failed",
        "render_diff_failure_count": failures,
        "average_mean_pixel_delta": round(sum(row["mean_delta"] or 0 for row in rows) / max(1, len(rows)), 3),
        "rows": rows,
    }


def build_visual_delta_contact_sheet(output: Path, baseline_dir: Path, e06_2_dir: Path, v2_dir: Path) -> None:
    sheet = Image.new("RGB", (960, 16 * 150 + 44), "#071018")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((18, 16), "E06 baseline vs E06.2 vs E06.2.1", fill="#F8FAFC", font=font)
    for idx in range(1, 17):
        y = 44 + (idx - 1) * 150
        triples = [
            (baseline_dir / f"slide-{idx:03d}.png", "baseline"),
            (e06_2_dir / f"recompiled-{idx:03d}.png", "E06.2"),
            (v2_dir / f"v2-{idx:03d}.png", "E06.2.1"),
        ]
        for col, (path, label) in enumerate(triples):
            x = col * 320 + 8
            draw.text((x, y + 4), f"{idx:02d} {label}", fill="#F2A900" if col < 2 else "#28D7E8", font=font)
            _paste(sheet, path, x, y + 22, 304, 120)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _paste(sheet: Image.Image, path: Path, x: int, y: int, width: int, height: int) -> None:
    if not path.exists():
        return
    image = Image.open(path).convert("RGB")
    image.thumbnail((width, height), Image.Resampling.LANCZOS)
    sheet.paste(image, (x + (width - image.width) // 2, y + (height - image.height) // 2))
