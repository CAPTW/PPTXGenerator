"""Curated Phase 7C delivery assembly and independent package validation."""

from __future__ import annotations

import copy
import hashlib
import mimetypes
import re
import shutil
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterable, Mapping, Sequence

from ..identity import canonical_json_bytes, stable_id
from ..manifest_io import read_json, write_json
from .contracts import (
    PROTECTED_OUTPUTS,
    bind_content_hash,
    scan_release_text,
    sha256_file,
    verify_content_hash,
)
from .devpost_evidence import generate_submission_drafts
from .release_candidate_gate import (
    REQUIRED_PREREQUISITES,
    build_release_candidate_gate,
    validate_release_candidate_gate,
)


SOURCE_FILES = (
    "input_request.json",
    "source_corpus.json",
    "source_locators.json",
    "evidence_unit_registry.json",
    "source_coverage_report.json",
)
ARCHITECTURE_FILES = (
    "workflow_resolution.json",
    "source_gap_report.json",
    "presentation_plan.json",
    "slide_blueprint_collection.json",
    "evidence_allocation_report.json",
    "presentation_architecture.json",
    "design_invariants.json",
    "module_art_directions.json",
    "creative_template_architecture.json",
    "creative_fit_report.json",
    "editable_template_spec.json",
)
QA_FILES = (
    "official_final_gate_report.json",
    "pptx_package_validation_report.json",
    "html_package_validation_report.json",
    "semantic_qa_report.json",
    "source_coverage_qa_report.json",
    "creative_qa_report.json",
    "editability_qa_report.json",
    "visual_qa_report.json",
    "raster_crop_qa_report.json",
    "parity_report.json",
    "composite_qa_report.json",
)
REPAIR_FILES = (
    "phase6_repair_proof.json",
    "fault_injection_spec.json",
    "controlled_failure_detection_report.json",
    "repair_history.json",
    "before_after_manifest.json",
    "before_faulty_repaired_contact_sheet.png",
)
PROVENANCE_FILES = (
    "release_contract.json",
    "runtime_environment_manifest.json",
    "external_prerequisite_manifest.json",
    "external_python_runtime_dependency_manifest.json",
    "dependency_closure_validation_report.json",
    "external_entrypoint_canary_report.json",
    "fresh_locked_environment_report.json",
    "external_skillset_pin.json",
    "phase4_bundle_fingerprint_authority.json",
    "phase5_bundle_fingerprint_authority.json",
    "build_week_provenance.json",
    "component_provenance.json",
    "demo_run_manifest.json",
    "semantic_reproducibility_report.json",
)
DEVPOST_FILES = (
    "ELEVATOR_PITCH.md",
    "DEVPOST_ABOUT_PROJECT.md",
    "BUILT_WITH_TAGS.md",
    "DEMO_SCRIPT.md",
    "JUDGING_EVIDENCE_MATRIX.md",
    "ARCHITECTURE_OVERVIEW.md",
    "EXISTING_ADAPTED_NEW.md",
    "KNOWN_LIMITATIONS.md",
    "SCREENSHOT_AND_ARTIFACT_INDEX.md",
    "TECHNICAL_METRICS.md",
    "SESSION_PROVENANCE.md",
    "SUBMISSION_CHECKLIST.md",
)
CONTROL_PATHS = frozenset({"delivery_manifest.json", "release_candidate_gate.json"})
REQUIRED_FILE_PATHS = (
    "README.md",
    "input/prompt.txt",
    "input/cooling_system_overview.pdf",
    "input/cooling_risk_decision_report.pdf",
    *(f"source/{name}" for name in SOURCE_FILES),
    *(f"architecture/{name}" for name in ARCHITECTURE_FILES),
    *(f"visual/semantic_sidecars/slide-{index:03d}.semantic.json" for index in range(1, 7)),
    *(f"visual/visual_targets/slide-{index:03d}.png" for index in range(1, 7)),
    "visual/visual_target_manifest.json",
    "visual/visual_dna.json",
    "visual/design_system.json",
    "visual/generation_provenance.json",
    "output/pptx_generator_demo.pptx",
    "output/html/index.html",
    *(f"renders/slide-{index:03d}.png" for index in range(1, 7)),
    "renders/contact_sheet.png",
    *(f"qa/{name}" for name in QA_FILES),
    *(f"repair/{name}" for name in REPAIR_FILES),
    *(f"provenance/{name}" for name in PROVENANCE_FILES),
    *(f"devpost/{name}" for name in DEVPOST_FILES),
    "THIRD_PARTY_NOTICES.md",
    "known_limitations.md",
    "delivery_manifest.json",
    "release_candidate_gate.json",
)
REQUIRED_DIRECTORY_PATHS = ("output/html/assets",)
ALLOWED_EXECUTABLE_SUFFIXES: frozenset[str] = frozenset()
UNEXPECTED_EXECUTABLE_SUFFIXES = {
    ".bat",
    ".cmd",
    ".com",
    ".dll",
    ".exe",
    ".msi",
    ".pif",
    ".ps1",
    ".scr",
    ".sh",
}
TEXT_SUFFIXES = {
    "",
    ".css",
    ".csv",
    ".html",
    ".htm",
    ".js",
    ".json",
    ".md",
    ".pem",
    ".txt",
    ".svg",
    ".xml",
    ".yaml",
    ".yml",
}
KNOWN_BINARY_SUFFIXES = {
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".pptx",
    ".webp",
}
MAX_PACKAGE_FILE_BYTES = 75 * 1024 * 1024
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{6,}\b")
_BEARER = re.compile(r"(?i)\bAuthorization\s*:\s*Bearer\s+[A-Za-z0-9._~+/=-]{8,}")
_CREDENTIAL = re.compile(
    r"(?i)\b(?:api[_-]?key|access[_-]?token|client[_-]?secret|password|"
    r"authorization|bearer|oauth[_-]?token|cookie|session[_-]?(?:id|token))"
    r"\s*[:=]\s*['\"]?[A-Za-z0-9_./+\-=]{8,}"
)
_PRIVATE_IDENTITY = re.compile(
    r"(?i)\b[A-Z0-9._%+-]+@(?!(?:example\.(?:com|org|net)|localhost)\b)"
    r"[A-Z0-9.-]+\.[A-Z]{2,}\b"
)
_BROWSER_PROFILE = re.compile(
    r"(?i)(?:browser[_ -]?profile|user[_ -]?data[_ -]?dir|"
    r"[\\/]User Data[\\/]|[\\/]Default[\\/](?:Cookies|Login Data))"
)
_ABSOLUTE_PATH = re.compile(
    r"(?i)(?:\b[A-Z]:[\\/](?:Users|dev|Windows|Program Files|ProgramData|Temp)[\\/]|"
    r"\b/(?:tmp|home|Users)/)"
)
_TEMP_PATH = re.compile(
    r"(?i)(?:\b[A-Z]:[\\/][^\s\"']*(?:AppData[\\/]Local[\\/]Temp|[\\/]Temp)[\\/]|"
    r"\b/(?:tmp|var/tmp)/)"
)
_USER_PATH = re.compile(r"(?i)\b[A-Z]:[\\/]Users[\\/][^\\/\s\"']+")
_BROWSER_BINARY_NAME = re.compile(
    r"(?i)^(?:chrome|chromium|msedge|firefox)(?:-headless-shell)?\.exe$"
)
_RUNTIME_UUID = re.compile(
    r"(?i)(?:phase7c|pptx-generator)[^\\/\s\"']*[\\/_-][0-9a-f]{24,}"
)
_SELF_HASH_FIELDS = (
    "manifest_hash",
    "report_hash",
    "provenance_hash",
    "content_sha256",
    "contract_hash",
    "policy_hash",
    "gate_hash",
)


class PackageError(RuntimeError):
    """Stable Phase 7C package failure."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def assert_safe_package_path(value: str | Path) -> str:
    raw = str(value).replace("\\", "/")
    posix = PurePosixPath(raw)
    windows = PureWindowsPath(str(value))
    if (
        not raw
        or raw.startswith("/")
        or windows.is_absolute()
        or posix.is_absolute()
        or any(part in {"", ".", ".."} for part in posix.parts)
        or ":" in posix.parts[0]
    ):
        raise PackageError("DC_PACKAGE_PATH_UNSAFE", str(value))
    return posix.as_posix()


def _media_type(path: Path) -> str:
    overrides = {
        ".json": "application/json",
        ".md": "text/markdown",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
    return overrides.get(
        path.suffix.lower(),
        mimetypes.guess_type(path.name)[0] or "application/octet-stream",
    )


def _logical_role(relative: str) -> str:
    if "/" not in relative:
        return {
            "README.md": "delivery_readme",
            "THIRD_PARTY_NOTICES.md": "third_party_notices",
            "known_limitations.md": "known_limitations",
            "delivery_manifest.json": "delivery_manifest",
            "release_candidate_gate.json": "release_candidate_gate",
        }.get(relative, "delivery_control")
    return relative.split("/", 1)[0]


def _default_provenance(relative: str) -> str:
    if relative.startswith(("input/", "source/")):
        return "existing"
    if relative.startswith(("visual/", "repair/")):
        return "historical_evidence"
    if relative.startswith("output/") or relative.startswith("renders/"):
        return "build_week_new"
    if relative.startswith(("qa/", "devpost/")):
        return "build_week_new"
    return "adapted"


def build_package_inventory(
    root: str | Path,
    *,
    exclude_paths: Iterable[str] = (),
    record_overrides: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    base = Path(root)
    excluded = {assert_safe_package_path(path) for path in exclude_paths}
    overrides = record_overrides or {}
    rows: list[dict[str, Any]] = []
    for path in sorted(
        (item for item in base.rglob("*") if item.is_file()),
        key=lambda item: item.relative_to(base).as_posix(),
    ):
        relative = path.relative_to(base).as_posix()
        if relative in excluded:
            continue
        assert_safe_package_path(relative)
        digest = sha256_file(path)
        override = dict(overrides.get(relative, {}))
        row = {
            "artifact_id": stable_id("artifact", relative, digest),
            "logical_role": _logical_role(relative),
            "path": relative,
            "byte_size": path.stat().st_size,
            "sha256": digest,
            "media_type": _media_type(path),
            "source_artifact_id": override.pop(
                "source_artifact_id", stable_id("source_artifact", relative)
            ),
            "source_sha256": override.pop("source_sha256", digest),
            "producer_stage": override.pop(
                "producer_stage", "delivery_package_assembly"
            ),
            "provenance_classification": override.pop(
                "provenance_classification", _default_provenance(relative)
            ),
            "required": override.pop("required", relative in REQUIRED_FILE_PATHS),
            "semantic_truth_role": override.pop(
                "semantic_truth_role",
                "authoritative_copy"
                if relative.startswith(("source/", "architecture/", "visual/"))
                else "supporting_evidence",
            ),
            "visual_truth_role": override.pop(
                "visual_truth_role",
                "reference_only"
                if relative.startswith("visual/visual_targets/")
                else "not_visual_truth",
            ),
            "redistributable_status": override.pop(
                "redistributable_status", "CLEARED"
            ),
            "validation_status": override.pop("validation_status", "PASS"),
        }
        row.update(override)
        rows.append(row)
    logical_hash = logical_package_fingerprint(rows)
    return bind_content_hash(
        {
            "schema_name": "package_inventory",
            "schema_version": "1.0.0",
            "file_count": len(rows),
            "total_bytes": sum(row["byte_size"] for row in rows),
            "logical_package_fingerprint": logical_hash,
            "files": rows,
        },
        "inventory_hash",
    )


def logical_package_fingerprint(records: Iterable[Mapping[str, Any]]) -> str:
    canonical = [
        {
            "path": assert_safe_package_path(str(row["path"])),
            "byte_size": int(row["byte_size"]),
            "sha256": str(row["sha256"]),
        }
        for row in records
    ]
    canonical.sort(key=lambda row: row["path"])
    return hashlib.sha256(canonical_json_bytes(canonical)).hexdigest()


def sanitize_json_value(
    value: Any, replacements: Mapping[str, str]
) -> tuple[Any, int]:
    """Return a deep sanitized copy and exact replacement count."""

    count = 0

    def visit(item: Any) -> Any:
        nonlocal count
        if isinstance(item, dict):
            return {key: visit(entry) for key, entry in item.items()}
        if isinstance(item, list):
            return [visit(entry) for entry in item]
        if isinstance(item, tuple):
            return [visit(entry) for entry in item]
        if isinstance(item, str):
            result = item
            for source, replacement in replacements.items():
                variants = {
                    source,
                    source.replace("\\", "/"),
                    source.replace("/", "\\"),
                }
                for variant in sorted(variants, key=len, reverse=True):
                    occurrences = result.count(variant)
                    if occurrences:
                        result = result.replace(variant, replacement)
                        count += occurrences
            return result
        return item

    return visit(copy.deepcopy(value)), count


def _text_scan(path: Path) -> dict[str, int]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {
            "secret_count": 0,
            "credential_count": 0,
            "private_key_count": 0,
            "path_leak_count": 0,
            "absolute_path_count": 0,
            "temp_path_count": 0,
            "user_path_leak_count": 0,
            "jwt_count": 0,
            "browser_profile_count": 0,
            "browser_binary_count": 0,
            "private_identity_count": 0,
            "runtime_uuid_path_count": 0,
        }
    base = scan_release_text(text)
    scan_text = text.replace("\\\\", "\\")
    jwt_count = len(_JWT.findall(text))
    bearer_count = len(_BEARER.findall(text))
    credential_count = len(_CREDENTIAL.findall(text)) + jwt_count
    absolute_path_count = int(_ABSOLUTE_PATH.search(scan_text) is not None)
    return {
        **base,
        "secret_count": base["secret_count"]
        + bearer_count
        + jwt_count,
        "credential_count": credential_count,
        "path_leak_count": int(
            bool(base["path_leak_count"] or absolute_path_count)
        ),
        "absolute_path_count": absolute_path_count,
        "temp_path_count": int(_TEMP_PATH.search(scan_text) is not None),
        "user_path_leak_count": int(_USER_PATH.search(scan_text) is not None),
        "jwt_count": jwt_count,
        "browser_profile_count": int(_BROWSER_PROFILE.search(text) is not None),
        "browser_binary_count": 0,
        "private_identity_count": len(_PRIVATE_IDENTITY.findall(text)),
        "runtime_uuid_path_count": int(_RUNTIME_UUID.search(text) is not None),
    }


def scan_package_tree(
    root: str | Path, *, max_file_bytes: int = MAX_PACKAGE_FILE_BYTES
) -> dict[str, Any]:
    base = Path(root)
    totals = {
        "secret_count": 0,
        "credential_count": 0,
        "private_key_count": 0,
        "path_leak_count": 0,
        "absolute_path_count": 0,
        "temp_path_count": 0,
        "user_path_leak_count": 0,
        "jwt_count": 0,
        "browser_profile_count": 0,
        "browser_binary_count": 0,
        "private_identity_count": 0,
        "runtime_uuid_path_count": 0,
        "protected_output_count": 0,
        "external_skill_source_count": 0,
        "unexpected_executable_count": 0,
        "unknown_binary_count": 0,
        "oversize_file_count": 0,
        "symlink_count": 0,
        "font_binary_count": 0,
        "cache_artifact_count": 0,
    }
    findings: list[dict[str, str]] = []
    protected_names = {Path(path).name.lower() for path in PROTECTED_OUTPUTS}
    for path in sorted(base.rglob("*")):
        relative = path.relative_to(base).as_posix()
        if path.is_symlink():
            totals["symlink_count"] += 1
            findings.append({"code": "symlink", "path": relative})
            continue
        if path.is_dir():
            if path.name.lower() in {
                ".git",
                ".pytest_cache",
                "__pycache__",
                "node_modules",
                ".venv",
                "venv",
            }:
                totals["cache_artifact_count"] += 1
            continue
        suffix = path.suffix.lower()
        if path.stat().st_size > max_file_bytes:
            totals["oversize_file_count"] += 1
        if path.name.lower() in protected_names:
            totals["protected_output_count"] += 1
        if suffix in UNEXPECTED_EXECUTABLE_SUFFIXES:
            totals["unexpected_executable_count"] += 1
        if _BROWSER_BINARY_NAME.fullmatch(path.name):
            totals["browser_binary_count"] += 1
        if suffix not in TEXT_SUFFIXES and suffix not in KNOWN_BINARY_SUFFIXES:
            totals["unknown_binary_count"] += 1
        if suffix in {".ttf", ".otf", ".woff", ".woff2"}:
            totals["font_binary_count"] += 1
        normalized = relative.lower()
        if path.name.lower() == "skill.md" or (
            "external_skill" in normalized and suffix in {".py", ".js", ".md"}
        ):
            totals["external_skill_source_count"] += 1
        if suffix in TEXT_SUFFIXES:
            result = _text_scan(path)
            for name, value in result.items():
                totals[name] += value
    totals["finding_count"] = sum(
        value for key, value in totals.items() if key.endswith("_count")
    )
    totals["findings"] = findings
    totals["status"] = "PASS" if totals["finding_count"] == 0 else "BLOCKED"
    return totals


def validate_delivery_manifest_records(
    root: str | Path,
    records: Sequence[Mapping[str, Any]],
    *,
    ignored_paths: Iterable[str] = (),
) -> bool:
    base = Path(root)
    ignored = {assert_safe_package_path(path) for path in ignored_paths}
    artifact_ids = [str(row.get("artifact_id", "")) for row in records]
    if len(artifact_ids) != len(set(artifact_ids)):
        raise PackageError("DC_PACKAGE_DUPLICATE_ARTIFACT_ID")
    paths = [assert_safe_package_path(str(row.get("path", ""))) for row in records]
    if len(paths) != len(set(paths)):
        raise PackageError("DC_PACKAGE_DUPLICATE_PATH")
    for row, relative in zip(records, paths):
        path = base / Path(relative)
        if not path.is_file():
            raise PackageError("DC_PACKAGE_FILE_MISSING", relative)
        if path.stat().st_size != row.get("byte_size") or sha256_file(path) != row.get(
            "sha256"
        ):
            raise PackageError("DC_PACKAGE_HASH_MISMATCH", relative)
    actual = {
        path.relative_to(base).as_posix()
        for path in base.rglob("*")
        if path.is_file()
    }
    unmanaged = sorted(actual - set(paths) - ignored)
    if unmanaged:
        raise PackageError("DC_PACKAGE_UNMANAGED_FILE", ",".join(unmanaged))
    return True


def validate_license_boundary(payload: Mapping[str, Any]) -> bool:
    valid = (
        payload.get("unresolved_redistribution_blocker_count") == 0
        and payload.get("external_skill_source_included") is False
        and payload.get("third_party_notice_complete") is True
        and payload.get("license_claims_verified") is True
        and payload.get("phase7a_license_report_valid") is True
        and payload.get("phase7a_security_audit_valid") is True
        and payload.get("component_provenance_valid") is True
        and payload.get("platform_generation_provenance_valid") is True
        and payload.get("external_skill_redistribution") is False
        and payload.get("third_party_source_content_count") == 0
        and payload.get("browser_binary_count") == 0
        and payload.get("font_binary_count") == 0
    )
    if not valid:
        raise PackageError("BLOCKED_LICENSE_PROVENANCE_INCOMPLETE")
    return True


def validate_qa_boundary(root: str | Path) -> bool:
    qa = Path(root) / "qa"
    reports = {name: read_json(qa / name) for name in QA_FILES}
    if any(report.get("status") != "PASS" for report in reports.values()):
        raise PackageError("DC_PACKAGE_QA_NOT_PASS")
    for report in reports.values():
        if "report_hash" in report and not verify_content_hash(report, "report_hash"):
            raise PackageError("DC_PACKAGE_QA_HASH_MISMATCH")
    semantic = reports["semantic_qa_report.json"].get("checks", {})
    source = reports["source_coverage_qa_report.json"].get("checks", {})
    editability = reports["editability_qa_report.json"].get("checks", {})
    raster = reports["raster_crop_qa_report.json"].get("checks", {})
    parity = reports["parity_report.json"].get("checks", {})
    composite = reports["composite_qa_report.json"].get("checks", {})
    zero_editability = (
        "full_slide_picture_count",
        "screenshot_slide_count",
        "semantic_raster_violation_count",
        "unsupported_semantic_substitution_count",
    )
    zero_raster = (
        "crop_count",
        "full_slide_raster_count",
        "html_image_count",
        "screenshot_slide_count",
        "semantic_raster_violation_count",
        "unknown_source_count",
    )
    valid = (
        semantic.get("pptx_fidelity") == 1.0
        and semantic.get("html_fidelity") == 1.0
        and source.get("coverage") == 1.0
        and editability.get("native_requirement_coverage") == 1.0
        and all(editability.get(key) == 0 for key in zero_editability)
        and all(raster.get(key) == 0 for key in zero_raster)
        and parity.get("parity_fidelity") == 1.0
        and parity.get("mismatch_count") == 0
        and composite.get("composite_acceptance") == "PASS"
    )
    if not valid:
        raise PackageError("DC_PACKAGE_EDITABILITY_OR_RASTER_POLICY_FAILED")
    return True


def create_deterministic_archive(root: str | Path, archive_path: str | Path) -> Path:
    base = Path(root)
    archive = Path(archive_path)
    archive.parent.mkdir(parents=True, exist_ok=True)
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(
        archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as handle:
        for path in sorted(base.rglob("*"), key=lambda item: item.as_posix()):
            relative = path.relative_to(base).as_posix()
            assert_safe_package_path(relative)
            if path.is_symlink():
                raise PackageError("DC_PACKAGE_SYMLINK_FORBIDDEN", relative)
            if path.is_dir():
                info = zipfile.ZipInfo(relative.rstrip("/") + "/")
                info.date_time = (1980, 1, 1, 0, 0, 0)
                info.external_attr = 0o40755 << 16
                handle.writestr(info, b"")
                continue
            info = zipfile.ZipInfo(relative)
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            handle.writestr(info, path.read_bytes())
    return archive


def validate_archive(
    archive_path: str | Path, directory_root: str | Path | None = None
) -> dict[str, Any]:
    archive = Path(archive_path)
    try:
        with zipfile.ZipFile(archive) as handle:
            names = handle.namelist()
            if len(names) != len(set(names)):
                raise PackageError("DC_PACKAGE_ZIP_DUPLICATE_MEMBER")
            for name in names:
                try:
                    assert_safe_package_path(name.rstrip("/"))
                except PackageError as exc:
                    raise PackageError("DC_PACKAGE_ZIP_SLIP", name) from exc
            bad = handle.testzip()
            if bad is not None:
                raise PackageError("DC_PACKAGE_ZIP_INVALID", bad)
            archive_files = {
                name: hashlib.sha256(handle.read(name)).hexdigest()
                for name in names
                if not name.endswith("/")
            }
            archive_dirs = {name.rstrip("/") for name in names if name.endswith("/")}
    except PackageError:
        raise
    except (OSError, zipfile.BadZipFile) as exc:
        raise PackageError("DC_PACKAGE_ZIP_INVALID", str(archive)) from exc
    if directory_root is not None:
        root = Path(directory_root)
        directory_files = {
            path.relative_to(root).as_posix(): sha256_file(path)
            for path in root.rglob("*")
            if path.is_file()
        }
        directory_dirs = {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_dir()
        }
        if archive_files != directory_files or archive_dirs != directory_dirs:
            raise PackageError("DC_PACKAGE_ARCHIVE_MISMATCH")
    return {
        "zip_crc_status": "PASS",
        "archive_sha256": sha256_file(archive),
        "archive_file_count": len(archive_files),
        "status": "PASS",
    }


def _required_roles(root: Path, *, allow_missing_gate: bool = False) -> list[str]:
    missing = [
        relative
        for relative in REQUIRED_FILE_PATHS
        if not (root / Path(relative)).is_file()
        and not (allow_missing_gate and relative == "release_candidate_gate.json")
    ]
    missing.extend(
        relative
        for relative in REQUIRED_DIRECTORY_PATHS
        if not (root / Path(relative)).is_dir()
    )
    return sorted(missing)


def validate_required_package_roles(
    root: str | Path, *, allow_missing_gate: bool = False
) -> bool:
    missing = _required_roles(Path(root), allow_missing_gate=allow_missing_gate)
    if missing:
        raise PackageError(
            "DC_PACKAGE_REQUIRED_ARTIFACT_MISSING", ",".join(missing)
        )
    return True


def validate_delivery(
    package: Mapping[str, Any], *, allow_missing_gate: bool = False
) -> dict[str, Any]:
    root = Path(package["delivery_root"])
    manifest_path = Path(package["delivery_manifest_path"])
    report_path = Path(package["validation_report_path"])
    archive_path = Path(package["archive_path"])
    missing = _required_roles(root, allow_missing_gate=allow_missing_gate)
    manifest = read_json(manifest_path)
    if not verify_content_hash(manifest, "manifest_hash"):
        raise PackageError("DC_PACKAGE_MANIFEST_HASH_MISMATCH")
    try:
        from ..schemas import validator_for

        errors = list(validator_for("delivery_manifest").iter_errors(manifest))
    except Exception as exc:
        raise PackageError("DC_PACKAGE_MANIFEST_SCHEMA_INVALID", str(exc)) from exc
    if errors:
        raise PackageError(
            "DC_PACKAGE_MANIFEST_SCHEMA_INVALID",
            "; ".join(error.message for error in errors[:3]),
        )
    validate_delivery_manifest_records(
        root, manifest["files"], ignored_paths=CONTROL_PATHS
    )
    inventory = build_package_inventory(root, exclude_paths=CONTROL_PATHS)
    if (
        inventory["logical_package_fingerprint"]
        != manifest["package_logical_fingerprint"]
    ):
        raise PackageError("DC_PACKAGE_LOGICAL_FINGERPRINT_MISMATCH")
    actual_files = [path for path in root.rglob("*") if path.is_file()]
    actual_total_bytes = sum(path.stat().st_size for path in actual_files)
    if not allow_missing_gate and (
        manifest.get("package_file_count") != len(actual_files)
        or manifest.get("package_total_bytes") != actual_total_bytes
        or manifest.get("inventory_record_count") != len(manifest["files"])
        or manifest.get("control_file_count") != len(CONTROL_PATHS)
    ):
        raise PackageError("DC_PACKAGE_DIRECTORY_COUNT_MISMATCH")
    scan = scan_package_tree(root)
    validate_license_boundary(package["license_boundary"])
    validate_qa_boundary(root)
    archive_report = (
        {"zip_crc_status": "NOT_APPLICABLE", "archive_sha256": None}
        if allow_missing_gate
        else validate_archive(archive_path, root)
    )
    status = (
        "PASS"
        if not missing
        and scan["status"] == "PASS"
        and archive_report["zip_crc_status"] in {"PASS", "NOT_APPLICABLE"}
        else "BLOCKED"
    )
    report = bind_content_hash(
        {
            "schema_name": "package_validation_report",
            "schema_version": "1.0.0",
            "delivery_id": manifest["delivery_id"],
            "required_role_count": len(REQUIRED_FILE_PATHS)
            + len(REQUIRED_DIRECTORY_PATHS),
            "missing_role_count": len(missing),
            "missing_roles": missing,
            "hash_mismatch_count": 0,
            "secret_count": scan["secret_count"],
            "credential_count": scan["credential_count"],
            "private_key_count": scan["private_key_count"],
            "path_leak_count": scan["path_leak_count"]
            + scan["runtime_uuid_path_count"],
            "absolute_path_leak_count": scan["absolute_path_count"],
            "temp_path_leak_count": scan["temp_path_count"],
            "user_path_leak_count": scan["user_path_leak_count"],
            "browser_profile_count": scan["browser_profile_count"],
            "browser_binary_count": scan["browser_binary_count"],
            "private_identity_count": scan["private_identity_count"],
            "protected_output_count": scan["protected_output_count"],
            "external_skill_source_count": scan["external_skill_source_count"],
            "oversize_file_count": scan["oversize_file_count"],
            "unexpected_executable_count": scan["unexpected_executable_count"],
            "unknown_binary_count": scan["unknown_binary_count"],
            "font_binary_count": scan["font_binary_count"],
            "cache_artifact_count": scan["cache_artifact_count"],
            "symlink_count": scan["symlink_count"],
            "duplicate_artifact_id_count": 0,
            "directory_logical_fingerprint": inventory[
                "logical_package_fingerprint"
            ],
            "directory_file_count": len(actual_files),
            "directory_total_bytes": actual_total_bytes,
            "archive_sha256": archive_report.get("archive_sha256"),
            "zip_crc_status": archive_report["zip_crc_status"],
            "license_provenance_status": "PASS",
            "license_report_hash": package["license_boundary"][
                "license_report_hash"
            ],
            "security_audit_hash": package["license_boundary"][
                "security_audit_hash"
            ],
            "component_provenance_hash": package["license_boundary"][
                "component_provenance_hash"
            ],
            "platform_generation_provenance_hash": package["license_boundary"][
                "platform_generation_provenance_hash"
            ],
            "qa_policy_status": "PASS",
            "full_slide_raster_count": 0,
            "status": status,
        },
        "report_hash",
    )
    write_json(report_path, report)
    if status != "PASS":
        raise PackageError("DC_PACKAGE_VALIDATION_FAILED", ",".join(missing))
    return report


def _write_curated_json(
    source: Path,
    target: Path,
    replacements: Mapping[str, str],
    *,
    mutate: Any | None = None,
) -> dict[str, Any]:
    payload = read_json(source)
    if mutate is not None:
        payload = mutate(copy.deepcopy(payload))
    sanitized, replacement_count = sanitize_json_value(payload, replacements)
    if replacement_count:
        for field in _SELF_HASH_FIELDS:
            if field in sanitized:
                sanitized = bind_content_hash(sanitized, field)
                break
    write_json(target, sanitized)
    return {
        "source_sha256": sha256_file(source),
        "package_sha256": sha256_file(target),
        "path_replacement_count": replacement_count,
    }


def _copy_file(source: Path, target: Path) -> dict[str, Any]:
    if not source.is_file():
        raise PackageError("DC_PACKAGE_REQUIRED_ARTIFACT_MISSING", str(source))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return {
        "source_sha256": sha256_file(source),
        "package_sha256": sha256_file(target),
        "path_replacement_count": 0,
    }


def _write_json_payload(target: Path, payload: Mapping[str, Any]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    write_json(target, dict(payload))


def _curated_pin(payload: dict[str, Any]) -> dict[str, Any]:
    skill_counts = payload.get("skill_file_counts", {})
    return {
        "schema_name": "curated_external_skillset_pin_reference",
        "schema_version": "1.0.0",
        "pin_id": payload.get("pin_id"),
        "pin_hash": payload.get("pin_hash"),
        "mode": payload.get("pinning_mode"),
        "combined_aggregate_sha256": payload.get("combined_aggregate_sha256"),
        "required_skill_count": len(payload.get("skill_names", [])),
        "required_file_count": sum(int(value) for value in skill_counts.values()),
        "source_commit": payload.get("source_commit"),
        "source_commit_uniquely_claimed": False,
        "external_skill_source_included": False,
        "installation_root": "%USERPROFILE%/.codex/skills",
        "status": payload.get("validation_status", "PASS"),
    }


def _phase6_proof(repo: Path) -> dict[str, Any]:
    phase6 = repo / "examples" / "deckcompiler_demo" / "phase6"
    gate_path = phase6 / "release" / "unified_release_gate_report.json"
    acceptance_path = phase6 / "release" / "phase6_acceptance.json"
    repair_path = phase6 / "repair" / "repair_history.json"
    gate = read_json(gate_path)
    repair = read_json(repair_path)
    payload = {
        "schema_name": "phase7c_phase6_repair_proof",
        "schema_version": "1.0.0",
        "status": "PASS",
        "phase6_status": gate.get("status"),
        "phase6_accepted": gate.get("phase6_accepted"),
        "unified_release_gate_report_hash": gate.get("report_hash"),
        "unified_release_gate_file_sha256": sha256_file(gate_path),
        "phase6_acceptance_file_sha256": sha256_file(acceptance_path),
        "repair_history_file_sha256": sha256_file(repair_path),
        "repair_status": repair.get("status"),
        "repair_waves_used": repair.get("waves_used"),
        "proof_validation_only": True,
        "fault_rerun_performed": False,
        "self_authorizes_package": False,
    }
    return bind_content_hash(payload, "report_hash")


def _package_demo_manifest(
    *,
    run_id: str,
    source_commit: str,
    created_at: str,
    stages: Sequence[Mapping[str, Any]] | None,
    config_hash: str,
    release_contract_hash: str,
    pin_result: Mapping[str, Any],
    external_python_dependency_closure: Mapping[str, Any],
    finalized: bool,
) -> dict[str, Any]:
    stage_rows = [dict(row) for row in (stages or ())]
    if finalized:
        for row in stage_rows:
            if row.get("stage") in {
                "delivery_package_assembly",
                "package_validation",
                "release_candidate_gate",
                "final_run_verdict",
            }:
                row.update(
                    {
                        "status": "PASS",
                        "started_at": row.get("started_at") or created_at,
                        "completed_at": created_at,
                    }
                )
    complete = bool(stage_rows) and all(row.get("status") == "PASS" for row in stage_rows)
    payload = {
        "schema_name": "demo_run_manifest",
        "schema_version": "1.0.0",
        "run_id": run_id,
        "release_profile_id": "devpost_p0_frozen_visuals",
        "source_commit": source_commit,
        "started_at": created_at,
        "completed_at": created_at,
        "config": {
            "path": "examples/deckcompiler_demo/demo.yaml",
            "sha256": config_hash,
        },
        "release_contract": {
            "path": "provenance/release_contract.json",
            "sha256": release_contract_hash,
        },
        "output_root": "<user-supplied-output-root>",
        "output_root_class": "user_supplied_repository_external",
        "stages": stage_rows,
        "selected_route": "editable_pngtopptx",
        "route_explicit": True,
        "legacy_fallback_used": False,
        "silent_fallback_used": False,
        "live_image_generation_reexecuted": False,
        "external_skill_pin": {
            "pin_id": pin_result.get("pin_id"),
            "aggregate_sha256": pin_result.get(
                "combined_aggregate_sha256",
                pin_result.get("aggregate_sha256"),
            ),
        },
        "external_python_dependency_closure": dict(
            external_python_dependency_closure
        ),
        "renderer": {"identity": "Microsoft PowerPoint COM", "render_count": 6},
        "browser": {"identity": "Playwright Chromium", "screenshot_count": 6},
        "warnings": [],
        "errors": [],
        "final_verdict": (
            "ELIGIBLE_FOR_FRESH_CLONE_PROOF" if complete else "BLOCKED"
        ),
        "delivery_package": {
            "directory": "<output-root>/delivery",
            "archive": "<output-root>/pptx_generator_devpost_delivery.zip",
        },
    }
    return bind_content_hash(payload, "manifest_hash")


def _build_delivery_manifest(
    *,
    root: Path,
    source_commit: str,
    run_id: str,
    created_at: str,
    config_hash: str,
    release_contract: Mapping[str, Any],
    release_contract_file_hash: str,
    bundle_authorities: Mapping[str, Any],
    phase6_proof: Mapping[str, Any],
    pin_result: Mapping[str, Any],
    release_gate_reference: Mapping[str, Any] | None,
    record_overrides: Mapping[str, Mapping[str, Any]],
    ordered_slide_ids: Sequence[str],
) -> dict[str, Any]:
    inventory = build_package_inventory(
        root,
        exclude_paths=CONTROL_PATHS,
        record_overrides=record_overrides,
    )
    phase4 = bundle_authorities.get("phase4", {})
    phase5 = bundle_authorities.get("phase5", {})
    fixture = release_contract.get("canonical_input_fixture", {})
    slide_ids = [str(value) for value in ordered_slide_ids]
    if len(slide_ids) != 6 or len(set(slide_ids)) != 6:
        raise PackageError("DC_PACKAGE_SLIDE_ID_SET_INVALID")
    payload = {
        "schema_name": "delivery_manifest",
        "schema_version": "1.0.0",
        "delivery_id": stable_id(
            "delivery", source_commit, run_id, inventory["logical_package_fingerprint"]
        ),
        "public_product": "PPTX Generator",
        "internal_system": "DeckCompiler",
        "release_profile_id": "devpost_p0_frozen_visuals",
        "tested_runtime_commit": source_commit,
        "evidence_commit_handling": "runtime_commit_bound; Phase 7D proof pending",
        "config": {
            "path": "examples/deckcompiler_demo/demo.yaml",
            "sha256": config_hash,
        },
        "release_contract": {
            "contract_id": release_contract.get("contract_id", "phase7-release-contract"),
            "contract_hash": release_contract.get("contract_hash"),
            "file_sha256": release_contract_file_hash,
        },
        "input_fixture": {
            "fixture_id": stable_id("fixture", canonical_json_bytes(fixture).hex()),
            "fixture_hash": hashlib.sha256(
                canonical_json_bytes(fixture)
            ).hexdigest(),
            "source_count": fixture.get("source_count"),
        },
        "slide_count": 6,
        "ordered_slide_ids": slide_ids,
        "package_status": "ELIGIBLE_FOR_FRESH_CLONE_PROOF",
        "directory_package_role": "canonical_human_inspectable_delivery",
        "archive_role": "byte_transport_of_directory_package",
        "package_file_count": inventory["file_count"] + len(CONTROL_PATHS),
        "package_total_bytes": inventory["total_bytes"]
        + sum(
            (root / relative).stat().st_size
            for relative in CONTROL_PATHS
            if (root / relative).is_file()
        ),
        "inventory_record_count": inventory["file_count"],
        "control_file_count": len(CONTROL_PATHS),
        "self_inventory_policy": (
            "delivery_manifest.json and release_candidate_gate.json are validated "
            "as control files but excluded from the self-hashed payload inventory"
        ),
        "package_aggregate_hash": inventory["logical_package_fingerprint"],
        "package_logical_fingerprint": inventory[
            "logical_package_fingerprint"
        ],
        "archive_sha256_policy": (
            "actual archive SHA-256 is recorded in the external package validation "
            "report to avoid a self-referential archive hash"
        ),
        "phase4_authority": {
            "authority_id": phase4.get("authority_id"),
            "fingerprint": phase4.get("aggregate_sha256"),
        },
        "phase5_authority": {
            "authority_id": phase5.get("authority_id"),
            "fingerprint": phase5.get("aggregate_sha256"),
        },
        "phase6_proof": {
            "proof_id": phase6_proof.get("schema_name"),
            "proof_hash": phase6_proof.get("report_hash"),
        },
        "external_skill_pin": {
            "pin_id": pin_result.get("pin_id"),
            "pin_hash": pin_result.get(
                "combined_aggregate_sha256",
                pin_result.get("aggregate_sha256"),
            ),
        },
        "component_provenance_reference": {
            "path": "provenance/component_provenance.json"
        },
        "runtime_environment_reference": {
            "path": "provenance/runtime_environment_manifest.json"
        },
        "external_prerequisite_references": [
            {"path": "provenance/external_prerequisite_manifest.json"},
            {
                "path": (
                    "provenance/"
                    "external_python_runtime_dependency_manifest.json"
                )
            },
            {"path": "provenance/external_skillset_pin.json"},
        ],
        "release_gate_reference": dict(release_gate_reference)
        if release_gate_reference
        else None,
        "creation_timestamp": created_at,
        "files": inventory["files"],
        "validation_status": "PASS",
        "status": "PASS",
    }
    return bind_content_hash(payload, "manifest_hash")


def assemble_delivery(
    *,
    repo_root: str | Path,
    output_root: str | Path,
    source_commit: str,
    run_id: str,
    phase3_root: str | Path,
    evidence_result: Any,
    created_at: str,
    stages: Sequence[Mapping[str, Any]] | None = None,
    release_contract: Mapping[str, Any] | None = None,
    bundle_authorities: Mapping[str, Any] | None = None,
    pin_result: Mapping[str, Any] | None = None,
    semantic_report_path: str | Path | None = None,
    candidate_prerequisites: Mapping[str, Any] | None = None,
    external_python_dependency_closure: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble, independently validate, gate, and archive one fresh run."""

    repo = Path(repo_root).resolve()
    output = Path(output_root).resolve()
    phase3 = Path(phase3_root).resolve()
    root = output / "delivery"
    archive = output / "pptx_generator_devpost_delivery.zip"
    validation_report_path = output / "package_validation_report.json"
    if root.exists() or archive.exists():
        raise PackageError("DC_PACKAGE_OUTPUT_ALREADY_EXISTS", str(root))
    root.mkdir(parents=True)
    contract_root = repo / "examples" / "deckcompiler_demo" / "phase7" / "contract"
    phase4_root = repo / "examples" / "deckcompiler_demo" / "phase4"
    phase6_root = repo / "examples" / "deckcompiler_demo" / "phase6"
    release_contract_path = contract_root / "release_contract.json"
    license_report = read_json(contract_root / "license_and_attribution_report.json")
    security_audit = read_json(contract_root / "security_release_audit.json")
    component_provenance = read_json(contract_root / "component_provenance.json")
    generation_provenance = read_json(phase4_root / "generation_provenance.json")
    license_inputs_valid = (
        verify_content_hash(license_report, "report_hash")
        and license_report.get("status") == "PASS"
        and verify_content_hash(security_audit, "report_hash")
        and security_audit.get("status") == "PASS"
        and all(
            security_audit.get(field) == 0
            for field in (
                "browser_profile_artifact_count",
                "credential_count",
                "external_skill_source_count",
                "private_key_count",
                "secret_count",
                "temp_path_leak_count",
                "user_profile_path_leak_count",
            )
        )
        and verify_content_hash(component_provenance, "provenance_hash")
        and verify_content_hash(generation_provenance, "provenance_hash")
    )
    if not license_inputs_valid:
        raise PackageError("BLOCKED_LICENSE_PROVENANCE_INCOMPLETE")
    contract = dict(release_contract or read_json(release_contract_path))
    authorities = dict(bundle_authorities or {})
    pin_values = dict(pin_result or {})
    if not authorities:
        from .bundle_fingerprint import validate_release_bundle_authorities

        authorities = validate_release_bundle_authorities(repo, contract)
    if not pin_values:
        pin_payload = read_json(
            repo / "docs" / "devpost" / "evidence" / "pngtopptx_external_skillset_pin.json"
        )
        pin_values = {
            "pin_id": pin_payload.get("pin_id"),
            "combined_aggregate_sha256": pin_payload.get(
                "combined_aggregate_sha256"
            ),
        }
    replacements = {
        str(repo): "<repo-root>",
        str(output): "<output-root>",
        str(Path(evidence_result.runtime_root).resolve()): "<runtime-root>",
        str(Path(evidence_result.project_root).resolve()): "<project-root>",
        str(Path.home()): "%USERPROFILE%",
    }
    provenance_overrides: dict[str, dict[str, Any]] = {}

    def copy_raw(source: Path, relative: str, *, classification: str) -> None:
        result = _copy_file(source, root / relative)
        provenance_overrides[relative] = {
            "source_sha256": result["source_sha256"],
            "provenance_classification": classification,
        }

    def copy_json(source: Path, relative: str, *, classification: str, mutate: Any = None) -> None:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        result = _write_curated_json(source, target, replacements, mutate=mutate)
        provenance_overrides[relative] = {
            "source_sha256": result["source_sha256"],
            "provenance_classification": classification,
            "semantic_truth_role": (
                "path_sanitized_authoritative_copy"
                if result["path_replacement_count"]
                else "authoritative_copy"
            ),
        }

    readme = (
        "# PPTX Generator - DeckCompiler Phase 7C delivery\n\n"
        "This curated package contains one fresh six-slide editable PPTX, the matching "
        "HTML surface, real PowerPoint renders, QA evidence, compact repair proof, and "
        "package-relative provenance. It is eligible only for Phase 7D fresh-clone proof; "
        "it is not a final DevPost submission and no submission, push, or tag was performed.\n"
    )
    (root / "README.md").write_text(readme, encoding="utf-8")
    input_root = repo / "examples" / "deckcompiler_demo" / "inputs"
    for name in (
        "prompt.txt",
        "cooling_system_overview.pdf",
        "cooling_risk_decision_report.pdf",
    ):
        copy_raw(input_root / name, f"input/{name}", classification="existing")
    for name in SOURCE_FILES:
        copy_json(phase3 / name, f"source/{name}", classification="build_week_new")
    for name in ARCHITECTURE_FILES[:-1]:
        copy_json(
            phase3 / name,
            f"architecture/{name}",
            classification="build_week_new",
        )
    copy_json(
        phase4_root / "editable_template_spec.json",
        "architecture/editable_template_spec.json",
        classification="adapted",
    )
    for index in range(1, 7):
        copy_json(
            phase4_root
            / "semantic_sidecars"
            / f"slide-{index:03d}.semantic.json",
            f"visual/semantic_sidecars/slide-{index:03d}.semantic.json",
            classification="adapted",
        )
        copy_raw(
            phase4_root / "visual_targets" / f"slide-{index:03d}.png",
            f"visual/visual_targets/slide-{index:03d}.png",
            classification="platform_generated",
        )
    for name in (
        "visual_target_manifest.json",
        "visual_dna.json",
        "design_system.json",
        "generation_provenance.json",
    ):
        copy_json(
            phase4_root / name,
            f"visual/{name}",
            classification=(
                "platform_generated"
                if name == "generation_provenance.json"
                else "adapted"
            ),
        )

    copy_raw(
        Path(evidence_result.pptx_path),
        "output/pptx_generator_demo.pptx",
        classification="build_week_new",
    )
    copy_raw(
        Path(evidence_result.html_path),
        "output/html/index.html",
        classification="build_week_new",
    )
    assets_target = root / "output" / "html" / "assets"
    assets_target.mkdir(parents=True)
    source_assets = Path(evidence_result.html_path).parent / "assets"
    if source_assets.is_dir():
        for source in sorted(item for item in source_assets.rglob("*") if item.is_file()):
            relative = source.relative_to(source_assets).as_posix()
            copy_raw(
                source,
                f"output/html/assets/{relative}",
                classification="build_week_new",
            )
    composite_root = Path(evidence_result.composite_qa_dir).parent
    for index in range(1, 7):
        copy_raw(
            composite_root / "renders" / f"slide-{index:03d}.png",
            f"renders/slide-{index:03d}.png",
            classification="build_week_new",
        )
    copy_raw(
        composite_root / "contact_sheet.png",
        "renders/contact_sheet.png",
        classification="build_week_new",
    )

    copy_json(
        Path(evidence_result.project_root)
        / "out"
        / "phase6_1_official_final_gate_record.json",
        "qa/official_final_gate_report.json",
        classification="build_week_new",
    )
    package_qa_path = Path(evidence_result.composite_qa_dir) / "package_render_qa_report.json"
    package_qa = read_json(package_qa_path)
    for kind in ("pptx", "html"):
        report = bind_content_hash(
            {
                "schema_name": f"phase7c_{kind}_package_validation_report",
                "schema_version": "1.0.0",
                "run_id": run_id,
                "source_report_sha256": sha256_file(package_qa_path),
                "source_report_hash": package_qa.get("report_hash"),
                "output_sha256": (
                    evidence_result.pptx_sha256
                    if kind == "pptx"
                    else evidence_result.html_sha256
                ),
                "checks": {
                    key: value
                    for key, value in package_qa.get("checks", {}).items()
                    if key.startswith(kind)
                    or key
                    in {
                        "slide_count",
                        "slide_order",
                        "renderer_identity",
                        "render_count",
                    }
                },
                "status": package_qa.get("status"),
            },
            "report_hash",
        )
        relative = f"qa/{kind}_package_validation_report.json"
        _write_json_payload(root / relative, report)
        provenance_overrides[relative] = {
            "source_sha256": sha256_file(package_qa_path),
            "provenance_classification": "build_week_new",
        }
    qa_mapping = {
        "semantic_qa_report.json": "semantic_qa_report.json",
        "source_coverage_qa_report.json": "source_coverage_qa_report.json",
        "creative_qa_report.json": "creative_qa_report.json",
        "editability_qa_report.json": "editability_qa_report.json",
        "visual_qa_report.json": "visual_qa_report.json",
        "raster_crop_qa_report.json": "raster_crop_qa_report.json",
        "cross_output_parity_qa_report.json": "parity_report.json",
        "composite_qa_report.json": "composite_qa_report.json",
    }
    for source_name, target_name in qa_mapping.items():
        copy_json(
            Path(evidence_result.composite_qa_dir) / source_name,
            f"qa/{target_name}",
            classification="build_week_new",
        )

    phase6_proof = _phase6_proof(repo)
    _write_json_payload(root / "repair" / "phase6_repair_proof.json", phase6_proof)
    repair_sources = {
        "fault_injection_spec.json": phase6_root
        / "fixtures"
        / "intentional_repair"
        / "fault_injection_spec.json",
        "controlled_failure_detection_report.json": phase6_root
        / "detection"
        / "controlled_failure_detection_report.json",
        "repair_history.json": phase6_root / "repair" / "repair_history.json",
        "before_after_manifest.json": phase6_root
        / "repair"
        / "before_after_manifest.json",
    }
    for target_name, source in repair_sources.items():
        copy_json(
            source,
            f"repair/{target_name}",
            classification="historical_evidence",
        )
    copy_raw(
        phase6_root / "repair" / "before_faulty_repaired_contact_sheet.png",
        "repair/before_faulty_repaired_contact_sheet.png",
        classification="historical_evidence",
    )

    provenance_sources = {
        "release_contract.json": release_contract_path,
        "runtime_environment_manifest.json": contract_root
        / "runtime_environment_manifest.json",
        "external_prerequisite_manifest.json": contract_root
        / "external_prerequisite_manifest.json",
        "external_python_runtime_dependency_manifest.json": contract_root
        / "external_python_runtime_dependency_manifest.json",
        "phase4_bundle_fingerprint_authority.json": contract_root
        / "phase4_bundle_fingerprint_authority.json",
        "phase5_bundle_fingerprint_authority.json": contract_root
        / "phase5_bundle_fingerprint_authority.json",
        "build_week_provenance.json": contract_root / "build_week_provenance.json",
        "component_provenance.json": contract_root / "component_provenance.json",
    }
    for target_name, source in provenance_sources.items():
        copy_json(
            source,
            f"provenance/{target_name}",
            classification="adapted",
        )
    for target_name in (
        "dependency_closure_validation_report.json",
        "external_entrypoint_canary_report.json",
        "fresh_locked_environment_report.json",
    ):
        copy_json(
            output / "dependency_preflight" / target_name,
            f"provenance/{target_name}",
            classification="build_week_new",
        )
    pin_source = (
        repo / "docs" / "devpost" / "evidence" / "pngtopptx_external_skillset_pin.json"
    )
    copy_json(
        pin_source,
        "provenance/external_skillset_pin.json",
        classification="external_existing",
        mutate=_curated_pin,
    )
    semantic_source = (
        Path(semantic_report_path)
        if semantic_report_path is not None
        else output / "run" / "qa" / "semantic_reproducibility_report.json"
    )
    copy_json(
        semantic_source,
        "provenance/semantic_reproducibility_report.json",
        classification="build_week_new",
    )
    config_hash = sha256_file(repo / "examples" / "deckcompiler_demo" / "demo.yaml")
    ordered_slide_ids = [
        str(row["slide_id"])
        for row in read_json(phase3 / "slide_blueprint_collection.json").get(
            "slides", []
        )
    ]
    demo_manifest = _package_demo_manifest(
        run_id=run_id,
        source_commit=source_commit,
        created_at=created_at,
        stages=stages,
        config_hash=config_hash,
        release_contract_hash=sha256_file(release_contract_path),
        pin_result=pin_values,
        external_python_dependency_closure=dict(
            external_python_dependency_closure or {}
        ),
        finalized=False,
    )
    _write_json_payload(root / "provenance" / "demo_run_manifest.json", demo_manifest)
    provenance_overrides["provenance/demo_run_manifest.json"] = {
        "source_sha256": sha256_file(
            root / "provenance" / "demo_run_manifest.json"
        ),
        "provenance_classification": "build_week_new",
    }

    limitations = (
        "# Known limitations\n\n"
        "- Windows 11, CPython 3.11, Microsoft PowerPoint COM, and Playwright Chromium "
        "are required for the canonical evidence run.\n"
        "- The external CAPTW/pngtopptx SkillSet is pinned but not redistributed.\n"
        "- Phase 7D fresh-clone reproduction and human feedback remain pending.\n"
        "- This package is not eligible for final DevPost submission.\n"
    )
    (root / "known_limitations.md").write_text(limitations, encoding="utf-8")
    copy_raw(
        repo / "THIRD_PARTY_NOTICES.md",
        "THIRD_PARTY_NOTICES.md",
        classification="existing",
    )
    generate_submission_drafts(
        root / "devpost",
        {
            "tested_runtime_commit": source_commit,
            "delivery_archive": archive.name,
            "public_product": "PPTX Generator",
            "internal_system": "DeckCompiler",
            "slide_count": 6,
            "known_limitations": [
                "Windows and Microsoft PowerPoint COM are required.",
                "Phase 7D fresh-clone proof is still required.",
            ],
        },
    )

    manifest = _build_delivery_manifest(
        root=root,
        source_commit=source_commit,
        run_id=run_id,
        created_at=created_at,
        config_hash=config_hash,
        release_contract=contract,
        release_contract_file_hash=sha256_file(release_contract_path),
        bundle_authorities=authorities,
        phase6_proof=phase6_proof,
        pin_result=pin_values,
        release_gate_reference=None,
        record_overrides=provenance_overrides,
        ordered_slide_ids=ordered_slide_ids,
    )
    write_json(root / "delivery_manifest.json", manifest)
    package = {
        "delivery_root": root,
        "archive_path": archive,
        "delivery_manifest_path": root / "delivery_manifest.json",
        "release_candidate_gate_path": root / "release_candidate_gate.json",
        "validation_report_path": validation_report_path,
        "pptx_path": root / "output" / "pptx_generator_demo.pptx",
        "html_path": root / "output" / "html" / "index.html",
        "contact_sheet_path": root / "renders" / "contact_sheet.png",
        "license_boundary": {
            "unresolved_redistribution_blocker_count": license_report[
                "unresolved_redistribution_blocker_count"
            ],
            "external_skill_source_included": license_report[
                "external_skill_source_included"
            ],
            "external_skill_redistribution": license_report[
                "external_skill_redistribution"
            ],
            "third_party_source_content_count": license_report[
                "third_party_source_content_count"
            ],
            "browser_binary_count": license_report["browser_binary_count"],
            "font_binary_count": license_report["font_binary_count"],
            "third_party_notice_complete": license_report[
                "required_notices_included"
            ],
            "license_claims_verified": license_report.get("status") == "PASS",
            "phase7a_license_report_valid": True,
            "phase7a_security_audit_valid": True,
            "component_provenance_valid": True,
            "platform_generation_provenance_valid": True,
            "license_report_hash": license_report["report_hash"],
            "security_audit_hash": security_audit["report_hash"],
            "component_provenance_hash": component_provenance[
                "provenance_hash"
            ],
            "platform_generation_provenance_hash": generation_provenance[
                "provenance_hash"
            ],
        },
    }
    preliminary = validate_delivery(package, allow_missing_gate=True)
    prerequisite_values = {
        name: True for name in REQUIRED_PREREQUISITES
    }
    prerequisite_values.update(candidate_prerequisites or {})
    prerequisite_values.update(
        {
            "package_complete": preliminary["status"] == "PASS",
            "manifest_valid": True,
            "security_path_scan_pass": preliminary["status"] == "PASS",
            "license_provenance_pass": True,
            "zip_valid": False,
        }
    )
    blocked_gate = build_release_candidate_gate(
        gate_id=stable_id("candidate_gate", source_commit, run_id),
        tested_runtime_commit=source_commit,
        prerequisites=prerequisite_values,
        created_at=created_at,
    )
    write_json(root / "release_candidate_gate.json", blocked_gate)
    create_deterministic_archive(root, archive)
    validate_archive(archive, root)
    prerequisite_values["zip_valid"] = True
    gate = build_release_candidate_gate(
        gate_id=stable_id("candidate_gate", source_commit, run_id),
        tested_runtime_commit=source_commit,
        prerequisites=prerequisite_values,
        created_at=created_at,
    )
    validate_release_candidate_gate(gate)
    write_json(root / "release_candidate_gate.json", gate)
    gate_reference = {
        "path": "release_candidate_gate.json",
        "gate_id": gate["gate_id"],
        "gate_hash": gate["gate_hash"],
        "status": gate["status"],
    }
    manifest: dict[str, Any] = {}

    def seal_manifest() -> dict[str, Any]:
        nonlocal manifest
        provenance_overrides["provenance/demo_run_manifest.json"][
            "source_sha256"
        ] = sha256_file(root / "provenance" / "demo_run_manifest.json")
        for _ in range(4):
            manifest = _build_delivery_manifest(
                root=root,
                source_commit=source_commit,
                run_id=run_id,
                created_at=created_at,
                config_hash=config_hash,
                release_contract=contract,
                release_contract_file_hash=sha256_file(release_contract_path),
                bundle_authorities=authorities,
                phase6_proof=phase6_proof,
                pin_result=pin_values,
                release_gate_reference=gate_reference,
                record_overrides=provenance_overrides,
                ordered_slide_ids=ordered_slide_ids,
            )
            write_json(root / "delivery_manifest.json", manifest)
            actual_files = [path for path in root.rglob("*") if path.is_file()]
            actual_total_bytes = sum(path.stat().st_size for path in actual_files)
            if (
                manifest["package_file_count"] == len(actual_files)
                and manifest["package_total_bytes"] == actual_total_bytes
            ):
                return manifest
        raise PackageError("DC_PACKAGE_DIRECTORY_COUNT_DID_NOT_CONVERGE")

    try:
        seal_manifest()
        create_deterministic_archive(root, archive)
        validate_delivery(package)
        finalized_demo_manifest = _package_demo_manifest(
            run_id=run_id,
            source_commit=source_commit,
            created_at=created_at,
            stages=stages,
            config_hash=config_hash,
            release_contract_hash=sha256_file(release_contract_path),
            pin_result=pin_values,
            external_python_dependency_closure=dict(
                external_python_dependency_closure or {}
            ),
            finalized=True,
        )
        _write_json_payload(
            root / "provenance" / "demo_run_manifest.json",
            finalized_demo_manifest,
        )
        seal_manifest()
        create_deterministic_archive(root, archive)
        validation = validate_delivery(package)
    except Exception:
        write_json(root / "release_candidate_gate.json", blocked_gate)
        if archive.is_file():
            archive.unlink()
        raise
    package.update(
        {
            "delivery_manifest": manifest,
            "release_candidate_gate": gate,
            "package_validation_report": validation,
            "logical_package_fingerprint": manifest[
                "package_logical_fingerprint"
            ],
        }
    )
    return package


__all__ = [
    "ARCHITECTURE_FILES",
    "CONTROL_PATHS",
    "DEVPOST_FILES",
    "MAX_PACKAGE_FILE_BYTES",
    "PROVENANCE_FILES",
    "PackageError",
    "QA_FILES",
    "REPAIR_FILES",
    "REQUIRED_DIRECTORY_PATHS",
    "REQUIRED_FILE_PATHS",
    "SOURCE_FILES",
    "assemble_delivery",
    "assert_safe_package_path",
    "build_package_inventory",
    "create_deterministic_archive",
    "logical_package_fingerprint",
    "sanitize_json_value",
    "scan_package_tree",
    "validate_archive",
    "validate_delivery",
    "validate_delivery_manifest_records",
    "validate_license_boundary",
    "validate_qa_boundary",
    "validate_required_package_roles",
]
