"""Report and setup-document writers for E01X-R4 bootstrap."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_setup_docs(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    docs = {
        "README.md": _readme(),
        "model_download_policy.md": _download_policy(),
        "minimal_cpu_setup.md": _minimal_cpu(),
        "minimal_gpu_setup.md": _minimal_gpu(),
        "adapter_env_vars.md": _env_vars(),
        "troubleshooting.md": _troubleshooting(),
    }
    for name, content in docs.items():
        (output_dir / name).write_text(content, encoding="utf-8")


def write_bootstrap_report(output_root: Path, report: dict[str, Any]) -> None:
    _write_json(output_root / "e01x_r4_real_model_bootstrap_report.json", report)
    (output_root / "e01x_r4_real_model_bootstrap_report.md").write_text(bootstrap_report_markdown(report), encoding="utf-8")


def bootstrap_report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# E01X-R4 Real Model Bootstrap Report",
        "",
        f"- Previous E01X decision: `{report['previous_e01x_decision']}`",
        f"- R4 decision: `{report['r4_decision']}`",
        f"- Real proposals: `{report['real_proposal_counts']['total_real_proposal_count']}`",
        f"- Heuristic proposals: `{report['real_proposal_counts']['total_heuristic_proposal_count']}`",
        f"- Text-first lock available: `{report['text_first_lock_available']}`",
        f"- Non-text proposal model available: `{report['non_text_proposal_available']}`",
        f"- Fusion accepted objects: `{report['fusion_accepted_object_count']}`",
        f"- Exact next command: `{report['next_command']}`",
        "- Canva parity claimed: `False`",
        "",
        "## Adapters Attempted",
        "",
    ]
    lines.extend(f"- `{item}`" for item in report.get("adapters_attempted", []) or ["none"])
    lines.extend(["", "## Adapters Skipped", ""])
    lines.extend(f"- `{item}`" for item in report.get("adapters_skipped", []) or ["none"])
    lines.extend(["", "## Adapters Failed", ""])
    lines.extend(f"- `{item}`" for item in report.get("adapters_failed", []) or ["none"])
    return "\n".join(lines) + "\n"


def adapter_failure_taxonomy(results: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [{"adapter_id": result.get("adapter_id"), "status": result.get("status"), "reason": result.get("reason")} for result in results]
    return {
        "schema_name": "adapter_failure_taxonomy",
        "failures": rows,
        "summary": {
            "unavailable_count": sum(1 for row in rows if row["status"] == "unavailable"),
            "failed_runtime_count": sum(1 for row in rows if row["status"] == "failed_runtime"),
        },
        "canva_parity_claimed": False,
    }


def adapter_failure_taxonomy_markdown(report: dict[str, Any]) -> str:
    lines = ["# Adapter Failure Taxonomy", "", "| Adapter | Status | Reason |", "|---|---|---|"]
    for row in report["failures"]:
        lines.append(f"| `{row['adapter_id']}` | `{row['status']}` | `{row['reason'] or '-'}` |")
    lines.append("")
    lines.append("Canva parity claimed: `False`")
    return "\n".join(lines) + "\n"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _readme() -> str:
    return """# E01X-R4 Real Model Bootstrap

Previous E01X blocked because no real local proposal adapters produced model evidence. R4 records local package and model-path readiness, runs smoke inference only for configured local adapters, and keeps E01 blocked unless real text and non-text proposals exist.

Real model evidence means an adapter actually ran on the reference image and recorded runtime evidence, input/output hashes, package or binary evidence, and local model/engine evidence. Heuristics never unblock E01X.

Minimal viable stack: one text-region/OCR backend plus one non-text layout/object/layer/mask backend.

Set `ML_LOCAL_MODEL_PACK_MANIFEST` to a local manifest path, set `ML_ENABLE_HF_ADAPTERS=1` for ML adapters, then run `npm run magic-layer:e01x-model-bootstrap` and `npm run magic-layer:e01x-adapter-smoke`.

Rerun E01X only after R4 reports `E01X_R4_READY_FOR_E01X_REENTRY`.
"""


def _download_policy() -> str:
    return """# Model Download Policy

Default behavior does not download weights, install large packages, call external services, or require network access. `ML_ALLOW_MODEL_DOWNLOADS=1` is only a permission flag for future explicit implementations; this R4 harness records the value and still favors local files.
"""


def _minimal_cpu() -> str:
    return """# Minimal CPU Setup

Recommended practical CPU path:
- Configure a real OCR/text-region backend such as PaddleOCR, EasyOCR, or system Tesseract.
- Configure one real layout/object detector such as DocLayout/Docling or a local object detector.
- Add a mask model only after text and layout/object evidence works.
"""


def _minimal_gpu() -> str:
    return """# Minimal GPU Setup

Recommended GPU path:
- OCR/text-region backend.
- DocLayout or object-detection model.
- SAM2 or equivalent mask model.
- Optional Qwen-Image-Layered/LayerD for layer proposals.
- Optional chart/table model for semantic chart/table promotion evidence.
"""


def _env_vars() -> str:
    return """# Adapter Environment Variables

- `ML_LOCAL_MODEL_PACK_MANIFEST`: JSON manifest describing local adapters and paths.
- `ML_ENABLE_HF_ADAPTERS=1`: enable ML adapter runtime attempts.
- `ML_ALLOW_MODEL_DOWNLOADS=1`: allow downloads only where explicitly implemented and reported.
- `ML_MODEL_CACHE_DIR`: local model cache root.
- `ML_MODEL_DEVICE`: `auto`, `cpu`, `cuda`, or `mps`.
"""


def _troubleshooting() -> str:
    return """# Troubleshooting

- `E01X_R4_BLOCKED_MODEL_PACK_NOT_CONFIGURED`: enable/configure at least one real text adapter and one non-text adapter.
- `E01X_R4_BLOCKED_TEXT_FIRST_LOCK_UNAVAILABLE`: configure OCR/text-region backend first.
- `E01X_R4_BLOCKED_NO_NON_TEXT_PROPOSAL_MODEL`: add layout/object/layer/mask adapter.
- `E01X_R4_BLOCKED_ADAPTER_RUNTIME_FAILURE`: inspect `adapter_stdout_stderr.json`.
"""
