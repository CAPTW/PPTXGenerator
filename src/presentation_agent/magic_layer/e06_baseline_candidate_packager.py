"""Non-canonical baseline candidate packager for E06."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def package_e06_baseline_candidate(source_deck: Path, output_root: Path, review_report: dict[str, Any] | None = None) -> dict[str, Any]:
    package_root = output_root / "baseline_candidate"
    package_root.mkdir(parents=True, exist_ok=True)
    target = package_root / "harness_v3_e06_source_bound_magic_layer_baseline_candidate.pptx"
    shutil.copy2(source_deck, target)
    manifest = {
        "schema_name": "baseline_candidate_manifest",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "created" if target.exists() else "failed",
        "non_canonical": True,
        "source_deck_path": source_deck.as_posix(),
        "baseline_candidate_deck_path": target.as_posix(),
        "canonical_promotion": False,
        "protected_artifacts_modified": False,
        "review_decision": (review_report or {}).get("decision"),
    }
    readme = "\n".join(
        [
            "# E06 Baseline Candidate",
            "",
            "This package is non-canonical.",
            "It is a copy of the E04.2 source-bound Magic Layer+ deck for baseline promotion review.",
            "It does not overwrite or promote protected canonical artifacts.",
            "",
        ]
    )
    (package_root / "baseline_candidate_manifest.json").write_text(_json_dumps(manifest), encoding="utf-8")
    (package_root / "baseline_candidate_readme.md").write_text(readme, encoding="utf-8")
    return manifest


def _json_dumps(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, indent=2, sort_keys=True) + "\n"

