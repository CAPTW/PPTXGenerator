"""Assemble the E06.4.1 accepted candidate deck."""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from src.presentation_agent.magic_layer.e06_2_contract_compiler import render_contract_deck


SOURCE_IDS = {
    "accept_e06_2_1": "e06_2_1",
    "accept_e06_3": "e06_3",
    "accept_e06_4": "e06_4",
}


def assemble_accepted_candidate(
    manifest: dict[str, Any],
    source_decks: dict[str, Path],
    output_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    output = output_root / "accepted_candidate" / "harness_v3_e06_4_1_human_accepted_baseline_candidate.pptx"
    output.parent.mkdir(parents=True, exist_ok=True)
    selections = manifest.get("slides", [])
    if not selections or any(row["accepted_source"] == "requires_manual_patch" for row in selections):
        return ({"schema_name": "assembled_candidate_report", "status": "manual_patch_required", "candidate_path": output.as_posix()}, {"schema_name": "accepted_candidate_render_report", "status": "skipped", "rendered_slide_count": 0})
    base = source_decks["e06_2_1"]
    with tempfile.TemporaryDirectory() as tmp:
        tmp_pptx = Path(tmp) / "accepted.pptx"
        with zipfile.ZipFile(base, "r") as zin, zipfile.ZipFile(tmp_pptx, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            source_zips: dict[str, zipfile.ZipFile] = {}
            try:
                for source_id, deck in source_decks.items():
                    source_zips[source_id] = zipfile.ZipFile(deck, "r")
                selected_by_slide = {int(row["slide_number"]): SOURCE_IDS[row["accepted_source"]] for row in selections}
                for name in zin.namelist():
                    if (name.startswith("ppt/slides/slide") or name.startswith("ppt/slides/_rels/slide")) and (name.endswith(".xml") or name.endswith(".xml.rels")):
                        slide_number = _slide_number(name)
                        selected = selected_by_slide.get(slide_number, "e06_2_1")
                        source_zip = source_zips[selected]
                        if name in source_zip.namelist():
                            zout.writestr(name, source_zip.read(name))
                            continue
                    zout.writestr(name, zin.read(name))
            finally:
                for zf in source_zips.values():
                    zf.close()
        shutil.copy2(tmp_pptx, output)
    render = render_contract_deck(output, output_root, prefix="accepted")
    report = {
        "schema_name": "assembled_candidate_report",
        "status": "passed" if output.exists() and render.get("rendered_slide_count") == 16 else "failed",
        "candidate_path": output.as_posix(),
        "slide_count": len(selections),
        "assembled_from_sources": manifest.get("accepted_source_counts", {}),
        "non_canonical": True,
        "canonical_promotion": False,
    }
    return report, render


def write_accepted_candidate_manifest(output_root: Path, assembled: dict[str, Any], best_manifest: dict[str, Any]) -> dict[str, Any]:
    manifest = {
        "schema_name": "human_accepted_candidate_manifest",
        "status": assembled.get("status"),
        "candidate_path": assembled.get("candidate_path"),
        "accepted_source_counts": best_manifest.get("accepted_source_counts", {}),
        "slides": best_manifest.get("slides", []),
        "non_canonical": True,
        "broad_canva_parity_claimed": False,
    }
    from src.presentation_agent.magic_layer.e03_16_orchestrator import write_json, write_md

    write_json(output_root / "accepted_candidate" / "human_accepted_candidate_manifest.json", manifest)
    write_md(
        output_root / "accepted_candidate" / "human_accepted_candidate_readme.md",
        "# E06.4.1 Human Accepted Candidate\n\nAssembled from slide-level accepted sources. This is non-canonical and does not promote protected artifacts.",
    )
    return manifest


def _slide_number(name: str) -> int:
    if name.endswith(".rels"):
        stem = Path(name).stem
    else:
        stem = Path(name).stem
    return int(stem.replace("slide", "").replace(".xml", ""))
