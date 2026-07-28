from __future__ import annotations

from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
C02_CONTROLLED_PPTX = ROOT / "design_runs/run_003/outputs/c02_rx_controlled_minimal_pptx_compile/controlled_minimal_editable_candidate.pptx"
EXPECTED_C02_CONTROLLED_HASH = "72395b7debf50d8cace0439269e864f5abd649d1781d6c9232d25d3b878df614"
C02B_PATCHED_PPTX = ROOT / "design_runs/run_003/outputs/c02b_rx_patch_minimal_ooxml_backend_compatibility/controlled_minimal_editable_candidate_c02b.pptx"
EXPECTED_C02B_PATCHED_HASH = "af09ecb032d9b187d8ceafb08b41097b1dcfc767dd079253237c781a0883559c"
DEFAULT_RENDER_NAME = "controlled_minimal_rendered_slide.png"
C03A_RETRY_RENDER_NAME = "controlled_minimal_c02b_rendered_slide.png"
C03A_RETRY_OUTPUT_FOLDER = ROOT / "design_runs/run_003/outputs/c03a_rx_retry_render_c02b_powerpoint_openable_pptx"
PROTECTED_NAMES = {
    "outputs/editable_template_spec.final.json",
    "outputs/golden_template_masters.pptx",
    "outputs/final_deck_large_premium.pptx",
}


def validate_render_scope(
    pptx_inputs: list[str | Path],
    out_dir: str | Path,
    *,
    render_output: str | Path | None = None,
) -> dict[str, Any]:
    out_root = Path(out_dir).resolve()
    output = Path(render_output).resolve() if render_output else out_root / DEFAULT_RENDER_NAME
    inputs = [Path(item).resolve() for item in pptx_inputs]
    blockers: list[str] = []
    decision = "RENDER_SCOPE_ALLOWED"

    if len(inputs) != 1:
        decision = "RENDER_SCOPE_BLOCKED_TOO_MANY_INPUTS"
        blockers.append("Exactly one PPTX input is allowed.")
    elif inputs[0] != C02_CONTROLLED_PPTX.resolve():
        decision = "RENDER_SCOPE_BLOCKED_WRONG_PPTX"
        blockers.append("Only the C02 controlled minimal PPTX may be rendered.")

    normalized_output = _norm(output)
    if any(protected.lower() in normalized_output.lower() for protected in PROTECTED_NAMES):
        decision = "RENDER_SCOPE_BLOCKED_PROTECTED_ARTIFACT"
        blockers.append("Protected/canonical artifact paths may not be written.")
    elif "source_bound" in normalized_output.lower() or "source-bound" in normalized_output.lower():
        decision = "RENDER_SCOPE_BLOCKED_CANONICAL"
        blockers.append("Source-bound render outputs are forbidden.")
    elif "_local_quarantine" in normalized_output.lower() or "__quarantine" in normalized_output.lower():
        decision = "RENDER_SCOPE_BLOCKED_QUARANTINE"
        blockers.append("Quarantine paths may not be read or written.")
    elif not _is_relative_to(output, out_root):
        decision = "RENDER_SCOPE_BLOCKED_OUTPUT_OUTSIDE_FOLDER"
        blockers.append("Render output must be under the C03 output folder.")

    return {
        "schema": "controlled_render_scope_guard.v1",
        "decision": decision,
        "allowed": decision == "RENDER_SCOPE_ALLOWED",
        "input_pptx_count": len(inputs),
        "input_pptx_paths": [str(item) for item in inputs],
        "allowed_input_pptx_path": str(C02_CONTROLLED_PPTX),
        "allowed_output_folder": str(out_root),
        "render_output": str(output),
        "expected_primary_render_count": 1,
        "pptx_output_allowed": False,
        "source_bound_output_allowed": False,
        "canonical_output_allowed": False,
        "blockers": blockers,
    }


def validate_render_scope_v2(
    pptx_inputs: list[str | Path],
    out_dir: str | Path,
    *,
    render_output: str | Path | None = None,
    expected_hash: str | None = EXPECTED_C02_CONTROLLED_HASH,
) -> dict[str, Any]:
    result = validate_render_scope(pptx_inputs, out_dir, render_output=render_output)
    result["schema"] = "controlled_render_scope_guard.v2"
    if not result["allowed"]:
        result["expected_input_sha256"] = expected_hash
        result["actual_input_sha256"] = _sha(inputs[0]) if (inputs := [Path(item).resolve() for item in pptx_inputs]) else None
        return result
    actual = _sha(Path(pptx_inputs[0]).resolve())
    result["expected_input_sha256"] = expected_hash
    result["actual_input_sha256"] = actual
    result["hash_match"] = expected_hash is None or actual == expected_hash
    if expected_hash is not None and actual != expected_hash:
        result["decision"] = "RENDER_SCOPE_BLOCKED_HASH_MISMATCH"
        result["allowed"] = False
        result.setdefault("blockers", []).append("Input PPTX hash does not match the controlled C02 hash.")
    return result


def validate_render_scope_retry(
    pptx_inputs: list[str | Path],
    out_dir: str | Path,
    *,
    render_output: str | Path | None = None,
    expected_hash: str | None = EXPECTED_C02B_PATCHED_HASH,
    allowed_output_folder: str | Path | None = None,
    allow_foreign_hash_match: bool = False,
) -> dict[str, Any]:
    out_root = Path(out_dir).resolve()
    allowed_root = Path(allowed_output_folder).resolve() if allowed_output_folder else C03A_RETRY_OUTPUT_FOLDER.resolve()
    output = Path(render_output).resolve() if render_output else out_root / C03A_RETRY_RENDER_NAME
    inputs = [Path(item).resolve() for item in pptx_inputs]
    blockers: list[str] = []
    decision = "RENDER_SCOPE_ALLOWED"
    actual_hash = _sha(inputs[0]) if inputs else None

    if len(inputs) != 1:
        decision = "RENDER_SCOPE_BLOCKED_TOO_MANY_INPUTS"
        blockers.append("Exactly one PPTX input is allowed.")
    elif inputs[0] != C02B_PATCHED_PPTX.resolve():
        if not (allow_foreign_hash_match and expected_hash is not None and actual_hash == expected_hash):
            decision = "RENDER_SCOPE_BLOCKED_WRONG_PPTX"
            blockers.append("Only the C02B patched controlled PPTX may be rendered.")

    if decision == "RENDER_SCOPE_ALLOWED" and expected_hash is not None and actual_hash != expected_hash:
        decision = "RENDER_SCOPE_BLOCKED_HASH_MISMATCH"
        blockers.append("Input PPTX hash does not match the C02B patched PPTX hash.")

    normalized_output = _norm(output)
    if any(protected.lower() in normalized_output.lower() for protected in PROTECTED_NAMES):
        decision = "RENDER_SCOPE_BLOCKED_PROTECTED_ARTIFACT"
        blockers.append("Protected/canonical artifact paths may not be written.")
    elif "source_bound" in normalized_output.lower() or "source-bound" in normalized_output.lower():
        decision = "RENDER_SCOPE_BLOCKED_CANONICAL"
        blockers.append("Source-bound render outputs are forbidden.")
    elif "_local_quarantine" in normalized_output.lower() or "__quarantine" in normalized_output.lower():
        decision = "RENDER_SCOPE_BLOCKED_QUARANTINE"
        blockers.append("Quarantine paths may not be read or written.")
    elif out_root != allowed_root:
        decision = "RENDER_SCOPE_BLOCKED_OUTPUT_OUTSIDE_FOLDER"
        blockers.append("Render output folder must equal the C03A retry output folder.")
    elif not _is_relative_to(output, out_root):
        decision = "RENDER_SCOPE_BLOCKED_OUTPUT_OUTSIDE_FOLDER"
        blockers.append("Render output must be under the C03A retry output folder.")

    return {
        "schema": "render_scope_guard_retry.v1",
        "decision": decision,
        "allowed": decision == "RENDER_SCOPE_ALLOWED",
        "input_pptx_count": len(inputs),
        "input_pptx_paths": [str(item) for item in inputs],
        "allowed_input_pptx_path": str(C02B_PATCHED_PPTX),
        "allowed_output_folder": str(allowed_root),
        "render_output": str(output),
        "expected_input_sha256": expected_hash,
        "actual_input_sha256": actual_hash,
        "hash_match": expected_hash is None or actual_hash == expected_hash,
        "expected_primary_render_count": 1,
        "pptx_output_allowed": False,
        "source_bound_output_allowed": False,
        "canonical_output_allowed": False,
        "blockers": blockers,
        "product_pass": False,
    }


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _norm(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _sha(path: Path) -> str | None:
    if not path.is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
