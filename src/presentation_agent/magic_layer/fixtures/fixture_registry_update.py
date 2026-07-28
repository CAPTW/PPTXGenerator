from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def update_e01b_repo_state(repo_root: str | Path, *, fixture_path: str, pptx_path: str, b03_report_path: str, status: str, limitations: list[str]) -> dict[str, Any]:
    root = Path(repo_root)
    evidence_path = root / "repo_state/evidence_index.json"
    registry_path = root / "repo_state/artifact_family_registry.json"
    evidence = _read_json(evidence_path)
    registry = _read_json(registry_path)

    fixtures = evidence.setdefault("fixtures", [])
    replacement = {
        "name": "e01b_single_reference_pass",
        "path": fixture_path,
        "exists": True,
        "file_count": len([p for p in Path(fixture_path).rglob("*") if p.is_file()]),
        "evidence_class": "REGRESSION_FIXTURE_SINGLE_REFERENCE_PASS",
        "scope": "SINGLE_REFERENCE_MAGIC_LAYER_PLUS_REGRESSION",
        "status": status,
        "product_pass": False,
        "arbitrary_robustness": False,
        "e03_unlock": False,
        "e04_unlock": False,
        "d08_unlock": False,
        "paths": {"pptx": pptx_path, "b03_report": b03_report_path},
        "limitations": limitations,
        "claims_supported": ["CLAIM_MAGIC_LAYER_PLUS_SINGLE_REFERENCE_REGRESSION", "CLAIM_SEMANTIC_EDITABILITY"],
        "claims_blocked": ["CLAIM_PRODUCT_PASS", "CLAIM_TEMPLATE_PACK_READINESS", "CLAIM_SOURCE_BOUND_READINESS", "CLAIM_SCALEOUT_READINESS", "CLAIM_CANONICAL_PROMOTION"],
    }
    fixtures[:] = [item for item in fixtures if item.get("name") != "e01b_single_reference_pass"]
    fixtures.append(replacement)
    evidence["p02_ready"] = False
    evidence["quarantine_excluded"] = True
    evidence["manual_review_not_product_evidence"] = True

    families = registry.setdefault("families", [])
    if "E01B_PASS_FIXTURE" not in families:
        families.append("E01B_PASS_FIXTURE")
    registry["manual_review_not_product_evidence"] = True
    registry["quarantine_not_active"] = True

    evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / "repo_state/evidence_index.md").write_text("# Evidence Index\n\n- `e01b_single_reference_pass` fixture는 C04에서 core evidence repaired 상태로 갱신되었다.\n- 이 fixture는 single-reference regression evidence이며 product PASS가 아니다.\n- E03/E04/D08/C11/bulk/canonical promotion은 계속 blocked 상태다.\n", encoding="utf-8")
    (root / "repo_state/artifact_family_registry.md").write_text("# 아티팩트 패밀리 레지스트리\n\n- `E01B_PASS_FIXTURE`는 single-reference regression fixture family이다.\n- quarantine artifact는 active product evidence가 아니다.\n- canonical promotion은 blocked 상태다.\n", encoding="utf-8")

    return {
        "schema": "repo_state_update_report.v1",
        "updated": True,
        "evidence_index_path": str(evidence_path),
        "artifact_family_registry_path": str(registry_path),
        "fixture_id": "e01b_single_reference_pass",
        "status": status,
        "product_pass": False,
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}
