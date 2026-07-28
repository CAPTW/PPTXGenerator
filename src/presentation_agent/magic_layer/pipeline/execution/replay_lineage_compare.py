from __future__ import annotations

from pathlib import Path
from typing import Any

from ..controlled_sample import C02B_HASH, C03A_RENDER_HASH, PATHS
from ..hash_lineage import sha256_file


def compare_with_p02_lineage(*, p03_pptx: str | Path, p03_render: str | Path, input_hashes: dict[str, str | None], dry_run_decision: str, b03_status: str, review_status: str) -> dict[str, Any]:
    pptx_hash = sha256_file(p03_pptx)
    render_hash = sha256_file(p03_render)
    limitations = []
    if pptx_hash != C02B_HASH:
        limitations.append("P03 PPTX hash differs from C02B baseline; structural gates decide passability.")
    if render_hash != C03A_RENDER_HASH:
        limitations.append("P03 render hash differs from C03A retry baseline; image profile and B01 decide passability.")
    input_match = all(value is not None for value in input_hashes.values())
    status = "LINEAGE_MATCH" if pptx_hash == C02B_HASH and render_hash == C03A_RENDER_HASH and input_match else "LINEAGE_MATCH_WITH_HASH_DIFFERENCE"
    return {
        "schema": "p03_compare_with_p02_lineage_report.v1",
        "status": status,
        "input_hashes": input_hashes,
        "p03_pptx_hash": pptx_hash,
        "p02_c02b_pptx_hash": C02B_HASH,
        "p03_render_hash": render_hash,
        "p02_c03a_render_hash": C03A_RENDER_HASH,
        "dry_run_decision": dry_run_decision,
        "b03_status": b03_status,
        "review_status": review_status,
        "render_is_reference_image": False,
        "limitations": limitations,
        "product_pass": False,
    }
