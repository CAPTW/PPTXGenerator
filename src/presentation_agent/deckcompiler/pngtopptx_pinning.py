"""Read-only provenance pinning for the external CAPTW/pngtopptx SkillSet."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import unicodedata
from pathlib import Path
from typing import Any, Mapping, Sequence

from .identity import content_sha256, stable_id


EXPECTED_SKILLS: tuple[str, ...] = (
    "slide-editable-deck-orchestrator",
    "slide-text-layer-inpaint",
    "slide-image-dual-render",
    "slide-visual-polish-qa",
)

KNOWN_SKILL_HASHES: dict[str, str] = {
    "slide-editable-deck-orchestrator": "b8d157acf6179197401b053b52b730c8d605fc877cc8b087d99f2c13a4964b7d",
    "slide-text-layer-inpaint": "e433ca0a9357f9b721866c33021db57d7ebbb6cb53b368b7500496140058720e",
    "slide-image-dual-render": "8b5ae4a3d4624222fc0779014f79be6679e904356777558f1dfde8f72a4c3ba9",
    "slide-visual-polish-qa": "4c3ff087e112ad2742d276b53480b62158852a8c9fbc8ddb487c9dbeec9db50a",
}

CANONICAL_REPOSITORY = "CAPTW/pngtopptx"
CANONICAL_REPOSITORY_URL = "https://github.com/CAPTW/pngtopptx.git"
PIN_SCHEMA_NAME = "external_skillset_pin"
PIN_SCHEMA_VERSION = "1.0.0"

_CACHE_DIRECTORIES = frozenset({"__pycache__", ".pytest_cache"})
_CACHE_FILENAMES = frozenset({".DS_Store", "Thumbs.db"})
_SCRIPT_SUFFIXES = frozenset(
    {".py", ".js", ".ts", ".mjs", ".cjs", ".ps1", ".cmd", ".bat", ".sh"}
)
_EXECUTABLE_SUFFIXES = frozenset({".exe", ".com", ".dll"})
_SOURCE_SUFFIXES = _SCRIPT_SUFFIXES | frozenset(
    {".md", ".json", ".yaml", ".yml", ".toml", ".txt", ".xml", ".html", ".css"}
)


class PinningError(RuntimeError):
    """Fail-closed external SkillSet pinning error."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _compact_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _canonical_text_bytes(data: bytes) -> bytes:
    text = data.decode("utf-8-sig")
    text = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))
    return text.encode("utf-8")


def canonical_text_linkage_hash(data: bytes) -> str:
    """Hash text for source linkage only; never use it as the execution pin."""

    return _sha256(_canonical_text_bytes(data))


def _is_reparse_or_symlink(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError as exc:
        raise PinningError("UNREADABLE_REQUIRED_PATH", f"cannot stat {path}: {exc}") from exc
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse_flag)


def _excluded_reason(relative_path: str) -> str | None:
    parts = relative_path.split("/")
    if any(part in _CACHE_DIRECTORIES for part in parts):
        return "cache_directory"
    if parts[-1] in _CACHE_FILENAMES:
        return "os_cache_file"
    if parts[-1].lower().endswith((".log", ".tmp")):
        return "temporary_log_or_file"
    return None


def _file_type(path: Path) -> str:
    if path.name == "SKILL.md":
        return "skill_manifest"
    return path.suffix.lower().lstrip(".") or "extensionless"


def _executable_status(path: Path, data: bytes) -> str:
    suffix = path.suffix.lower()
    if suffix in _EXECUTABLE_SUFFIXES or data.startswith(b"MZ"):
        return "executable_binary"
    if suffix in _SCRIPT_SUFFIXES or data.startswith(b"#!"):
        return "script"
    return "not_executable"


def _text_metadata(data: bytes) -> tuple[str, str | None]:
    try:
        return "text", canonical_text_linkage_hash(data)
    except UnicodeDecodeError:
        return "binary", None


def _walk_regular_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for current, directory_names, file_names in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in list(directory_names):
            directory = current_path / name
            if _is_reparse_or_symlink(directory):
                raise PinningError(
                    "REPARSE_POINT_BLOCKED", f"external Skill path contains reparse point: {directory}"
                )
        for name in file_names:
            path = current_path / name
            if _is_reparse_or_symlink(path):
                raise PinningError(
                    "REPARSE_POINT_BLOCKED", f"external Skill path contains reparse point: {path}"
                )
            if not path.is_file():
                raise PinningError("UNREADABLE_REQUIRED_FILE", f"not a regular file: {path}")
            files.append(path)
    return sorted(files, key=lambda item: item.relative_to(root).as_posix())


def build_installation_inventory(
    installation_root: str | Path,
    *,
    expected_skill_hashes: Mapping[str, str] = KNOWN_SKILL_HASHES,
    expected_skills: Sequence[str] = EXPECTED_SKILLS,
) -> dict[str, Any]:
    """Inventory the installed SkillSet without modifying any installed byte."""

    root = Path(installation_root).absolute()
    if not root.is_dir():
        raise PinningError("MISSING_INSTALLATION_ROOT", f"installation root missing: {root}")
    if _is_reparse_or_symlink(root):
        raise PinningError("REPARSE_POINT_BLOCKED", f"installation root is a reparse point: {root}")

    skills: list[dict[str, Any]] = []
    excluded_files: list[dict[str, Any]] = []
    combined_records: list[dict[str, Any]] = []
    for skill_name in sorted(expected_skills):
        skill_root = root / skill_name
        if not skill_root.is_dir():
            raise PinningError("MISSING_SKILL", f"required Skill directory missing: {skill_name}")
        if _is_reparse_or_symlink(skill_root):
            raise PinningError(
                "REPARSE_POINT_BLOCKED", f"required Skill path is a reparse point: {skill_root}"
            )
        records: list[dict[str, Any]] = []
        skill_excluded: list[dict[str, Any]] = []
        for path in _walk_regular_files(skill_root):
            relative_path = path.relative_to(skill_root).as_posix()
            try:
                data = path.read_bytes()
            except OSError as exc:
                raise PinningError("UNREADABLE_REQUIRED_FILE", f"cannot read {path}: {exc}") from exc
            reason = _excluded_reason(relative_path)
            if reason:
                excluded = {
                    "skill_name": skill_name,
                    "relative_path": relative_path,
                    "byte_size": len(data),
                    "sha256": _sha256(data),
                    "reason": reason,
                }
                skill_excluded.append(excluded)
                excluded_files.append(excluded)
                continue
            classification, linkage_hash = _text_metadata(data)
            record = {
                "skill_name": skill_name,
                "relative_path": relative_path,
                "byte_size": len(data),
                "sha256": _sha256(data),
                "file_type": _file_type(path),
                "executable_status": _executable_status(path, data),
                "classification": classification,
                "canonical_text_linkage_sha256": linkage_hash,
            }
            records.append(record)
            combined_records.append(
                {
                    "skill_name": skill_name,
                    "relative_path": relative_path,
                    "byte_size": len(data),
                    "sha256": record["sha256"],
                }
            )
        skill_md = next((record for record in records if record["relative_path"] == "SKILL.md"), None)
        if skill_md is None:
            raise PinningError("MISSING_SKILL_MANIFEST", f"SKILL.md missing: {skill_name}")
        expected_hash = expected_skill_hashes.get(skill_name)
        if expected_hash is None:
            raise PinningError("MISSING_EXPECTED_HASH", f"no expected SKILL.md hash for {skill_name}")
        if skill_md["sha256"] != expected_hash:
            raise PinningError(
                "SKILL_HASH_MISMATCH",
                f"{skill_name} expected {expected_hash}, got {skill_md['sha256']}",
            )
        aggregate_records = [
            {
                "skill_name": record["skill_name"],
                "relative_path": record["relative_path"],
                "byte_size": record["byte_size"],
                "sha256": record["sha256"],
            }
            for record in records
        ]
        skills.append(
            {
                "skill_name": skill_name,
                "installed_path": str(skill_root),
                "file_count": len(records),
                "aggregate_sha256": _sha256(_compact_json_bytes(aggregate_records)),
                "skill_md_sha256": skill_md["sha256"],
                "files": records,
                "excluded_files": skill_excluded,
            }
        )
    combined_records.sort(key=lambda record: (record["skill_name"], record["relative_path"]))
    return {
        "installation_root": str(root),
        "skills": skills,
        "combined_aggregate_sha256": _sha256(_compact_json_bytes(combined_records)),
        "known_skill_hashes_match": True,
        "excluded_file_count": len(excluded_files),
        "excluded_files": excluded_files,
    }


def _git(repository: Path, *args: str) -> bytes:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repository), *args], stderr=subprocess.STDOUT
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        output = getattr(exc, "output", b"").decode("utf-8", errors="replace").strip()
        raise PinningError("SOURCE_REPOSITORY_ERROR", output or str(exc)) from exc


def _normalized_repository_identity(url: str) -> str:
    normalized = url.strip().lower().replace("\\", "/")
    normalized = normalized.removesuffix(".git").removesuffix("/")
    if normalized.startswith("git@github.com:"):
        normalized = "https://github.com/" + normalized.split(":", 1)[1]
    return normalized


def _source_records(repository: Path, commit: str, skill_name: str) -> dict[str, dict[str, Any]]:
    prefix = f"skills/{skill_name}/"
    paths = _git(
        repository, "ls-tree", "-r", "--name-only", commit, "--", f"skills/{skill_name}"
    ).decode("utf-8").splitlines()
    records: dict[str, dict[str, Any]] = {}
    for source_path in paths:
        if not source_path.startswith(prefix):
            continue
        data = _git(repository, "show", f"{commit}:{source_path}")
        classification, linkage_hash = _text_metadata(data)
        records[source_path[len(prefix) :]] = {
            "sha256": _sha256(data),
            "classification": classification,
            "canonical_text_linkage_sha256": linkage_hash,
        }
    return records


def _source_content_aggregate(
    source_by_skill: Mapping[str, Mapping[str, Mapping[str, Any]]]
) -> str:
    records: list[dict[str, Any]] = []
    for skill_name in sorted(source_by_skill):
        for relative_path in sorted(source_by_skill[skill_name]):
            record = source_by_skill[skill_name][relative_path]
            records.append(
                {
                    "skill_name": skill_name,
                    "relative_path": relative_path,
                    "linkage_sha256": record["canonical_text_linkage_sha256"]
                    if record["classification"] == "text"
                    else record["sha256"],
                }
            )
    return _sha256(_compact_json_bytes(records))


def _source_like(relative_path: str) -> bool:
    path = Path(relative_path)
    return path.name == "SKILL.md" or path.suffix.lower() in (_SOURCE_SUFFIXES | _EXECUTABLE_SUFFIXES)


def _resolve_source_linkage(
    inventory: Mapping[str, Any], source_repository: Path
) -> dict[str, Any]:
    repository = source_repository.absolute()
    if not (repository / ".git").exists():
        raise PinningError("SOURCE_REPOSITORY_ERROR", f"not a Git repository: {repository}")
    try:
        remote_url = _git(repository, "config", "--get", "remote.origin.url").decode().strip()
    except PinningError as exc:
        raise PinningError("SOURCE_IDENTITY_UNVERIFIED", str(exc)) from exc
    if _normalized_repository_identity(remote_url) != _normalized_repository_identity(
        CANONICAL_REPOSITORY_URL
    ):
        raise PinningError("SOURCE_IDENTITY_UNVERIFIED", f"unexpected origin: {remote_url}")

    installed_by_skill = {
        skill["skill_name"]: {record["relative_path"]: record for record in skill["files"]}
        for skill in inventory["skills"]
    }
    commits = sorted(_git(repository, "rev-list", "--all").decode().splitlines())
    candidates: list[dict[str, Any]] = []
    source_like_extras: set[str] = set()
    matching_skill_manifest_commit_seen = False
    inventory_mismatch_seen = False
    for commit in commits:
        source_by_skill = {
            skill_name: _source_records(repository, commit, skill_name)
            for skill_name in sorted(installed_by_skill)
        }
        manifests_match = all(
            installed_by_skill[skill_name]["SKILL.md"]["canonical_text_linkage_sha256"]
            == source_by_skill[skill_name].get("SKILL.md", {}).get(
                "canonical_text_linkage_sha256"
            )
            for skill_name in installed_by_skill
        )
        if not manifests_match:
            continue
        matching_skill_manifest_commit_seen = True
        paths_exact = True
        content_equivalent = True
        raw_exact = True
        tree_oids: dict[str, str] = {}
        for skill_name, installed_records in installed_by_skill.items():
            source_records = source_by_skill[skill_name]
            installed_paths = set(installed_records)
            source_paths = set(source_records)
            for extra in installed_paths - source_paths:
                if _source_like(extra):
                    source_like_extras.add(f"{skill_name}/{extra}")
            if installed_paths != source_paths:
                paths_exact = False
                inventory_mismatch_seen = True
                continue
            tree_oids[skill_name] = _git(
                repository, "rev-parse", f"{commit}:skills/{skill_name}"
            ).decode().strip()
            for relative_path, installed_record in installed_records.items():
                source_record = source_records[relative_path]
                if installed_record["sha256"] != source_record["sha256"]:
                    raw_exact = False
                if installed_record["classification"] == "text" and source_record[
                    "classification"
                ] == "text":
                    equal = (
                        installed_record["canonical_text_linkage_sha256"]
                        == source_record["canonical_text_linkage_sha256"]
                    )
                else:
                    equal = installed_record["sha256"] == source_record["sha256"]
                if not equal:
                    content_equivalent = False
        if paths_exact and content_equivalent:
            candidates.append(
                {
                    "commit": commit,
                    "raw_exact": raw_exact,
                    "tree_oids": tree_oids,
                    "source_content_aggregate_sha256": _source_content_aggregate(
                        source_by_skill
                    ),
                }
            )

    if not candidates:
        if source_like_extras:
            raise PinningError(
                "UNEXPECTED_SOURCE_EXTRA", ", ".join(sorted(source_like_extras))
            )
        if matching_skill_manifest_commit_seen and inventory_mismatch_seen:
            raise PinningError(
                "SOURCE_INVENTORY_MISMATCH",
                "matching SKILL.md content exists but the installed source path set is incomplete",
            )
        raise PinningError(
            "SOURCE_LINKAGE_INCONCLUSIVE", "no source commit matches all installed Skill files"
        )

    candidate_commits = sorted(candidate["commit"] for candidate in candidates)
    content_aggregates = {candidate["source_content_aggregate_sha256"] for candidate in candidates}
    if len(candidates) == 1:
        candidate = candidates[0]
        mode = "git_revision_exact" if candidate["raw_exact"] else "git_revision_content_equivalent"
        source_commit: str | None = candidate["commit"]
        git_revision_verified = True
        source_tree_oids = candidate["tree_oids"]
    elif len(content_aggregates) == 1:
        mode = "git_tree_pin"
        source_commit = None
        git_revision_verified = False
        tree_sets = {
            json.dumps(candidate["tree_oids"], sort_keys=True) for candidate in candidates
        }
        source_tree_oids = json.loads(next(iter(tree_sets))) if len(tree_sets) == 1 else {}
    else:
        raise PinningError(
            "AMBIGUOUS_SOURCE_LINKAGE",
            "matching commits do not share one relevant source-content aggregate",
        )
    return {
        "pinning_mode": mode,
        "source_repository_url": CANONICAL_REPOSITORY_URL,
        "source_commit": source_commit,
        "source_tree_oids": source_tree_oids,
        "candidate_commits": candidate_commits,
        "git_revision_verified": git_revision_verified,
        "source_content_aggregate_sha256": next(iter(content_aggregates)),
        "source_comparison_status": "PASS",
        "unexpected_executable_extras_count": 0,
        "final_provenance_limitation": False,
    }


def _fallback_linkage() -> dict[str, Any]:
    return {
        "pinning_mode": "installation_fingerprint_bundle_v1",
        "source_repository_url": None,
        "source_commit": None,
        "source_tree_oids": {},
        "candidate_commits": [],
        "git_revision_verified": False,
        "source_content_aggregate_sha256": None,
        "source_comparison_status": "not_available",
        "unexpected_executable_extras_count": 0,
        "final_provenance_limitation": True,
    }


def _pin_hash(payload: Mapping[str, Any]) -> str:
    return content_sha256({key: value for key, value in payload.items() if key != "pin_hash"})


def validate_pin_claims(payload: Mapping[str, Any]) -> None:
    mode = payload.get("pinning_mode")
    source_commit = payload.get("source_commit")
    revision_verified = payload.get("git_revision_verified")
    if source_commit and not revision_verified:
        raise PinningError(
            "UNSUPPORTED_GIT_REVISION_CLAIM", "source_commit requires verified unique revision evidence"
        )
    if mode == "git_tree_pin" and source_commit is not None:
        raise PinningError(
            "UNSUPPORTED_GIT_REVISION_CLAIM", "git_tree_pin cannot claim a unique source commit"
        )
    if mode in {"git_revision_exact", "git_revision_content_equivalent"}:
        if not source_commit or revision_verified is not True:
            raise PinningError(
                "UNSUPPORTED_GIT_REVISION_CLAIM", "revision pin requires a verified source commit"
            )
    if mode == "installation_fingerprint_bundle_v1" and (
        source_commit is not None or revision_verified is not False
    ):
        raise PinningError(
            "UNSUPPORTED_GIT_REVISION_CLAIM", "fingerprint fallback cannot claim Git revision provenance"
        )


def build_external_skillset_pin(
    installation_root: str | Path,
    *,
    deckcompiler_commit: str,
    created_at: str,
    timezone: str,
    source_repository: str | Path | None = None,
    expected_skill_hashes: Mapping[str, str] = KNOWN_SKILL_HASHES,
) -> dict[str, Any]:
    inventory = build_installation_inventory(
        installation_root, expected_skill_hashes=expected_skill_hashes
    )
    if source_repository is None:
        linkage = _fallback_linkage()
    else:
        linkage = _resolve_source_linkage(inventory, Path(source_repository))
    skill_file_counts = {
        skill["skill_name"]: skill["file_count"] for skill in inventory["skills"]
    }
    skill_aggregate_hashes = {
        skill["skill_name"]: skill["aggregate_sha256"] for skill in inventory["skills"]
    }
    installed_skill_paths = {
        skill["skill_name"]: skill["installed_path"] for skill in inventory["skills"]
    }
    pin_components = {
        "combined_aggregate_sha256": inventory["combined_aggregate_sha256"],
        "pinning_mode": linkage["pinning_mode"],
        "candidate_commits": linkage["candidate_commits"],
        "source_tree_oids": linkage["source_tree_oids"],
    }
    payload: dict[str, Any] = {
        "schema_name": PIN_SCHEMA_NAME,
        "schema_version": PIN_SCHEMA_VERSION,
        "pin_id": stable_id("pngpin", pin_components),
        "canonical_repository": CANONICAL_REPOSITORY,
        "expected_orchestrator": "slide-editable-deck-orchestrator",
        "companion_skills": list(EXPECTED_SKILLS[1:]),
        "installation_root": inventory["installation_root"],
        "installed_skill_paths": installed_skill_paths,
        "skill_names": sorted(EXPECTED_SKILLS),
        "skill_file_counts": skill_file_counts,
        "skill_aggregate_hashes": skill_aggregate_hashes,
        "combined_aggregate_sha256": inventory["combined_aggregate_sha256"],
        "known_skill_md_hashes": dict(sorted(expected_skill_hashes.items())),
        "pinning_mode": linkage["pinning_mode"],
        "source_repository_url": linkage["source_repository_url"],
        "source_commit": linkage["source_commit"],
        "source_tree_oids": linkage["source_tree_oids"],
        "source_content_aggregate_sha256": linkage["source_content_aggregate_sha256"],
        "candidate_commits": linkage["candidate_commits"],
        "git_revision_verified": linkage["git_revision_verified"],
        "installation_bundle_verified": True,
        "unexpected_executable_extras_count": linkage[
            "unexpected_executable_extras_count"
        ],
        "excluded_cache_files": inventory["excluded_files"],
        "created_at": created_at,
        "timezone": timezone,
        "deckcompiler_commit": deckcompiler_commit,
        "external_skill_modified": False,
        "execution_allowed": True,
        "final_provenance_limitation": linkage["final_provenance_limitation"],
        "source_comparison_status": linkage["source_comparison_status"],
        "validation_status": "PASS",
        "inventory": inventory["skills"],
    }
    payload["pin_hash"] = _pin_hash(payload)
    validate_pin_claims(payload)
    from .schemas import validator_for

    errors = sorted(
        validator_for("external_skillset_pin").iter_errors(payload),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        raise PinningError(
            "PIN_SCHEMA_INVALID",
            "; ".join(f"{list(error.absolute_path)}: {error.message}" for error in errors),
        )
    return payload


def validate_external_skillset_pin(
    installation_root: str | Path,
    payload: Mapping[str, Any],
    *,
    expected_skill_hashes: Mapping[str, str] = KNOWN_SKILL_HASHES,
) -> dict[str, Any]:
    validate_pin_claims(payload)
    if payload.get("pin_hash") != _pin_hash(payload):
        raise PinningError("PIN_HASH_MISMATCH", "pin artifact self-hash does not verify")
    current = build_installation_inventory(
        installation_root, expected_skill_hashes=expected_skill_hashes
    )
    if current["combined_aggregate_sha256"] != payload.get("combined_aggregate_sha256"):
        raise PinningError(
            "INSTALLATION_MUTATED",
            f"expected {payload.get('combined_aggregate_sha256')}, got {current['combined_aggregate_sha256']}",
        )
    for skill in current["skills"]:
        name = skill["skill_name"]
        if skill["aggregate_sha256"] != payload.get("skill_aggregate_hashes", {}).get(name):
            raise PinningError("INSTALLATION_MUTATED", f"aggregate mismatch for {name}")
        if skill["file_count"] != payload.get("skill_file_counts", {}).get(name):
            raise PinningError("INSTALLATION_MUTATED", f"file-count mismatch for {name}")
    return {
        "valid": True,
        "pin_id": payload["pin_id"],
        "combined_aggregate_sha256": current["combined_aggregate_sha256"],
        "excluded_file_count": current["excluded_file_count"],
    }


__all__ = [
    "CANONICAL_REPOSITORY",
    "CANONICAL_REPOSITORY_URL",
    "EXPECTED_SKILLS",
    "KNOWN_SKILL_HASHES",
    "PinningError",
    "build_external_skillset_pin",
    "build_installation_inventory",
    "canonical_text_linkage_hash",
    "validate_external_skillset_pin",
    "validate_pin_claims",
]
