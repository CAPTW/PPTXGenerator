"""Install the pinned CAPTW/pngtopptx SkillSet without vendoring it.

The installer uses only the Python standard library and Git. It clones the
canonical public repository at the release-pinned commit, forces an LF
checkout, verifies the four committed subtree OIDs and every installed file
against the repository-owned pin, then installs only missing Skills.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PIN_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "devpost"
    / "evidence"
    / "pngtopptx_external_skillset_pin.json"
)
CANONICAL_REPOSITORY = "CAPTW/pngtopptx"
CANONICAL_REPOSITORY_URL = "https://github.com/CAPTW/pngtopptx.git"
PINNED_SOURCE_COMMIT = "921eec900550204f6c8f019f811d65dc0839f8c0"
INSTALLER_VERSION = "1.0.0"

_CACHE_DIRECTORIES = frozenset({"__pycache__", ".pytest_cache"})
_CACHE_FILENAMES = frozenset({".DS_Store", "Thumbs.db"})
_REPARSE_FLAG = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


class SkillsetInstallError(RuntimeError):
    """Stable, fail-closed installer error."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _pin_hash(payload: Mapping[str, Any]) -> str:
    material = {key: value for key, value in payload.items() if key != "pin_hash"}
    return hashlib.sha256(_canonical_json_bytes(material)).hexdigest()


def _records_hash(records: Sequence[Mapping[str, Any]]) -> str:
    return hashlib.sha256(
        json.dumps(
            list(records),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalized_repository_identity(value: str) -> str:
    normalized = value.strip().lower().replace("\\", "/")
    normalized = normalized.removesuffix(".git").removesuffix("/")
    if normalized.startswith("git@github.com:"):
        normalized = "https://github.com/" + normalized.split(":", 1)[1]
    return normalized


def _is_reparse_or_symlink(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        return bool(getattr(path.lstat(), "st_file_attributes", 0) & _REPARSE_FLAG)
    except OSError as exc:
        raise SkillsetInstallError(
            "PNGTPPTX_PATH_UNREADABLE", f"{path}: {exc}"
        ) from exc


def _excluded(relative_path: str) -> bool:
    parts = relative_path.split("/")
    return (
        any(part in _CACHE_DIRECTORIES for part in parts)
        or parts[-1] in _CACHE_FILENAMES
        or parts[-1].lower().endswith((".log", ".tmp"))
    )


def _safe_relative_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    candidate = PurePosixPath(normalized)
    if (
        not normalized
        or candidate.is_absolute()
        or any(part in {"", ".", ".."} for part in candidate.parts)
    ):
        raise SkillsetInstallError("PNGTPPTX_PIN_PATH_INVALID", value)
    return candidate.as_posix()


def load_pin(path: Path = PIN_PATH) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SkillsetInstallError("PNGTPPTX_PIN_INVALID", str(exc)) from exc
    if not isinstance(payload, dict) or payload.get("pin_hash") != _pin_hash(payload):
        raise SkillsetInstallError("PNGTPPTX_PIN_INVALID", "self-hash mismatch")
    if payload.get("canonical_repository") != CANONICAL_REPOSITORY:
        raise SkillsetInstallError(
            "PNGTPPTX_SOURCE_IDENTITY_MISMATCH",
            str(payload.get("canonical_repository")),
        )
    if _normalized_repository_identity(
        str(payload.get("source_repository_url", ""))
    ) != _normalized_repository_identity(CANONICAL_REPOSITORY_URL):
        raise SkillsetInstallError(
            "PNGTPPTX_SOURCE_IDENTITY_MISMATCH",
            str(payload.get("source_repository_url")),
        )
    if PINNED_SOURCE_COMMIT not in payload.get("candidate_commits", []):
        raise SkillsetInstallError(
            "PNGTPPTX_PINNED_COMMIT_MISSING", PINNED_SOURCE_COMMIT
        )
    skill_names = payload.get("skill_names")
    inventory = payload.get("inventory")
    source_tree_oids = payload.get("source_tree_oids")
    if (
        not isinstance(skill_names, list)
        or len(skill_names) != 4
        or not isinstance(inventory, list)
        or not isinstance(source_tree_oids, dict)
        or set(skill_names) != set(source_tree_oids)
    ):
        raise SkillsetInstallError("PNGTPPTX_PIN_INVALID", "Skill inventory")
    return payload


def _inventory_by_skill(pin: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in pin["inventory"]:
        name = str(row.get("skill_name", ""))
        if name in result or name not in pin["skill_names"]:
            raise SkillsetInstallError("PNGTPPTX_PIN_INVALID", name)
        expected_files: dict[str, dict[str, Any]] = {}
        for file_row in row.get("files", []):
            relative = _safe_relative_path(str(file_row.get("relative_path", "")))
            if relative in expected_files:
                raise SkillsetInstallError(
                    "PNGTPPTX_PIN_INVALID", f"duplicate {name}/{relative}"
                )
            expected_files[relative] = dict(file_row)
        result[name] = {
            "aggregate_sha256": row.get("aggregate_sha256"),
            "file_count": row.get("file_count"),
            "files": expected_files,
        }
    if set(result) != set(pin["skill_names"]):
        raise SkillsetInstallError("PNGTPPTX_PIN_INVALID", "incomplete inventory")
    return result


def _walk_skill_files(skill_root: Path) -> list[Path]:
    files: list[Path] = []
    for current, directory_names, file_names in os.walk(
        skill_root, followlinks=False
    ):
        current_path = Path(current)
        for name in list(directory_names):
            directory = current_path / name
            if _is_reparse_or_symlink(directory):
                raise SkillsetInstallError(
                    "PNGTPPTX_REPARSE_POINT_BLOCKED", str(directory)
                )
        for name in file_names:
            path = current_path / name
            if _is_reparse_or_symlink(path) or not path.is_file():
                raise SkillsetInstallError(
                    "PNGTPPTX_NONREGULAR_FILE_BLOCKED", str(path)
                )
            relative = path.relative_to(skill_root).as_posix()
            if not _excluded(relative):
                files.append(path)
    return sorted(files, key=lambda item: item.relative_to(skill_root).as_posix())


def _inspect_skill(
    skill_root: Path,
    *,
    skill_name: str,
    expected: Mapping[str, Any],
) -> dict[str, Any]:
    if not skill_root.is_dir():
        return {"status": "MISSING", "skill_name": skill_name}
    if _is_reparse_or_symlink(skill_root):
        raise SkillsetInstallError(
            "PNGTPPTX_REPARSE_POINT_BLOCKED", str(skill_root)
        )
    expected_files = expected["files"]
    observed_files: dict[str, dict[str, Any]] = {}
    aggregate_records: list[dict[str, Any]] = []
    for path in _walk_skill_files(skill_root):
        relative = path.relative_to(skill_root).as_posix()
        record = {
            "skill_name": skill_name,
            "relative_path": relative,
            "byte_size": path.stat().st_size,
            "sha256": _sha256_file(path),
        }
        observed_files[relative] = record
        aggregate_records.append(record)
    path_mismatch = sorted(set(expected_files) ^ set(observed_files))
    content_mismatch = sorted(
        relative
        for relative in set(expected_files) & set(observed_files)
        if (
            observed_files[relative]["byte_size"]
            != expected_files[relative].get("byte_size")
            or observed_files[relative]["sha256"]
            != expected_files[relative].get("sha256")
        )
    )
    observed_aggregate = _records_hash(aggregate_records)
    exact = (
        not path_mismatch
        and not content_mismatch
        and len(observed_files) == expected.get("file_count")
        and observed_aggregate == expected.get("aggregate_sha256")
    )
    return {
        "status": "PASS" if exact else "MISMATCH",
        "skill_name": skill_name,
        "observed_file_count": len(observed_files),
        "observed_aggregate_sha256": observed_aggregate,
        "path_mismatch": path_mismatch,
        "content_mismatch": content_mismatch,
    }


def inspect_installation(
    installation_root: Path, pin: Mapping[str, Any]
) -> dict[str, Any]:
    root = installation_root.resolve(strict=False)
    expected = _inventory_by_skill(pin)
    if root.exists() and (not root.is_dir() or _is_reparse_or_symlink(root)):
        raise SkillsetInstallError("PNGTPPTX_TARGET_ROOT_INVALID", str(root))
    skills = [
        _inspect_skill(root / name, skill_name=name, expected=expected[name])
        for name in sorted(pin["skill_names"])
    ]
    statuses = {row["status"] for row in skills}
    status = (
        "PASS"
        if statuses == {"PASS"}
        else "MISSING"
        if statuses <= {"PASS", "MISSING"}
        else "MISMATCH"
    )
    return {
        "status": status,
        "installation_root": str(root),
        "combined_aggregate_sha256": (
            pin["combined_aggregate_sha256"] if status == "PASS" else None
        ),
        "skills": skills,
    }


def _run_git(*args: str, cwd: Path | None = None) -> str:
    command = ["git"]
    if cwd is not None:
        command.extend(["-C", str(cwd)])
    command.extend(args)
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError as exc:
        raise SkillsetInstallError("PNGTPPTX_GIT_UNAVAILABLE", str(exc)) from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise SkillsetInstallError("PNGTPPTX_GIT_FAILED", detail)
    return completed.stdout.strip()


def _verified_source(pin: Mapping[str, Any], temporary_root: Path) -> Path:
    source = temporary_root / "pngtopptx"
    _run_git(
        "clone",
        "--no-tags",
        "--no-checkout",
        CANONICAL_REPOSITORY_URL,
        str(source),
    )
    _run_git("config", "core.autocrlf", "false", cwd=source)
    _run_git("checkout", "--detach", PINNED_SOURCE_COMMIT, cwd=source)
    if _run_git("rev-parse", "HEAD", cwd=source) != PINNED_SOURCE_COMMIT:
        raise SkillsetInstallError(
            "PNGTPPTX_SOURCE_COMMIT_MISMATCH", PINNED_SOURCE_COMMIT
        )
    origin = _run_git("config", "--get", "remote.origin.url", cwd=source)
    if _normalized_repository_identity(origin) != _normalized_repository_identity(
        CANONICAL_REPOSITORY_URL
    ):
        raise SkillsetInstallError("PNGTPPTX_SOURCE_IDENTITY_MISMATCH", origin)
    for skill_name, expected_oid in sorted(pin["source_tree_oids"].items()):
        observed_oid = _run_git(
            "rev-parse",
            f"{PINNED_SOURCE_COMMIT}:skills/{skill_name}",
            cwd=source,
        )
        if observed_oid != expected_oid:
            raise SkillsetInstallError(
                "PNGTPPTX_SOURCE_TREE_MISMATCH",
                f"{skill_name}: expected {expected_oid}, got {observed_oid}",
            )
    source_status = inspect_installation(source / "skills", pin)
    if source_status["status"] != "PASS":
        raise SkillsetInstallError(
            "PNGTPPTX_SOURCE_BYTES_MISMATCH",
            json.dumps(source_status["skills"], ensure_ascii=False),
        )
    return source / "skills"


def _reject_repository_target(target_root: Path) -> None:
    target = target_root.resolve(strict=False)
    repository = REPOSITORY_ROOT.resolve()
    if target == repository or target.is_relative_to(repository):
        raise SkillsetInstallError("PNGTPPTX_TARGET_INSIDE_REPOSITORY", str(target))


def _write_receipt(
    target_root: Path,
    *,
    pin: Mapping[str, Any],
    installed_skills: Sequence[str],
    retained_backup: Path | None,
) -> None:
    receipt = {
        "schema_name": "pngtopptx_automatic_install_receipt",
        "schema_version": "1.0.0",
        "installer_version": INSTALLER_VERSION,
        "canonical_repository": CANONICAL_REPOSITORY,
        "source_commit": PINNED_SOURCE_COMMIT,
        "combined_aggregate_sha256": pin["combined_aggregate_sha256"],
        "installed_skills": sorted(installed_skills),
        "retained_backup": retained_backup.name if retained_backup else None,
        "completed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    destination = target_root / ".pptxgenerator-pngtopptx-install.json"
    temporary = target_root / f".{destination.name}.{uuid.uuid4().hex}.tmp"
    temporary.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(destination)


def install_skillset(
    target_root: Path,
    *,
    pin: Mapping[str, Any],
    backup_and_replace: bool = False,
) -> dict[str, Any]:
    target = target_root.resolve(strict=False)
    _reject_repository_target(target)
    initial = inspect_installation(target, pin)
    mismatched = [
        row["skill_name"]
        for row in initial["skills"]
        if row["status"] == "MISMATCH"
    ]
    missing = [
        row["skill_name"]
        for row in initial["skills"]
        if row["status"] == "MISSING"
    ]
    if mismatched and not backup_and_replace:
        raise SkillsetInstallError(
            "PNGTPPTX_EXISTING_SKILL_MISMATCH",
            ", ".join(mismatched)
            + "; rerun with --backup-and-replace to retain a backup and install the pin",
        )
    if initial["status"] == "PASS":
        return {
            "status": "PASS",
            "action": "already_installed",
            "installation_root": str(target),
            "source_commit": PINNED_SOURCE_COMMIT,
            "combined_aggregate_sha256": pin["combined_aggregate_sha256"],
            "installed_skills": [],
            "retained_backup": None,
        }

    target.mkdir(parents=True, exist_ok=True)
    if _is_reparse_or_symlink(target):
        raise SkillsetInstallError("PNGTPPTX_TARGET_ROOT_INVALID", str(target))
    install_names = sorted(set(missing + mismatched))
    expected = _inventory_by_skill(pin)
    retained_backup: Path | None = None
    staging = target / f".pptxgenerator-pngtopptx-staging-{uuid.uuid4().hex}"
    staging.mkdir()
    try:
        with tempfile.TemporaryDirectory(
            prefix="pptxgenerator-pngtopptx-source-"
        ) as temporary_name:
            source_root = _verified_source(pin, Path(temporary_name))
            for skill_name in install_names:
                staged_skill = staging / skill_name
                shutil.copytree(source_root / skill_name, staged_skill)
                staged_status = _inspect_skill(
                    staged_skill,
                    skill_name=skill_name,
                    expected=expected[skill_name],
                )
                if staged_status["status"] != "PASS":
                    raise SkillsetInstallError(
                        "PNGTPPTX_STAGING_VERIFICATION_FAILED", skill_name
                    )

        backed_up: dict[str, Path] = {}
        installed_destinations: list[Path] = []
        if mismatched:
            timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
            retained_backup = target / (
                f".pptxgenerator-pngtopptx-backup-{timestamp}-{uuid.uuid4().hex[:8]}"
            )
            retained_backup.mkdir()
        try:
            for skill_name in mismatched:
                destination = target / skill_name
                assert retained_backup is not None
                backup_destination = retained_backup / skill_name
                destination.replace(backup_destination)
                backed_up[skill_name] = backup_destination
            for skill_name in install_names:
                destination = target / skill_name
                if destination.exists():
                    continue
                (staging / skill_name).replace(destination)
                installed_destinations.append(destination)
        except Exception:
            for destination in reversed(installed_destinations):
                if destination.exists():
                    destination.replace(staging / destination.name)
            for skill_name, backup_path in backed_up.items():
                destination = target / skill_name
                if backup_path.exists() and not destination.exists():
                    backup_path.replace(destination)
            raise

        final = inspect_installation(target, pin)
        if final["status"] != "PASS":
            raise SkillsetInstallError(
                "PNGTPPTX_POST_INSTALL_VERIFICATION_FAILED",
                json.dumps(final["skills"], ensure_ascii=False),
            )
        _write_receipt(
            target,
            pin=pin,
            installed_skills=install_names,
            retained_backup=retained_backup,
        )
        return {
            "status": "PASS",
            "action": "installed",
            "installation_root": str(target),
            "source_commit": PINNED_SOURCE_COMMIT,
            "combined_aggregate_sha256": pin["combined_aggregate_sha256"],
            "installed_skills": install_names,
            "retained_backup": (
                str(retained_backup) if retained_backup is not None else None
            ),
        }
    finally:
        if staging.is_dir():
            shutil.rmtree(staging)


def _default_target_root() -> Path:
    configured = os.environ.get("DECKCOMPILER_EXTERNAL_SKILLS")
    if configured:
        return Path(configured)
    codex_home = os.environ.get("CODEX_HOME")
    return (
        Path(codex_home) / "skills"
        if codex_home
        else Path.home() / ".codex" / "skills"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Install the release-pinned CAPTW/pngtopptx SkillSet."
    )
    parser.add_argument("--target-root", type=Path, default=_default_target_root())
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate the target without network access or installation.",
    )
    parser.add_argument(
        "--backup-and-replace",
        action="store_true",
        help="Move mismatched Skill directories to a retained backup before install.",
    )
    args = parser.parse_args(argv)
    try:
        pin = load_pin()
        if args.check:
            result = inspect_installation(args.target_root, pin)
            if result["status"] != "PASS":
                raise SkillsetInstallError(
                    "PNGTPPTX_INSTALLATION_NOT_READY", result["status"]
                )
        else:
            result = install_skillset(
                args.target_root,
                pin=pin,
                backup_and_replace=args.backup_and_replace,
            )
    except SkillsetInstallError as exc:
        print(
            json.dumps(
                {"status": "BLOCKED", "code": exc.code, "detail": exc.detail},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
