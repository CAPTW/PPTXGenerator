"""HTML workbench update for E06.2 contract-first compile diffs."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


def build_e06_2_html_workbench(
    output_root: Path,
    e06_1_html_root: Path,
    contract: dict[str, Any],
    recompile_diff: dict[str, Any],
    mutation_diff: dict[str, Any],
) -> dict[str, Any]:
    root = output_root / "html_workbench"
    root.mkdir(parents=True, exist_ok=True)
    for name in ("index.html", "styles.css", "README.md"):
        source = e06_1_html_root / name
        if source.exists():
            shutil.copy2(source, root / name)
    if not (root / "index.html").exists():
        (root / "index.html").write_text("<!doctype html><title>E06.2 Contract Workbench</title><script src='layout_contract_viewer.js'></script>", encoding="utf-8")
    if not (root / "styles.css").exists():
        (root / "styles.css").write_text("body{font-family:system-ui;background:#071018;color:#e6edf3}", encoding="utf-8")
    (root / "layout_contract_16_slides.json").write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / "contract_recompile_diff.json").write_text(json.dumps(recompile_diff, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / "mutation_smoke_test_diff.json").write_text(json.dumps(mutation_diff, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    readme = root / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8") if readme.exists() else "# E06.2 Contract Workbench\n",
        encoding="utf-8",
    )
    with readme.open("a", encoding="utf-8") as fh:
        fh.write("\n## E06.2\n\nIncludes `contract_recompile_diff.json` and `mutation_smoke_test_diff.json`.\n")
    return {
        "schema_name": "e06_2_html_workbench_manifest",
        "status": "passed" if (root / "index.html").exists() and (root / "contract_recompile_diff.json").exists() else "failed",
        "html_workbench_path": (root / "index.html").as_posix(),
        "root": root.as_posix(),
    }
