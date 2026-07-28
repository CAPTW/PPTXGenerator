"""Checkout-independent bundle identity and checkout compatibility contracts.

``git_object_bundle_fingerprint_v1`` identifies a committed subtree from Git
objects only.  ``runtime_bundle_compatibility_v1`` is deliberately separate:
it establishes whether a particular materialized checkout is safe to execute.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from copy import deepcopy
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

from ..schemas import validator_for


GIT_OBJECT_FINGERPRINT_CONTRACT = "git_object_bundle_fingerprint_v1"
RUNTIME_COMPATIBILITY_CONTRACT = "runtime_bundle_compatibility_v1"
SUPPORTED_FILE_MODES = {"100644", "100755"}
BINARY_EXACT_EXTENSIONS = {
    ".docx",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".pptx",
    ".webp",
    ".xlsx",
    ".zip",
}
JSON_SEMANTIC_EXTENSIONS = {".json"}
TEXT_CLEAN_FILTER_EXTENSIONS = {
    ".css",
    ".html",
    ".js",
    ".md",
    ".ps1",
    ".py",
    ".txt",
    ".yaml",
    ".yml",
}
_HEX = re.compile(r"^[0-9a-f]+$")


class BundleFingerprintError(RuntimeError):
    """Stable fail-closed bundle-fingerprint failure."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def _git(
    repo: Path,
    *args: str,
    input_bytes: bytes | None = None,
    check: bool = True,
) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        input=input_bytes,
        capture_output=True,
        check=False,
    )
    if check and completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise BundleFingerprintError("GIT_OBJECT_ACCESS_FAILED", detail)
    return completed.stdout


def _git_text(repo: Path, *args: str, check: bool = True) -> str:
    return _git(repo, *args, check=check).decode("utf-8", errors="strict").strip()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _normalize_relative_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    candidate = PurePosixPath(normalized)
    if (
        not normalized
        or candidate.is_absolute()
        or normalized.startswith("/")
        or any(part in {"", ".", ".."} for part in candidate.parts)
    ):
        raise BundleFingerprintError("BUNDLE_PATH_OUTSIDE_SUBTREE", value)
    return candidate.as_posix()


def _validate_hex(value: Any, lengths: set[int]) -> bool:
    return (
        isinstance(value, str)
        and len(value) in lengths
        and _HEX.fullmatch(value) is not None
    )


def fingerprint_records(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Normalize, validate, sort, and fingerprint Git-blob identity records."""

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in records:
        path = _normalize_relative_path(str(source.get("path", "")))
        if path in seen:
            raise BundleFingerprintError("DUPLICATE_BUNDLE_PATH", path)
        seen.add(path)
        mode = str(source.get("mode", ""))
        if mode == "120000":
            raise BundleFingerprintError("SYMLINK_ENTRY_FORBIDDEN", path)
        if mode == "160000":
            raise BundleFingerprintError("SUBMODULE_ENTRY_FORBIDDEN", path)
        if mode not in SUPPORTED_FILE_MODES:
            raise BundleFingerprintError("UNSUPPORTED_FILE_MODE", f"{path}: {mode}")
        blob_oid = source.get("blob_oid")
        blob_sha256 = source.get("blob_sha256")
        if not _validate_hex(blob_oid, {40, 64}):
            raise BundleFingerprintError("MISSING_BLOB", path)
        if not _validate_hex(blob_sha256, {64}):
            raise BundleFingerprintError("MISSING_BLOB_SHA256", path)
        byte_size = source.get("byte_size")
        if not isinstance(byte_size, int) or isinstance(byte_size, bool) or byte_size < 0:
            raise BundleFingerprintError("INVALID_BLOB_SIZE", path)
        normalized.append(
            {
                "path": path,
                "mode": mode,
                "blob_oid": blob_oid,
                "byte_size": byte_size,
                "blob_sha256": blob_sha256,
            }
        )
    normalized.sort(key=lambda row: row["path"])
    serialized = _canonical_json_bytes(normalized)
    paths = [row["path"] for row in normalized]
    return {
        "algorithm": GIT_OBJECT_FINGERPRINT_CONTRACT,
        "record_ordering": "unicode_code_point_ordinal_over_normalized_posix_paths",
        "serialization": "compact_sorted_key_json_utf8_no_bom_no_trailing_newline",
        "records": normalized,
        "aggregate_sha256": _sha256(serialized),
        "path_set_sha256": _sha256(_canonical_json_bytes(paths)),
        "file_count": len(normalized),
        "total_blob_bytes": sum(row["byte_size"] for row in normalized),
    }


def _resolve_commit(repo: Path, commit: str) -> str:
    resolved = _git_text(repo, "rev-parse", "--verify", f"{commit}^{{commit}}")
    if not _validate_hex(resolved, {40, 64}):
        raise BundleFingerprintError("GIT_COMMIT_IDENTITY_INVALID", resolved)
    return resolved


def build_git_object_bundle_fingerprint(
    repo: Path | str,
    commit: str,
    subtree: str,
) -> dict[str, Any]:
    """Build a bundle identity using only the selected commit's Git objects."""

    repo_path = Path(repo).resolve()
    subtree_path = _normalize_relative_path(subtree)
    source_commit = _resolve_commit(repo_path, commit)
    tree_oid = _git_text(
        repo_path, "rev-parse", "--verify", f"{source_commit}:{subtree_path}"
    )
    object_type = _git_text(repo_path, "cat-file", "-t", tree_oid)
    if object_type != "tree":
        raise BundleFingerprintError("BUNDLE_SUBTREE_NOT_TREE", subtree_path)

    raw = _git(
        repo_path,
        "ls-tree",
        "-r",
        "-z",
        "--full-tree",
        source_commit,
        "--",
        subtree_path,
    )
    prefix = f"{subtree_path}/"
    records: list[dict[str, Any]] = []
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        header, separator, raw_path = entry.partition(b"\t")
        if not separator:
            raise BundleFingerprintError("GIT_TREE_ENTRY_INVALID", repr(entry))
        parts = header.decode("ascii").split(" ")
        if len(parts) != 3:
            raise BundleFingerprintError("GIT_TREE_ENTRY_INVALID", repr(entry))
        mode, object_kind, oid = parts
        full_path = raw_path.decode("utf-8", errors="strict").replace("\\", "/")
        if not full_path.startswith(prefix):
            raise BundleFingerprintError("BUNDLE_PATH_OUTSIDE_SUBTREE", full_path)
        relative = _normalize_relative_path(full_path[len(prefix) :])
        if mode == "120000":
            raise BundleFingerprintError("SYMLINK_ENTRY_FORBIDDEN", relative)
        if mode == "160000" or object_kind == "commit":
            raise BundleFingerprintError("SUBMODULE_ENTRY_FORBIDDEN", relative)
        if object_kind != "blob":
            raise BundleFingerprintError(
                "UNSUPPORTED_GIT_OBJECT_TYPE", f"{relative}: {object_kind}"
            )
        blob = _git(repo_path, "cat-file", "blob", oid)
        records.append(
            {
                "path": relative,
                "mode": mode,
                "blob_oid": oid,
                "byte_size": len(blob),
                "blob_sha256": _sha256(blob),
            }
        )
    result = fingerprint_records(records)
    result.update(
        {
            "source_commit": source_commit,
            "subtree_path": subtree_path,
            "subtree_tree_oid": tree_oid,
        }
    )
    return result


def _reject_duplicate_object_pairs(
    pairs: Sequence[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise BundleFingerprintError("DUPLICATE_JSON_KEY", key)
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise BundleFingerprintError("JSON_NONFINITE_NUMBER", value)


def _canonical_decimal(value: Decimal) -> str:
    if not value.is_finite():
        raise BundleFingerprintError("JSON_NONFINITE_NUMBER", str(value))
    if value == 0:
        return "0"
    rendered = format(value.normalize(), "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def _canonical_json_semantic_text(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, Decimal):
        return _canonical_decimal(value)
    if isinstance(value, list):
        return "[" + ",".join(_canonical_json_semantic_text(item) for item in value) + "]"
    if isinstance(value, dict):
        return (
            "{"
            + ",".join(
                f"{json.dumps(key, ensure_ascii=False)}:"
                f"{_canonical_json_semantic_text(value[key])}"
                for key in sorted(value)
            )
            + "}"
        )
    raise BundleFingerprintError("JSON_VALUE_UNSUPPORTED", type(value).__name__)


def canonical_json_semantic_sha256(data: bytes) -> str:
    """Hash deterministic semantic JSON, rejecting duplicates and non-finite values."""

    try:
        text = data.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            parse_float=Decimal,
            parse_int=Decimal,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_reject_duplicate_object_pairs,
        )
    except BundleFingerprintError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BundleFingerprintError("JSON_PARSE_FAILURE", str(exc)) from exc
    return _sha256(_canonical_json_semantic_text(value).encode("utf-8"))


def _blob_bytes(repo: Path, oid: str) -> bytes:
    return _git(repo, "cat-file", "blob", oid)


def _runtime_class(path: str) -> str:
    suffix = PurePosixPath(path).suffix.lower()
    if suffix in BINARY_EXACT_EXTENSIONS:
        return "binary-exact"
    if suffix in JSON_SEMANTIC_EXTENSIONS:
        return "json-semantic"
    if suffix in TEXT_CLEAN_FILTER_EXTENSIONS:
        return "text-clean-filter"
    return "unsupported"


def _runtime_policy(
    repo: Path, fingerprint: Mapping[str, Any]
) -> tuple[dict[str, Any], str]:
    files: list[dict[str, Any]] = []
    json_rows: list[dict[str, str]] = []
    counts = {
        "binary_exact_count": 0,
        "json_semantic_count": 0,
        "text_clean_filter_count": 0,
        "exact_runtime_text_count": 0,
        "unsupported_count": 0,
    }
    for record in fingerprint["records"]:
        classification = _runtime_class(record["path"])
        row: dict[str, Any] = {
            "path": record["path"],
            "classification": classification,
            "expected_blob_oid": record["blob_oid"],
            "expected_blob_sha256": record["blob_sha256"],
        }
        if classification == "binary-exact":
            counts["binary_exact_count"] += 1
        elif classification == "json-semantic":
            counts["json_semantic_count"] += 1
            semantic = canonical_json_semantic_sha256(
                _blob_bytes(repo, record["blob_oid"])
            )
            row["expected_semantic_sha256"] = semantic
            json_rows.append({"path": record["path"], "semantic_sha256": semantic})
        elif classification == "text-clean-filter":
            counts["text_clean_filter_count"] += 1
        else:
            counts["unsupported_count"] += 1
        files.append(row)
    semantic_aggregate = _sha256(_canonical_json_bytes(json_rows))
    policy = {
        "contract": RUNTIME_COMPATIBILITY_CONTRACT,
        "classification_policy": {
            "binary_exact_extensions": sorted(BINARY_EXACT_EXTENSIONS),
            "json_semantic_extensions": sorted(JSON_SEMANTIC_EXTENSIONS),
            "text_clean_filter_extensions": sorted(TEXT_CLEAN_FILTER_EXTENSIONS),
            "duplicate_json_key_policy": "reject",
            "unsupported_file_policy": "block",
        },
        **counts,
        "files": files,
    }
    return policy, semantic_aggregate


def _hash_without_fields(
    payload: Mapping[str, Any], hash_field: str, excluded: Iterable[str] = ()
) -> str:
    semantic = deepcopy(dict(payload))
    semantic.pop(hash_field, None)
    for field in excluded:
        semantic.pop(field, None)
    return _sha256(_canonical_json_bytes(semantic))


def _hash_exclusions(payload: Mapping[str, Any]) -> tuple[str, ...]:
    if payload.get("hash_scope") == "semantic_payload_excludes_created_at":
        return ("created_at",)
    return ()


def verify_bound_hash(payload: Mapping[str, Any], field: str) -> bool:
    expected = payload.get(field)
    return (
        isinstance(expected, str)
        and _validate_hex(expected, {64})
        and expected
        == _hash_without_fields(payload, field, _hash_exclusions(payload))
    )


def _bind_hash(payload: Mapping[str, Any], field: str) -> dict[str, Any]:
    result = deepcopy(dict(payload))
    result.pop(field, None)
    result[field] = _hash_without_fields(
        result, field, _hash_exclusions(result)
    )
    return result


def build_bundle_authority(
    repo: Path | str,
    commit: str,
    subtree: str,
    *,
    bundle_id: str,
    bundle_role: str,
    legacy_fingerprints: Sequence[Mapping[str, Any] | str],
) -> dict[str, Any]:
    repo_path = Path(repo).resolve()
    fingerprint = build_git_object_bundle_fingerprint(repo_path, commit, subtree)
    runtime_policy, json_aggregate = _runtime_policy(repo_path, fingerprint)
    identity_material = {
        "bundle_id": bundle_id,
        "subtree_tree_oid": fingerprint["subtree_tree_oid"],
        "aggregate_sha256": fingerprint["aggregate_sha256"],
    }
    authority_id = "bundleauth_" + _sha256(_canonical_json_bytes(identity_material))[:20]
    created_at = _git_text(
        repo_path, "show", "-s", "--format=%cI", fingerprint["source_commit"]
    )
    payload = {
        "schema_name": "bundle_fingerprint_authority",
        "schema_version": "1.0.0",
        "authority_id": authority_id,
        "bundle_id": bundle_id,
        "bundle_role": bundle_role,
        "subtree_path": fingerprint["subtree_path"],
        "source_commit": fingerprint["source_commit"],
        "subtree_tree_oid": fingerprint["subtree_tree_oid"],
        "file_count": fingerprint["file_count"],
        "total_blob_bytes": fingerprint["total_blob_bytes"],
        "path_set_sha256": fingerprint["path_set_sha256"],
        "git_object_fingerprint": {
            "algorithm": fingerprint["algorithm"],
            "record_ordering": fingerprint["record_ordering"],
            "serialization": fingerprint["serialization"],
            "aggregate_sha256": fingerprint["aggregate_sha256"],
            "records": fingerprint["records"],
        },
        "json_semantic_aggregate_sha256": json_aggregate,
        "binary_exact_count": runtime_policy["binary_exact_count"],
        "json_semantic_count": runtime_policy["json_semantic_count"],
        "text_clean_filter_count": runtime_policy["text_clean_filter_count"],
        "exact_runtime_text_count": runtime_policy["exact_runtime_text_count"],
        "unsupported_count": runtime_policy["unsupported_count"],
        "runtime_compatibility_policy": runtime_policy,
        "legacy_fingerprints": [deepcopy(item) for item in legacy_fingerprints],
        "authority_status": "CANONICAL",
        "authority_commit": "resolved_by_git_metadata",
        "created_at": created_at,
        "hash_scope": "semantic_payload_excludes_created_at",
        "implementation_provenance": {
            "module": "presentation_agent.deckcompiler.release.bundle_fingerprint",
            "builder": "build_bundle_authority",
            "git_identity_contract": GIT_OBJECT_FINGERPRINT_CONTRACT,
            "runtime_contract": RUNTIME_COMPATIBILITY_CONTRACT,
        },
    }
    return _bind_hash(payload, "manifest_hash")


def _schema_errors(schema_name: str, payload: Mapping[str, Any]) -> list[str]:
    return [
        f"{error.json_path}: {error.message}"
        for error in sorted(
            validator_for(schema_name).iter_errors(dict(payload)),
            key=lambda error: list(error.path),
        )
    ]


def validate_bundle_authority(
    repo: Path | str, authority: Mapping[str, Any]
) -> bool:
    """Validate schema, current Git-object identity, then the content binding."""

    errors = _schema_errors("bundle_fingerprint_authority", authority)
    if errors:
        raise BundleFingerprintError("AUTHORITY_SCHEMA_INVALID", errors[0])
    observed = build_bundle_authority(
        repo,
        str(authority["source_commit"]),
        str(authority["subtree_path"]),
        bundle_id=str(authority["bundle_id"]),
        bundle_role=str(authority["bundle_role"]),
        legacy_fingerprints=authority["legacy_fingerprints"],
    )
    identity_fields = (
        "authority_id",
        "subtree_tree_oid",
        "file_count",
        "total_blob_bytes",
        "path_set_sha256",
        "git_object_fingerprint",
        "json_semantic_aggregate_sha256",
        "binary_exact_count",
        "json_semantic_count",
        "text_clean_filter_count",
        "exact_runtime_text_count",
        "unsupported_count",
        "runtime_compatibility_policy",
        "authority_status",
    )
    mismatches = [
        field for field in identity_fields if authority.get(field) != observed.get(field)
    ]
    if mismatches:
        raise BundleFingerprintError(
            "CURRENT_BUNDLE_AUTHORITY_MISMATCH", ",".join(mismatches)
        )
    if not verify_bound_hash(authority, "manifest_hash"):
        raise BundleFingerprintError("AUTHORITY_MANIFEST_HASH_MISMATCH")
    return True


def build_bundle_fingerprint_policy(
    *,
    exact_runtime_text_path: str = (
        "src/presentation_agent/deckcompiler/qa/reconstruction_source/slides.js"
    ),
    exact_runtime_text_sha256: str = (
        "8130f47caa5decf4e1df5343f405fcc79ff18f6d7c6e1880d7e56733d45ae20b"
    ),
) -> dict[str, Any]:
    payload = {
        "schema_name": "bundle_fingerprint_policy",
        "schema_version": "1.0.0",
        "git_object_identity": {
            "contract": GIT_OBJECT_FINGERPRINT_CONTRACT,
            "source": "committed_git_tree_and_blob_objects",
            "checkout_representation_independent": True,
            "record_ordering": "unicode_code_point_ordinal_over_normalized_posix_paths",
            "serialization": "compact_sorted_key_json_utf8_no_bom_no_trailing_newline",
            "symlink_policy": "reject",
            "submodule_policy": "reject",
        },
        "runtime_compatibility": {
            "contract": RUNTIME_COMPATIBILITY_CONTRACT,
            "repository_identity": False,
            "binary_exact_extensions": sorted(BINARY_EXACT_EXTENSIONS),
            "json_semantic_extensions": sorted(JSON_SEMANTIC_EXTENSIONS),
            "text_clean_filter_extensions": sorted(TEXT_CLEAN_FILTER_EXTENSIONS),
            "duplicate_json_key_policy": "reject",
            "unsupported_file_policy": "block",
        },
        "supported_release_checkout": {
            "core_autocrlf": False,
            "reason": "exact_runtime_text_fixture",
            "exact_runtime_text": [
                {
                    "path": exact_runtime_text_path,
                    "sha256": exact_runtime_text_sha256,
                }
            ],
        },
        "legacy_current_authority_fallback": "forbidden",
        "policy_status": "ACTIVE",
    }
    return _bind_hash(payload, "policy_hash")


def _clean_filter_oid(repo: Path, repo_relative_path: str, file_path: Path) -> str:
    return _git_text(
        repo,
        "hash-object",
        f"--path={repo_relative_path}",
        str(file_path),
    )


def build_runtime_bundle_compatibility(
    repo: Path | str,
    bundle_root: Path | str,
    authority: Mapping[str, Any],
) -> dict[str, Any]:
    repo_path = Path(repo).resolve()
    root = Path(bundle_root).resolve()
    if authority.get("schema_name") != "bundle_fingerprint_authority":
        raise BundleFingerprintError("AUTHORITY_SCHEMA_INVALID")
    expected_records = {
        row["path"]: row
        for row in authority["git_object_fingerprint"]["records"]
    }
    policy_rows = {
        row["path"]: row
        for row in authority["runtime_compatibility_policy"]["files"]
    }
    actual_paths = (
        {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file()
        }
        if root.is_dir()
        else set()
    )
    expected_paths = set(expected_records)
    missing = sorted(expected_paths - actual_paths)
    extra = sorted(actual_paths - expected_paths)
    failures: set[str] = set()
    if missing:
        failures.add("MISSING_TRACKED_BUNDLE_FILE")
    if extra:
        failures.add("EXTRA_BUNDLE_FILE")

    files: list[dict[str, Any]] = []
    subtree = str(authority["subtree_path"])
    for relative in sorted(expected_paths):
        record = expected_records[relative]
        policy = policy_rows[relative]
        classification = policy["classification"]
        path = root / Path(relative)
        row: dict[str, Any] = {
            "path": relative,
            "classification": classification,
            "present": path.is_file(),
            "raw_sha256_match": False,
            "clean_filter_oid_match": False,
            "semantic_match": None,
            "status": "BLOCKED",
        }
        if not path.is_file():
            files.append(row)
            continue
        data = path.read_bytes()
        raw_match = _sha256(data) == record["blob_sha256"]
        row["raw_sha256_match"] = raw_match
        try:
            clean_oid = _clean_filter_oid(
                repo_path, f"{subtree}/{relative}", path
            )
        except BundleFingerprintError:
            clean_oid = ""
        clean_match = clean_oid == record["blob_oid"]
        row["clean_filter_oid_match"] = clean_match

        if classification == "binary-exact":
            if not raw_match:
                failures.add("BINARY_EXACT_MISMATCH")
            if not clean_match:
                failures.add("CLEAN_FILTER_OID_MISMATCH")
            row["status"] = "PASS" if raw_match and clean_match else "BLOCKED"
        elif classification == "json-semantic":
            try:
                semantic = canonical_json_semantic_sha256(data)
            except BundleFingerprintError as exc:
                failures.add(exc.code)
                row["semantic_match"] = False
            else:
                semantic_match = (
                    semantic == policy.get("expected_semantic_sha256")
                )
                row["semantic_match"] = semantic_match
                if not semantic_match:
                    failures.add("JSON_SEMANTIC_MISMATCH")
            if not clean_match:
                failures.add("CLEAN_FILTER_OID_MISMATCH")
            row["status"] = (
                "PASS"
                if row["semantic_match"] is True and clean_match
                else "BLOCKED"
            )
        elif classification == "text-clean-filter":
            if not clean_match:
                failures.add("CLEAN_FILTER_OID_MISMATCH")
            row["status"] = "PASS" if clean_match else "BLOCKED"
        else:
            failures.add("UNSUPPORTED_RUNTIME_FILE")
        files.append(row)

    payload = {
        "schema_name": "runtime_bundle_compatibility",
        "schema_version": "1.0.0",
        "contract": RUNTIME_COMPATIBILITY_CONTRACT,
        "authority_id": authority["authority_id"],
        "bundle_id": authority["bundle_id"],
        "subtree_path": subtree,
        "source_commit": authority["source_commit"],
        "expected_file_count": len(expected_paths),
        "observed_file_count": len(actual_paths),
        "missing_file_count": len(missing),
        "extra_file_count": len(extra),
        "missing_paths": missing,
        "extra_paths": extra,
        "files": files,
        "failure_codes": sorted(failures),
        "status": "PASS" if not failures else "BLOCKED",
    }
    return _bind_hash(payload, "report_hash")


def validate_exact_runtime_text(
    path: Path | str,
    *,
    expected_sha256: str,
    supported_checkout: bool,
) -> dict[str, Any]:
    file_path = Path(path)
    actual = _sha256(file_path.read_bytes()) if file_path.is_file() else None
    if actual == expected_sha256:
        status = "PASS"
    elif supported_checkout:
        raise BundleFingerprintError(
            "EXACT_RUNTIME_TEXT_MISMATCH", file_path.name
        )
    else:
        status = "RUNTIME_MATERIALIZATION_UNSUPPORTED_FOR_EXACT_TEXT"
    return {
        "path": file_path.name,
        "expected_sha256": expected_sha256,
        "actual_sha256": actual,
        "supported_checkout": supported_checkout,
        "status": status,
    }


def validate_supported_release_checkout(
    repo: Path | str,
    exact_runtime_text_path: Path | str,
    *,
    expected_sha256: str,
    required_core_autocrlf: bool,
) -> dict[str, Any]:
    repo_path = Path(repo).resolve()
    observed_text = _git_text(
        repo_path, "config", "--bool", "--get", "core.autocrlf", check=False
    ).lower()
    observed: bool | None
    if observed_text == "true":
        observed = True
    elif observed_text == "false":
        observed = False
    else:
        observed = None
    supported = observed is required_core_autocrlf
    runtime_path = Path(exact_runtime_text_path)
    if not runtime_path.is_absolute():
        runtime_path = repo_path / runtime_path
    exact = validate_exact_runtime_text(
        runtime_path,
        expected_sha256=expected_sha256,
        supported_checkout=supported,
    )
    status = (
        "PASS"
        if supported and exact["status"] == "PASS"
        else "RUNTIME_MATERIALIZATION_UNSUPPORTED_FOR_EXACT_TEXT"
    )
    return {
        "required_core_autocrlf": required_core_autocrlf,
        "observed_core_autocrlf": observed,
        "exact_runtime_text": exact,
        "status": status,
    }


def legacy_directory_aggregate(
    repo: Path | str,
    commit: str,
    subtree: str,
    *,
    include_size: bool,
) -> dict[str, Any]:
    fingerprint = build_git_object_bundle_fingerprint(repo, commit, subtree)
    if include_size:
        rows = [
            f"{row['path']}\0{row['byte_size']}\0{row['blob_sha256']}\n"
            for row in fingerprint["records"]
        ]
        algorithm = "legacy_path_size_sha256_rows"
    else:
        rows = [
            f"{row['path']}\0{row['blob_sha256']}\n"
            for row in fingerprint["records"]
        ]
        algorithm = "legacy_path_sha256_rows"
    return {
        "algorithm": algorithm,
        "aggregate_sha256": _sha256("".join(rows).encode("utf-8")),
        "subtree_tree_oid": fingerprint["subtree_tree_oid"],
        "file_count": fingerprint["file_count"],
        "total_blob_bytes": fingerprint["total_blob_bytes"],
    }


def classify_legacy_fingerprint(
    *,
    expected: str,
    git_object_matches: Sequence[Mapping[str, Any]],
    algorithm_matches: Sequence[Mapping[str, Any]],
    materialization_match: bool,
    materialization_evidence: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if materialization_match and materialization_evidence is None:
        raise BundleFingerprintError("WORKTREE_MATERIALIZATION_EVIDENCE_REQUIRED")
    if git_object_matches:
        classification = "HISTORICAL_GIT_OBJECT_FINGERPRINT"
    elif materialization_match:
        classification = "HISTORICAL_WORKTREE_MATERIALIZATION_FINGERPRINT"
    elif algorithm_matches:
        classification = "LEGACY_ALGORITHM_FINGERPRINT"
    else:
        classification = "UNREPRODUCED_LEGACY_FINGERPRINT"
    return {
        "value": expected,
        "classification": classification,
        "git_object_matches": [dict(item) for item in git_object_matches],
        "algorithm_matches": [dict(item) for item in algorithm_matches],
        "materialization_match": materialization_match,
        "materialization_evidence": (
            dict(materialization_evidence)
            if materialization_evidence is not None
            else None
        ),
        "no_overclaim": True,
    }


def replay_bundle_history(
    repo: Path | str,
    commit: str,
    subtree: str,
    *,
    expected: str,
) -> dict[str, Any]:
    candidates = [
        legacy_directory_aggregate(
            repo, commit, subtree, include_size=False
        ),
        legacy_directory_aggregate(
            repo, commit, subtree, include_size=True
        ),
    ]
    matches = [candidate for candidate in candidates if candidate["aggregate_sha256"] == expected]
    classification = classify_legacy_fingerprint(
        expected=expected,
        git_object_matches=matches,
        algorithm_matches=[],
        materialization_match=False,
        materialization_evidence=None,
    )
    fingerprint = build_git_object_bundle_fingerprint(repo, commit, subtree)
    return {
        "source_commit": fingerprint["source_commit"],
        "subtree_path": fingerprint["subtree_path"],
        "subtree_tree_oid": fingerprint["subtree_tree_oid"],
        "expected": expected,
        "candidate_algorithms": candidates,
        "matched": bool(matches),
        "matching_algorithm": matches[0]["algorithm"] if matches else None,
        "classification": classification["classification"],
        "working_tree_mutation_performed": False,
    }


def discover_legacy_value_history(
    repo: Path | str, value: str
) -> dict[str, Any]:
    repo_path = Path(repo).resolve()
    pathspecs = [
        "*.json",
        "*.md",
        "*.ps1",
        "*.py",
        "*.toml",
        "*.txt",
        "*.yaml",
        "*.yml",
    ]
    output = _git_text(
        repo_path,
        "log",
        "--all",
        "--reverse",
        "--format=%H",
        f"-G{value}",
        "--",
        *pathspecs,
        check=False,
    )
    commits = [line for line in output.splitlines() if _validate_hex(line, {40, 64})]
    occurrences: list[dict[str, Any]] = []
    for commit in commits:
        grep = _git_text(
            repo_path,
            "grep",
            "-I",
            "-l",
            "-F",
            value,
            commit,
            "--",
            *pathspecs,
            check=False,
        )
        paths = sorted(
            line.split(":", 1)[1] if ":" in line else line
            for line in grep.splitlines()
            if line
        )
        occurrences.append({"commit": commit, "paths": paths})
    return {
        "value": value,
        "first_text_commit": commits[0] if commits else None,
        "commits": commits,
        "occurrences": occurrences,
    }


def inventory_subtree_history(
    repo: Path | str, subtree: str
) -> list[dict[str, Any]]:
    repo_path = Path(repo).resolve()
    normalized = _normalize_relative_path(subtree)
    raw = _git_text(
        repo_path,
        "log",
        "--all",
        "--reverse",
        "--format=%H%x00%P%x00%cI",
        "--",
        normalized,
    )
    result: list[dict[str, Any]] = []
    for line in raw.splitlines():
        if not line:
            continue
        commit, parents, committed_at = line.split("\0", 2)
        try:
            fingerprint = build_git_object_bundle_fingerprint(
                repo_path, commit, normalized
            )
        except BundleFingerprintError:
            continue
        changed = _git_text(
            repo_path,
            "diff-tree",
            "--root",
            "--no-commit-id",
            "--name-only",
            "-r",
            commit,
            "--",
            normalized,
            check=False,
        )
        result.append(
            {
                "commit": commit,
                "parents": parents.split() if parents else [],
                "committed_at": committed_at,
                "subtree_tree_oid": fingerprint["subtree_tree_oid"],
                "file_count": fingerprint["file_count"],
                "changed_paths": sorted(line for line in changed.splitlines() if line),
            }
        )
    return result


def build_legacy_correction_record(
    *,
    phase4_legacy: str,
    phase5_legacy: str,
    phase4_classification: str,
    phase5_classification: str,
    phase4_authority: Mapping[str, Any],
    phase5_authority: Mapping[str, Any],
    phase5_matches: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    identity = {
        "phase4_legacy": phase4_legacy,
        "phase5_legacy": phase5_legacy,
        "phase4_authority_id": phase4_authority["authority_id"],
        "phase5_authority_id": phase5_authority["authority_id"],
    }
    payload = {
        "schema_name": "legacy_bundle_fingerprint_correction",
        "schema_version": "1.0.0",
        "record_type": "current_release_authority_supersession",
        "correction_id": "bundlecorrection_"
        + _sha256(_canonical_json_bytes(identity))[:20],
        "phase4_legacy": {
            "value": phase4_legacy,
            "classification": phase4_classification,
            "reproduced": phase4_classification
            != "UNREPRODUCED_LEGACY_FINGERPRINT",
            "matching_commits": [],
            "historical_algorithm": "legacy_path_sha256_rows_working_tree_bytes",
        },
        "phase5_legacy": {
            "value": phase5_legacy,
            "classification": phase5_classification,
            "reproduced": phase5_classification
            != "UNREPRODUCED_LEGACY_FINGERPRINT",
            "matching_commits": [dict(item) for item in phase5_matches],
            "historical_algorithm": "legacy_path_size_sha256_rows",
        },
        "current_authorities": {
            "phase4": {
                "authority_id": phase4_authority["authority_id"],
                "subtree_tree_oid": phase4_authority["subtree_tree_oid"],
                "aggregate_sha256": phase4_authority["git_object_fingerprint"][
                    "aggregate_sha256"
                ]
                if "git_object_fingerprint" in phase4_authority
                else phase4_authority["aggregate_sha256"],
            },
            "phase5": {
                "authority_id": phase5_authority["authority_id"],
                "subtree_tree_oid": phase5_authority["subtree_tree_oid"],
                "aggregate_sha256": phase5_authority["git_object_fingerprint"][
                    "aggregate_sha256"
                ]
                if "git_object_fingerprint" in phase5_authority
                else phase5_authority["aggregate_sha256"],
            },
        },
        "legacy_bytes_modified": False,
        "phase4_bytes_modified": False,
        "phase5_bytes_modified": False,
        "legacy_constants_deleted": False,
        "git_attributes_modified": False,
        "historical_reports_rewritten": False,
        "supersession_scope": "current_release_and_fresh_clone_gates_only",
        "no_overclaim": True,
    }
    return _bind_hash(payload, "correction_hash")


def validate_release_bundle_authorities(
    repo: Path | str, release_contract: Mapping[str, Any]
) -> dict[str, Any]:
    repo_path = Path(repo).resolve()
    result: dict[str, Any] = {}
    for phase in ("phase4", "phase5"):
        key = f"{phase}_authority_manifest_path"
        raw_path = release_contract.get(key)
        if not isinstance(raw_path, str) or not raw_path:
            raise BundleFingerprintError("AUTHORITY_MANIFEST_MISSING", key)
        path = Path(raw_path)
        if not path.is_absolute():
            path = repo_path / path
        if not path.is_file():
            raise BundleFingerprintError("AUTHORITY_MANIFEST_MISSING", raw_path)
        try:
            authority = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BundleFingerprintError(
                "AUTHORITY_SCHEMA_INVALID", str(exc)
            ) from exc
        validate_bundle_authority(repo_path, authority)
        bundle_key = f"{phase}_bundle_path"
        bundle_raw = release_contract.get(bundle_key) or authority["subtree_path"]
        bundle_path = Path(str(bundle_raw))
        if not bundle_path.is_absolute():
            bundle_path = repo_path / bundle_path
        runtime = build_runtime_bundle_compatibility(
            repo_path, bundle_path, authority
        )
        if runtime["status"] != "PASS":
            raise BundleFingerprintError(
                "BLOCKED_RUNTIME_BUNDLE_COMPATIBILITY", phase
            )
        runtime_key = f"{phase}_runtime_compatibility_report_path"
        runtime_raw = release_contract.get(runtime_key)
        if not isinstance(runtime_raw, str) or not runtime_raw:
            raise BundleFingerprintError(
                "RUNTIME_COMPATIBILITY_REPORT_MISSING", runtime_key
            )
        runtime_path = Path(runtime_raw)
        if not runtime_path.is_absolute():
            runtime_path = repo_path / runtime_path
        if not runtime_path.is_file():
            raise BundleFingerprintError(
                "RUNTIME_COMPATIBILITY_REPORT_MISSING", runtime_raw
            )
        try:
            recorded_runtime = json.loads(
                runtime_path.read_text(encoding="utf-8")
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BundleFingerprintError(
                "RUNTIME_COMPATIBILITY_SCHEMA_INVALID", str(exc)
            ) from exc
        runtime_errors = _schema_errors(
            "runtime_bundle_compatibility", recorded_runtime
        )
        if runtime_errors or not verify_bound_hash(
            recorded_runtime, "report_hash"
        ):
            raise BundleFingerprintError(
                "RUNTIME_COMPATIBILITY_SCHEMA_INVALID",
                runtime_errors[0] if runtime_errors else "report hash",
            )
        if recorded_runtime != runtime:
            raise BundleFingerprintError(
                "BLOCKED_RUNTIME_BUNDLE_COMPATIBILITY",
                f"{phase}: recorded report differs from current materialization",
            )
        result[phase] = {
            "authority_id": authority["authority_id"],
            "authority_status": authority["authority_status"],
            "runtime_compatibility_status": runtime["status"],
            "aggregate_sha256": authority["git_object_fingerprint"][
                "aggregate_sha256"
            ],
        }
    return result


def evaluate_phase7c_readiness(
    *,
    authority_validation_status: str,
    runtime_compatibility_status: str,
    cross_clone_report: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if (
        authority_validation_status != "PASS"
        or runtime_compatibility_status != "PASS"
    ):
        return {"status": "BLOCKED_BUNDLE_FINGERPRINT_AUTHORITY"}
    if cross_clone_report is None:
        return {"status": "BLOCKED_PENDING_CROSS_CLONE_PROOF"}
    if (
        cross_clone_report.get("verdict") != "PASS"
        or cross_clone_report.get("unexpected_difference_count") != 0
    ):
        return {"status": "BLOCKED_CROSS_CLONE_FINGERPRINT_MISMATCH"}
    return {"status": "READY_FOR_PHASE7C"}


__all__ = [
    "BINARY_EXACT_EXTENSIONS",
    "BundleFingerprintError",
    "GIT_OBJECT_FINGERPRINT_CONTRACT",
    "JSON_SEMANTIC_EXTENSIONS",
    "RUNTIME_COMPATIBILITY_CONTRACT",
    "TEXT_CLEAN_FILTER_EXTENSIONS",
    "build_bundle_authority",
    "build_bundle_fingerprint_policy",
    "build_git_object_bundle_fingerprint",
    "build_legacy_correction_record",
    "build_runtime_bundle_compatibility",
    "canonical_json_semantic_sha256",
    "classify_legacy_fingerprint",
    "discover_legacy_value_history",
    "evaluate_phase7c_readiness",
    "fingerprint_records",
    "inventory_subtree_history",
    "legacy_directory_aggregate",
    "replay_bundle_history",
    "validate_bundle_authority",
    "validate_exact_runtime_text",
    "validate_release_bundle_authorities",
    "validate_supported_release_checkout",
    "verify_bound_hash",
]
