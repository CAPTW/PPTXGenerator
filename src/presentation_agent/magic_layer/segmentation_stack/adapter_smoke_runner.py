"""Run bounded local adapter smoke checks for E01X-R4."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .adapter_runtime import AdapterRuntimeConfig, build_unavailable_runtime_result, run_tesseract_smoke
from .real_model_evidence import summarize_real_model_evidence


GROUP_OUTPUTS = {
    "text_first_lock": "text_first_lock",
    "layout": "layout",
    "grounding": "grounding",
    "masks": "masks",
    "layers": "layers",
    "matting": "matting",
    "chart_table": "chart_table",
}


def run_smoke_adapters(
    *,
    reference_image: Path,
    output_root: Path,
    resolved_entries: list[dict[str, Any]],
    enable_ml_adapters: bool,
    runtime_config: AdapterRuntimeConfig | None = None,
) -> dict[str, Any]:
    smoke_root = output_root / "smoke_tests"
    smoke_root.mkdir(parents=True, exist_ok=True)
    config = runtime_config or AdapterRuntimeConfig(output_root=output_root)
    results = []
    write_paths = [str(smoke_root).replace("\\", "/")]
    for entry in resolved_entries:
        adapter_id = entry.get("adapter_id")
        group = entry.get("group", "unknown")
        adapter_dir = smoke_root / GROUP_OUTPUTS.get(group, group)
        adapter_dir.mkdir(parents=True, exist_ok=True)
        write_paths.append(str(adapter_dir).replace("\\", "/"))
        if not entry.get("enabled"):
            results.append(build_unavailable_runtime_result(adapter_id, group, "adapter_disabled", adapter_dir))
            continue
        if not entry.get("can_run"):
            results.append(build_unavailable_runtime_result(adapter_id, group, ",".join(entry.get("blockers", [])) or "adapter_cannot_run", adapter_dir))
            continue
        if group != "text_first_lock" and not enable_ml_adapters:
            results.append(build_unavailable_runtime_result(adapter_id, group, "ML_ENABLE_HF_ADAPTERS_not_set", adapter_dir))
            continue
        if adapter_id == "tesseract":
            results.append(run_tesseract_smoke(reference_image, adapter_dir, entry, config))
        else:
            results.append(build_unavailable_runtime_result(adapter_id, group, "smoke_inference_not_implemented_for_adapter", adapter_dir))

    proposals = [proposal for result in results for proposal in result.get("proposals", [])]
    evidence = summarize_real_model_evidence(proposals)
    summary = {
        "schema_name": "adapter_smoke_summary",
        "adapter_count": len(results),
        "attempted_count": sum(1 for result in results if result.get("runtime_evidence", {}).get("real_inference_ran")),
        "produced_proposal_adapter_count": sum(1 for result in results if result.get("status") == "produced_proposals"),
        "total_real_proposal_count": evidence["total_real_proposal_count"],
        "total_heuristic_proposal_count": evidence["total_heuristic_proposal_count"],
        "runtime_failure_count": sum(1 for result in results if result.get("status") == "failed_runtime"),
        "canva_parity_claimed": False,
    }
    return {
        "schema_name": "adapter_smoke_run",
        "adapter_results": results,
        "summary": summary,
        "evidence": evidence,
        "write_paths": write_paths,
        "canva_parity_claimed": False,
    }


def write_smoke_outputs(output_root: Path, smoke: dict[str, Any]) -> None:
    smoke_root = output_root / "smoke_tests"
    smoke_root.mkdir(parents=True, exist_ok=True)
    _write_json(smoke_root / "smoke_test_manifest.json", {"schema_name": "smoke_test_manifest", "adapter_results": smoke["adapter_results"], "canva_parity_claimed": False})
    _write_json(smoke_root / "adapter_smoke_summary.json", smoke["summary"])
    (smoke_root / "adapter_smoke_summary.md").write_text(adapter_smoke_summary_markdown(smoke["summary"]), encoding="utf-8")
    _write_group_outputs(smoke_root, smoke["adapter_results"])


def adapter_smoke_summary_markdown(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Adapter Smoke Summary",
            "",
            f"- Adapter count: `{summary['adapter_count']}`",
            f"- Attempted count: `{summary['attempted_count']}`",
            f"- Produced proposal adapters: `{summary['produced_proposal_adapter_count']}`",
            f"- Total real proposals: `{summary['total_real_proposal_count']}`",
            f"- Total heuristic proposals: `{summary['total_heuristic_proposal_count']}`",
            f"- Runtime failures: `{summary['runtime_failure_count']}`",
            "- Canva parity claimed: `False`",
        ]
    ) + "\n"


def _write_group_outputs(smoke_root: Path, results: list[dict[str, Any]]) -> None:
    by_group: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        by_group.setdefault(result.get("group", "unknown"), []).append(result)
    _write_text_outputs(smoke_root / "text_first_lock", by_group.get("text_first_lock", []))
    _write_family(smoke_root / "layout", "real_layout_region_proposals.json", "real_layout_adapter_report.md", "Real Layout Adapter Report", by_group.get("layout", []))
    _write_family(smoke_root / "grounding", "real_object_bbox_proposals.json", "real_grounding_adapter_report.md", "Real Grounding Adapter Report", by_group.get("grounding", []))
    _write_family(smoke_root / "masks", "real_polygon_mask_ledger.json", "real_mask_adapter_report.md", "Real Mask Adapter Report", by_group.get("masks", []))
    _write_layers(smoke_root / "layers", by_group.get("layers", []))
    _write_family(smoke_root / "matting", "real_image_field_alpha_ledger.json", "real_matting_adapter_report.md", "Real Matting Adapter Report", by_group.get("matting", []))
    _write_chart_table(smoke_root / "chart_table", by_group.get("chart_table", []))


def _write_text_outputs(root: Path, results: list[dict[str, Any]]) -> None:
    proposals = [proposal for result in results for proposal in result.get("proposals", [])]
    root.mkdir(parents=True, exist_ok=True)
    _write_json(root / "real_text_region_ledger.json", {"schema_name": "real_text_region_ledger", "status": "produced_proposals" if proposals else "unavailable", "regions": proposals, "canva_parity_claimed": False})
    zones = [
        {
            "zone_id": f"REAL_LOCK_{proposal['proposal_id']}",
            "source_region_id": proposal["proposal_id"],
            "bbox_px": proposal.get("bbox_px"),
            "bbox_norm": proposal.get("bbox_norm"),
            "must_promote_to_ppt_text": True,
            "exclude_from_visual_masks": True,
        }
        for proposal in proposals
    ]
    _write_json(root / "real_protected_text_zones.json", {"schema_name": "real_protected_text_zones", "status": "passed" if zones else "unavailable", "zones": zones, "canva_parity_claimed": False})
    (root / "real_text_first_lock_report.md").write_text(_family_md("Real Text-First Lock Report", results, len(proposals)), encoding="utf-8")
    _write_stdout_stderr(root, results)


def _write_family(root: Path, json_name: str, md_name: str, title: str, results: list[dict[str, Any]]) -> None:
    proposals = [proposal for result in results for proposal in result.get("proposals", [])]
    root.mkdir(parents=True, exist_ok=True)
    _write_json(root / json_name, {"schema_name": json_name.removesuffix(".json"), "status": "produced_proposals" if proposals else "unavailable", "proposals": proposals, "adapter_results": results, "canva_parity_claimed": False})
    (root / md_name).write_text(_family_md(title, results, len(proposals)), encoding="utf-8")
    _write_stdout_stderr(root, results)


def _write_layers(root: Path, results: list[dict[str, Any]]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    qwen = [result for result in results if result.get("adapter_id") == "qwen_image_layered"]
    layerd = [result for result in results if result.get("adapter_id") in {"layerd", "layerd_birefnet"}]
    _write_json(root / "real_qwen_rgba_layer_proposals.json", {"schema_name": "real_qwen_rgba_layer_proposals", "status": "unavailable", "proposals": [p for r in qwen for p in r.get("proposals", [])], "adapter_results": qwen, "canva_parity_claimed": False})
    _write_json(root / "real_layerd_layer_proposals.json", {"schema_name": "real_layerd_layer_proposals", "status": "unavailable", "proposals": [p for r in layerd for p in r.get("proposals", [])], "adapter_results": layerd, "canva_parity_claimed": False})
    (root / "real_layer_proposal_report.md").write_text(_family_md("Real Layer Proposal Report", results, sum(len(r.get("proposals", [])) for r in results)), encoding="utf-8")
    _write_stdout_stderr(root, results)


def _write_chart_table(root: Path, results: list[dict[str, Any]]) -> None:
    _write_family(root, "real_chart_table_region_ledger.json", "real_chart_table_adapter_report.md", "Real Chart/Table Adapter Report", results)
    _write_json(root / "real_native_reconstruction_candidates.json", {"schema_name": "real_native_reconstruction_candidates", "status": "unavailable", "candidates": [], "canva_parity_claimed": False})


def _write_stdout_stderr(root: Path, results: list[dict[str, Any]]) -> None:
    _write_json(root / "adapter_stdout_stderr.json", {"schema_name": "adapter_stdout_stderr", "adapters": [{"adapter_id": r.get("adapter_id"), "stdout": r.get("stdout", ""), "stderr": r.get("stderr", ""), "status": r.get("status")} for r in results], "canva_parity_claimed": False})


def _family_md(title: str, results: list[dict[str, Any]], proposal_count: int) -> str:
    lines = [f"# {title}", "", f"- Proposal count: `{proposal_count}`", "- Canva parity claimed: `False`", "", "| Adapter | Status | Reason |", "|---|---|---|"]
    for result in results:
        lines.append(f"| `{result.get('adapter_id')}` | `{result.get('status')}` | `{result.get('reason') or '-'}` |")
    if not results:
        lines.append("| `none` | `unavailable` | `not configured` |")
    return "\n".join(lines) + "\n"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
