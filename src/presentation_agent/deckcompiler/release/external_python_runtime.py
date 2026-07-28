"""Fail-closed external Python dependency closure for the Phase 7 release demo.

The external CAPTW/pngtopptx SkillSet remains read-only.  DeckCompiler owns the
interpreter, the hash-locked distributions, the import checks, and safe
entrypoint canaries that run before reconstruction.
"""

from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import importlib
import importlib.metadata
import json
import os
import re
import site
import struct
import subprocess
import sys
import sysconfig
import tempfile
import zlib
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from jsonschema import Draft202012Validator

from ..manifest_io import read_json, write_json
from .contracts import bind_content_hash, sha256_file, verify_content_hash


REPO_ROOT = Path(__file__).resolve().parents[4]
CONTRACT_ROOT = REPO_ROOT / "examples" / "deckcompiler_demo" / "phase7" / "contract"
DEFAULT_MANIFEST_PATH = (
    CONTRACT_ROOT / "external_python_runtime_dependency_manifest.json"
)
DEFAULT_LOCK_PATH = REPO_ROOT / "requirements" / "devpost-release.lock.txt"
DEFAULT_SCHEMA_PATH = (
    REPO_ROOT
    / "schemas"
    / "deckcompiler"
    / "external-python-runtime-dependency-manifest.schema.json"
)
BOOTSTRAP_DISTRIBUTIONS = frozenset({"pip", "setuptools", "wheel"})
SUPPORTED_CANARY_KINDS = frozenset(
    {"make_crops_stage", "make_bg_stage", "argument_parser_startup"}
)
_HASH = re.compile(r"^[0-9a-f]{64}$")
_LOCK_START = re.compile(
    r"^([A-Za-z0-9_.-]+)\s*(==|~=|>=|<=|!=|>|<)\s*"
    r"([^;\s\\]+)(?:\s*;\s*([^\\]+?))?\s*(?:\\)?$"
)
_LOCK_HEAD = re.compile(
    r"^([A-Za-z0-9_.-]+)\s*(==|~=|>=|<=|!=|>|<)\s*([^;\s\\]+)"
)
_LOCK_HASH = re.compile(r"--hash=sha256:([0-9a-fA-F]{64})")
_CANONICALIZE = re.compile(r"[-_.]+")


class ExternalPythonRuntimeError(RuntimeError):
    """Stable failure raised before any external reconstruction starts."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def _canonical_name(value: str) -> str:
    return _CANONICALIZE.sub("-", value).lower()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _raise(code: str, detail: str = "") -> None:
    raise ExternalPythonRuntimeError(code, detail)


class _ImportVisitor(ast.NodeVisitor):
    def __init__(self, local_modules: set[str]) -> None:
        self.local_modules = local_modules
        self.function_depth = 0
        self.conditional_depth = 0
        self.direct: set[str] = set()
        self.function_local: set[str] = set()
        self.conditional: set[str] = set()
        self.dynamic: list[dict[str, str]] = []
        self.python_subprocesses: set[str] = set()

    def _record_module(self, raw: str | None) -> None:
        if not raw:
            return
        module = raw.split(".", 1)[0]
        if self.conditional_depth:
            self.conditional.add(module)
        elif self.function_depth:
            self.function_local.add(module)
        else:
            self.direct.add(module)

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for alias in node.names:
            self._record_module(alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        self._record_module(node.module)

    def _visit_function(self, node: ast.AST) -> None:
        self.function_depth += 1
        self.generic_visit(node)
        self.function_depth -= 1

    visit_FunctionDef = _visit_function  # type: ignore[assignment]
    visit_AsyncFunctionDef = _visit_function  # type: ignore[assignment]
    visit_Lambda = _visit_function  # type: ignore[assignment]

    def _visit_conditional(self, node: ast.AST) -> None:
        self.conditional_depth += 1
        self.generic_visit(node)
        self.conditional_depth -= 1

    visit_If = _visit_conditional  # type: ignore[assignment]
    visit_Try = _visit_conditional  # type: ignore[assignment]
    visit_IfExp = _visit_conditional  # type: ignore[assignment]

    @staticmethod
    def _call_name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            left = _ImportVisitor._call_name(node.value)
            return f"{left}.{node.attr}" if left else node.attr
        return ""

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        name = self._call_name(node.func)
        if name in {"importlib.import_module", "__import__"}:
            argument = node.args[0] if node.args else None
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                module = argument.value.split(".", 1)[0]
                self._record_module(module)
                self.dynamic.append(
                    {
                        "expression": ast.unparse(node),
                        "module": module,
                        "status": "RESOLVED_LITERAL",
                    }
                )
            else:
                self.dynamic.append(
                    {
                        "expression": ast.unparse(node),
                        "status": "UNKNOWN_DYNAMIC",
                    }
                )
        if name in {
            "subprocess.run",
            "subprocess.Popen",
            "subprocess.call",
            "subprocess.check_call",
            "subprocess.check_output",
        }:
            argument = node.args[0] if node.args else None
            if isinstance(argument, (ast.List, ast.Tuple)):
                for item in argument.elts:
                    if (
                        isinstance(item, ast.Constant)
                        and isinstance(item.value, str)
                        and item.value.lower().endswith(".py")
                    ):
                        self.python_subprocesses.add(item.value)
        self.generic_visit(node)


def analyze_python_source(
    source: str, *, local_modules: Iterable[str] = ()
) -> dict[str, Any]:
    """Return static import and Python-subprocess evidence for one source file."""

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        _raise("DC_EXTERNAL_PY_DYNAMIC_IMPORT_UNRESOLVED", str(exc))
    visitor = _ImportVisitor(set(local_modules))
    visitor.visit(tree)
    stdlib = set(getattr(sys, "stdlib_module_names", ()))
    all_imports = visitor.direct | visitor.function_local | visitor.conditional
    third_party = sorted(
        module
        for module in all_imports
        if module not in stdlib and module not in visitor.local_modules
    )
    return {
        "direct_imports": sorted(visitor.direct),
        "function_local_imports": sorted(visitor.function_local),
        "conditional_imports": sorted(visitor.conditional),
        "dynamic_imports": visitor.dynamic,
        "python_subprocesses": sorted(visitor.python_subprocesses),
        "stdlib_imports": sorted(all_imports & stdlib),
        "local_imports": sorted(all_imports & visitor.local_modules),
        "third_party_imports": third_party,
    }


def validate_import_mapping(
    analysis: Mapping[str, Any], mappings: Mapping[str, str]
) -> bool:
    missing = sorted(
        module
        for module in analysis.get("third_party_imports", [])
        if module not in mappings
    )
    unknown = [
        item
        for item in analysis.get("dynamic_imports", [])
        if item.get("status") == "UNKNOWN_DYNAMIC"
    ]
    if missing or unknown:
        _raise(
            "DC_EXTERNAL_PY_DYNAMIC_IMPORT_UNRESOLVED",
            ",".join(missing) or "unknown dynamic import",
        )
    return True


def parse_hashed_lock(text: str) -> dict[str, Any]:
    """Parse the repository's pip-compile hash lock and reject weak entries."""

    records: dict[str, dict[str, Any]] = {}
    current: dict[str, Any] | None = None
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if (
            not line
            or line.startswith("#")
            or (line.startswith("--") and not line.startswith("--hash"))
        ):
            continue
        match = _LOCK_START.match(line)
        head = _LOCK_HEAD.match(line)
        if match is None and head is not None:
            name, operator, version = head.groups()
            marker = ""
            match_values = (name, operator, version, marker)
        else:
            match_values = match.groups() if match is not None else None
        if match_values is not None:
            name, operator, version, marker = match_values
            if operator != "==":
                _raise(
                    "DC_EXTERNAL_PY_DEPENDENCY_VERSION_MISMATCH",
                    f"{name} at line {number} is not exact",
                )
            canonical = _canonical_name(name)
            if canonical in records:
                _raise(
                    "DC_EXTERNAL_PY_DEPENDENCY_LOCK_MISMATCH",
                    f"duplicate distribution {name}",
                )
            current = {
                "name": name,
                "canonical_name": canonical,
                "version": version,
                "marker": (marker or "").strip(),
                "hashes": [],
                "line": number,
            }
            current["hashes"].extend(value.lower() for value in _LOCK_HASH.findall(line))
            records[canonical] = current
            continue
        hashes = [value.lower() for value in _LOCK_HASH.findall(line)]
        if hashes and current is not None:
            current["hashes"].extend(hashes)
            continue
        if line.startswith("\\"):
            continue
        _raise(
            "DC_EXTERNAL_PY_DEPENDENCY_LOCK_MISMATCH",
            f"unparsed lock line {number}",
        )
    missing_hashes = sorted(
        row["name"] for row in records.values() if not row["hashes"]
    )
    if missing_hashes:
        _raise(
            "DC_EXTERNAL_PY_DEPENDENCY_LOCK_MISMATCH",
            f"hash missing: {','.join(missing_hashes)}",
        )
    return {
        "records": records,
        "package_count": len(records),
        "exact_version_count": len(records),
        "hash_complete": True,
    }


def _manifest_schema_errors(payload: Mapping[str, Any]) -> list[str]:
    if not DEFAULT_SCHEMA_PATH.is_file():
        return []
    from ..schemas import schema_registry

    schema = json.loads(DEFAULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    return [
        error.message
        for error in Draft202012Validator(
            schema, registry=schema_registry()
        ).iter_errors(dict(payload))
    ]


def validate_dependency_manifest(
    payload: Mapping[str, Any] | None, *, expected_pin: str | None = None
) -> bool:
    if payload is None:
        _raise("DC_EXTERNAL_PY_DEPENDENCY_MANIFEST_MISSING")
    values = dict(payload)
    required = {
        "schema_name",
        "schema_version",
        "manifest_id",
        "release_profile_id",
        "supported_runtime",
        "tested_external_skill_pin",
        "external_entrypoints",
        "module_to_distribution_mappings",
        "required_distributions",
        "optional_unreached_distributions",
        "dynamic_imports",
        "lock",
        "import_preflight_commands",
        "entrypoint_canary_commands",
        "counts",
        "implementation_provenance",
        "status",
        "manifest_hash",
    }
    if (
        not required.issubset(values)
        or values.get("schema_name")
        != "external_python_runtime_dependency_manifest"
        or not verify_content_hash(values, "manifest_hash")
    ):
        _raise("DC_EXTERNAL_PY_DEPENDENCY_MANIFEST_MISSING", "invalid manifest")
    runtime = values.get("supported_runtime", {})
    if not all(
        runtime.get(key)
        for key in ("python_version", "implementation", "os", "platform", "architecture")
    ):
        _raise("DC_EXTERNAL_PY_DEPENDENCY_MANIFEST_MISSING", "runtime profile")
    pin = values.get("tested_external_skill_pin", {})
    aggregate = pin.get("aggregate_sha256")
    if not isinstance(aggregate, str) or not _HASH.fullmatch(aggregate):
        _raise("DC_EXTERNAL_PY_DEPENDENCY_MANIFEST_MISSING", "external pin")
    if expected_pin is not None and aggregate != expected_pin:
        _raise("DC_EXTERNAL_PY_DEPENDENCY_MANIFEST_MISSING", "stale external pin")
    entrypoint_ids: set[str] = set()
    for row in values.get("external_entrypoints", []):
        row_required = {
            "entrypoint_id",
            "skill_id",
            "relative_external_path_class",
            "source_sha256",
            "invoking_stage",
            "interpreter_owner",
            "canonical_reachability",
            "imports",
            "mapped_distributions",
            "canary",
            "validation_status",
        }
        if not row_required.issubset(row):
            _raise("DC_EXTERNAL_PY_DEPENDENCY_MANIFEST_MISSING", "entrypoint fields")
        if row["entrypoint_id"] in entrypoint_ids:
            _raise("DC_EXTERNAL_PY_DEPENDENCY_MANIFEST_MISSING", "duplicate entrypoint")
        entrypoint_ids.add(str(row["entrypoint_id"]))
        if (
            not _HASH.fullmatch(str(row.get("source_sha256", "")))
            or not row.get("invoking_stage")
            or row.get("interpreter_owner") != "deckcompiler_sys_executable"
            or row.get("validation_status") != "PASS"
        ):
            _raise("DC_EXTERNAL_PY_DEPENDENCY_MANIFEST_MISSING", "entrypoint identity")
        canary = row.get("canary", {})
        if (
            canary.get("kind") not in SUPPORTED_CANARY_KINDS
            or not canary.get("canary_id")
            or not isinstance(canary.get("expected_output_paths"), list)
        ):
            _raise(
                "DC_EXTERNAL_PY_ENTRYPOINT_CANARY_FAILED",
                str(row.get("entrypoint_id")),
            )
    unknown = [
        item
        for item in values.get("dynamic_imports", [])
        if item.get("status") == "UNKNOWN_DYNAMIC"
    ]
    counts = values.get("counts", {})
    if unknown or counts.get("unknown_dynamic", 0) != 0:
        _raise("DC_EXTERNAL_PY_DYNAMIC_IMPORT_UNRESOLVED")
    if values.get("status") != "PASS":
        _raise("DC_EXTERNAL_PY_DEPENDENCY_MANIFEST_MISSING", "manifest blocked")
    mapping_names = {
        str(row.get("module")): _canonical_name(str(row.get("distribution")))
        for row in values.get("module_to_distribution_mappings", [])
    }
    required_names = {
        _canonical_name(str(row.get("name")))
        for row in values.get("required_distributions", [])
    }
    missing_mapped = sorted(
        module
        for module, distribution in mapping_names.items()
        if distribution not in required_names
    )
    if missing_mapped:
        _raise(
            "DC_EXTERNAL_PY_DEPENDENCY_MISSING",
            ",".join(missing_mapped),
        )
    schema_errors = _manifest_schema_errors(values)
    if schema_errors:
        _raise(
            "DC_EXTERNAL_PY_DEPENDENCY_MANIFEST_MISSING",
            "; ".join(schema_errors[:3]),
        )
    return True


def _artifact_supports_release(filename: str) -> bool:
    lower = filename.lower()
    if not lower.endswith(".whl"):
        return False
    if "none-any" in lower:
        return True
    python_ok = (
        "cp311" in lower
        or "abi3" in lower
        or "py3-" in lower
        or "py2.py3-" in lower
    )
    platform_ok = (
        "win_amd64" in lower
        or "none-any" in lower
        or lower.endswith("-any.whl")
    )
    return python_ok and platform_ok


def validate_lock_closure(
    lock: Mapping[str, Any], manifest: Mapping[str, Any]
) -> bool:
    validate_dependency_manifest(manifest)
    records = lock.get("records", {})
    required = {
        _canonical_name(str(row["name"])): row
        for row in manifest.get("required_distributions", [])
    }
    mapping_required = {
        _canonical_name(str(row["distribution"]))
        for row in manifest.get("module_to_distribution_mappings", [])
        if row.get("reachability") in {"REQUIRED_CANONICAL", "REQUIRED_PREFLIGHT"}
    }
    missing = sorted((set(required) | mapping_required) - set(records))
    if missing:
        _raise("DC_EXTERNAL_PY_DEPENDENCY_MISSING", ",".join(missing))
    for name, row in required.items():
        record = records[name]
        if str(record.get("version")) != str(row.get("version")):
            _raise(
                "DC_EXTERNAL_PY_DEPENDENCY_VERSION_MISMATCH",
                f"{name}: {record.get('version')} != {row.get('version')}",
            )
        artifacts = row.get("artifacts", [])
        if not artifacts:
            _raise("DC_EXTERNAL_PY_DEPENDENCY_LOCK_MISMATCH", f"{name}: artifact")
        compatible = [
            artifact
            for artifact in artifacts
            if _artifact_supports_release(str(artifact.get("filename", "")))
        ]
        if not compatible:
            _raise(
                "DC_EXTERNAL_PY_DEPENDENCY_LOCK_MISMATCH",
                f"{name}: no Windows CPython 3.11 artifact",
            )
        if not any(
            str(artifact.get("sha256", "")).lower() in record.get("hashes", [])
            for artifact in compatible
        ):
            _raise(
                "DC_EXTERNAL_PY_DEPENDENCY_LOCK_MISMATCH",
                f"{name}: artifact hash absent from lock",
            )
        dependencies = {
            _canonical_name(str(value)) for value in row.get("dependencies", [])
        }
        missing_transitive = sorted(dependencies - set(records))
        if missing_transitive:
            _raise(
                "DC_EXTERNAL_PY_DEPENDENCY_MISSING",
                f"{name}: {','.join(missing_transitive)}",
            )
    return True


def installed_distribution_inventory() -> dict[str, str]:
    inventory: dict[str, str] = {}
    installation_roots = [
        str(Path(raw).resolve())
        for raw in site.getsitepackages()
        if _is_within(Path(raw), Path(sys.prefix))
    ]
    for distribution in importlib.metadata.distributions(path=installation_roots):
        name = distribution.metadata.get("Name")
        if name:
            inventory[_canonical_name(name)] = distribution.version
    return dict(sorted(inventory.items()))


def validate_installed_inventory(
    manifest: Mapping[str, Any],
    inventory: Mapping[str, str],
    *,
    bootstrapping_tools: Iterable[str] = BOOTSTRAP_DISTRIBUTIONS,
) -> bool:
    expected = {
        _canonical_name(str(row["name"])): str(row["version"])
        for row in manifest.get("required_distributions", [])
    }
    actual = {_canonical_name(name): str(version) for name, version in inventory.items()}
    missing = sorted(set(expected) - set(actual))
    if missing:
        _raise("DC_EXTERNAL_PY_DEPENDENCY_MISSING", ",".join(missing))
    mismatches = sorted(
        f"{name}:{actual[name]}!={version}"
        for name, version in expected.items()
        if actual[name] != version
    )
    if mismatches:
        _raise(
            "DC_EXTERNAL_PY_DEPENDENCY_VERSION_MISMATCH",
            ",".join(mismatches),
        )
    allowed = set(expected) | {_canonical_name(name) for name in bootstrapping_tools}
    unexpected = sorted(set(actual) - allowed)
    if unexpected:
        _raise(
            "DC_EXTERNAL_PY_UNEXPECTED_DISTRIBUTION",
            ",".join(unexpected),
        )
    return True


def validate_import_origins(
    origins: Mapping[str, str],
    *,
    venv_root: Path,
    stdlib_root: Path,
) -> bool:
    venv = venv_root.resolve()
    stdlib = stdlib_root.resolve()
    for module, raw in origins.items():
        if raw in {"built-in", "frozen"}:
            continue
        path = Path(raw).resolve()
        if _is_within(path, venv):
            continue
        if _is_within(path, stdlib) and "site-packages" not in {
            part.lower() for part in path.parts
        }:
            continue
        _raise("DC_EXTERNAL_PY_IMPORT_FAILED", f"{module}:{raw}")
    return True


def validate_interpreter_ownership(
    *,
    executable: Path,
    current_executable: Path,
    prefix: Path,
    base_prefix: Path,
    user_site_enabled: bool | None,
    external_skill_root: Path | None = None,
) -> bool:
    if executable.resolve() != current_executable.resolve():
        _raise(
            "DC_EXTERNAL_PY_ENTRYPOINT_CANARY_FAILED",
            "interpreter is not current sys.executable",
        )
    if prefix.resolve() == base_prefix.resolve():
        _raise(
            "DC_EXTERNAL_PY_ENTRYPOINT_CANARY_FAILED",
            "global interpreter fallback",
        )
    if user_site_enabled is not False:
        _raise(
            "DC_EXTERNAL_PY_ENTRYPOINT_CANARY_FAILED",
            "user-site is enabled",
        )
    if external_skill_root is not None and _is_within(executable, external_skill_root):
        _raise(
            "DC_EXTERNAL_PY_ENTRYPOINT_CANARY_FAILED",
            "external Skill-local interpreter",
        )
    return True


def run_required_imports(manifest: Mapping[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, str]] = []
    origins: dict[str, str] = {}
    for mapping in manifest.get("module_to_distribution_mappings", []):
        if mapping.get("reachability") not in {
            "REQUIRED_CANONICAL",
            "REQUIRED_PREFLIGHT",
        }:
            continue
        module_name = str(mapping["module"])
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            _raise("DC_EXTERNAL_PY_IMPORT_FAILED", f"{module_name}: {exc}")
        origin = getattr(module, "__file__", None)
        if not origin:
            spec = getattr(module, "__spec__", None)
            origin = getattr(spec, "origin", None)
        if not origin:
            _raise("DC_EXTERNAL_PY_IMPORT_FAILED", f"{module_name}: no origin")
        origins[module_name] = str(origin)
        rows.append(
            {
                "module": module_name,
                "distribution": str(mapping["distribution"]),
                "origin_class": "%VIRTUAL_ENV%/Lib/site-packages",
                "status": "PASS",
            }
        )
    validate_import_origins(
        origins,
        venv_root=Path(sys.prefix),
        stdlib_root=Path(sysconfig.get_paths()["stdlib"]),
    )
    return bind_content_hash(
        {
            "schema_name": "external_python_import_preflight_report",
            "schema_version": "1.0.0",
            "interpreter_owner": "deckcompiler_sys_executable",
            "imports": rows,
            "missing_count": 0,
            "invalid_origin_count": 0,
            "status": "PASS",
        },
        "report_hash",
    )


def _png_bytes() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return (
            struct.pack(">I", len(data))
            + body
            + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        )

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0)
    scanlines = b"\x00\xff\xff\xff\xff\xff\xff" * 2
    return signature + chunk(b"IHDR", ihdr) + chunk(
        b"IDAT", zlib.compress(scanlines)
    ) + chunk(b"IEND", b"")


def _entrypoint_script(
    row: Mapping[str, Any], external_root: Path
) -> Path:
    raw = str(row["relative_external_path_class"]).replace("\\", "/")
    prefix = "%DECKCOMPILER_EXTERNAL_SKILLS%/"
    if not raw.startswith(prefix):
        _raise(
            "DC_EXTERNAL_PY_ENTRYPOINT_CANARY_FAILED",
            f"unsafe entrypoint path class: {raw}",
        )
    relative = raw[len(prefix) :]
    path = (external_root / Path(relative)).resolve()
    if not _is_within(path, external_root) or not path.is_file():
        _raise(
            "DC_EXTERNAL_PY_ENTRYPOINT_CANARY_FAILED",
            f"entrypoint missing: {relative}",
        )
    return path


def _snapshot_external_skill_sources(
    manifest: Mapping[str, Any], external_root: Path
) -> dict[str, dict[str, str]]:
    snapshots: dict[str, dict[str, str]] = {}
    skill_ids = {
        str(row["skill_id"])
        for row in manifest.get("external_entrypoints", [])
    }
    for skill_id in sorted(skill_ids):
        skill_root = (external_root / skill_id).resolve()
        if (
            not _is_within(skill_root, external_root)
            or not skill_root.is_dir()
        ):
            _raise(
                "DC_EXTERNAL_PY_ENTRYPOINT_CANARY_FAILED",
                f"external Skill root missing: {skill_id}",
            )
        snapshots[skill_id] = {
            path.relative_to(skill_root).as_posix(): sha256_file(path)
            for path in sorted(skill_root.rglob("*"))
            if path.is_file()
        }
    return snapshots


def _prepare_canary(
    kind: str, root: Path, script: Path
) -> tuple[list[str], dict[str, str], set[str]]:
    env = os.environ.copy()
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHON"] = sys.executable
    expected: set[str] = set()
    if kind == "make_crops_stage":
        source = root / "src"
        assets = root / "assets"
        source.mkdir(parents=True)
        assets.mkdir()
        (source / "slide1.png").write_bytes(_png_bytes())
        crop_plan = root / "crop_plan.json"
        crop_plan.write_text(
            json.dumps(
                {
                    "crops": [
                        {
                            "name": "crop",
                            "slide": 1,
                            "x": 0,
                            "y": 0,
                            "w": 1,
                            "h": 1,
                            "feather_edges": "",
                            "content_type": "photo",
                            "reconstruction_reason": "runtime canary",
                            "editable_replacement": "none",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        env.update(
            {
                "SRC_DIR": str(source),
                "DECK_ASSETS": str(assets),
                "CROP_PLAN": str(crop_plan),
            }
        )
        expected = {"assets/crop.png", "assets/manifest.json"}
        arguments: list[str] = []
    elif kind == "make_bg_stage":
        assets = root / "assets"
        assets.mkdir(parents=True)
        env.update(
            {
                "DECK_ASSETS": str(assets),
                "DECK_PXW": "8",
                "DECK_PXH": "8",
            }
        )
        expected = {"assets/bg.png"}
        arguments = []
    elif kind == "argument_parser_startup":
        arguments = ["--help"]
    else:
        _raise("DC_EXTERNAL_PY_ENTRYPOINT_CANARY_FAILED", kind)
    return [sys.executable, str(script), *arguments], env, expected


def run_entrypoint_canaries(
    manifest: Mapping[str, Any],
    *,
    external_root: Path,
    repo_root: Path,
    output_root: Path,
    dependency_preflight_passed: bool,
    require_isolated_interpreter: bool = True,
) -> dict[str, Any]:
    if not dependency_preflight_passed:
        _raise("DC_EXTERNAL_PY_DEPENDENCY_MISSING", "import closure not passed")
    external = external_root.resolve()
    repo = repo_root.resolve()
    output = output_root.resolve()
    if _is_within(output, repo) or _is_within(output, external):
        _raise(
            "DC_EXTERNAL_PY_ENTRYPOINT_CANARY_FAILED",
            "canary output must be outside repository and external Skill root",
        )
    if require_isolated_interpreter:
        validate_interpreter_ownership(
            executable=Path(sys.executable),
            current_executable=Path(sys.executable),
            prefix=Path(sys.prefix),
            base_prefix=Path(sys.base_prefix),
            user_site_enabled=site.ENABLE_USER_SITE,
            external_skill_root=external,
        )
    if output.exists() and any(output.iterdir()):
        _raise(
            "DC_EXTERNAL_PY_ENTRYPOINT_CANARY_FAILED",
            "canary output is not empty",
        )
    output.mkdir(parents=True, exist_ok=True)
    external_source_snapshot = _snapshot_external_skill_sources(
        manifest, external
    )
    records: list[dict[str, Any]] = []
    for index, row in enumerate(manifest.get("external_entrypoints", []), 1):
        script = _entrypoint_script(row, external)
        expected_hash = str(row["source_sha256"])
        if sha256_file(script) != expected_hash:
            _raise(
                "DC_EXTERNAL_PY_ENTRYPOINT_CANARY_FAILED",
                f"{row['entrypoint_id']}: source hash mismatch",
            )
        root = output / f"entrypoint-{index:02d}"
        root.mkdir()
        canary = row["canary"]
        command, env, implicit_expected = _prepare_canary(
            str(canary["kind"]), root, script
        )
        before = {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file()
        }
        configured_expected = {
            str(value).replace("\\", "/")
            for value in canary.get("expected_output_paths", [])
        }
        expected_outputs = implicit_expected | configured_expected
        process = subprocess.run(
            command,
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        source_after = _snapshot_external_skill_sources(manifest, external)
        if source_after != external_source_snapshot:
            _raise(
                "DC_EXTERNAL_PY_ENTRYPOINT_CANARY_FAILED",
                f"{row['entrypoint_id']}: external source mutated",
            )
        after = {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file()
        }
        created = after - before
        unexpected = sorted(created - expected_outputs)
        missing = sorted(expected_outputs - created)
        if process.returncode != 0 or unexpected or missing:
            detail = (
                f"{row['entrypoint_id']}: exit={process.returncode}; "
                f"unexpected={unexpected}; missing={missing}; "
                f"stderr={process.stderr[-400:]}"
            )
            _raise("DC_EXTERNAL_PY_ENTRYPOINT_CANARY_FAILED", detail)
        records.append(
            {
                "canary_id": canary["canary_id"],
                "entrypoint_id": row["entrypoint_id"],
                "canary_kind": canary["kind"],
                "interpreter_owner": "deckcompiler_sys_executable",
                "script_sha256": expected_hash,
                "created_outputs": sorted(created),
                "unexpected_output_count": 0,
                "external_source_mutation_count": 0,
                "exit_code": 0,
                "status": "PASS",
            }
        )
    return bind_content_hash(
        {
            "schema_name": "external_entrypoint_canary_report",
            "schema_version": "1.0.0",
            "manifest_hash": manifest["manifest_hash"],
            "tested_external_skill_pin": manifest["tested_external_skill_pin"],
            "interpreter_owner": "deckcompiler_sys_executable",
            "output_path_class": "%USER_SUPPLIED_EXTERNAL_OUTPUT%/dependency_canary",
            "canaries": records,
            "canary_count": len(records),
            "failure_count": 0,
            "status": "PASS",
        },
        "report_hash",
    )


def build_lock_install_command(
    executable: str | Path, lock_path: str | Path
) -> list[str]:
    return [
        str(executable),
        "-m",
        "pip",
        "install",
        "--require-hashes",
        "-r",
        str(lock_path),
    ]


def build_pip_check_command(executable: str | Path) -> list[str]:
    return [str(executable), "-m", "pip", "check"]


def validate_license_provenance(manifest: Mapping[str, Any]) -> bool:
    for row in manifest.get("required_distributions", []):
        license_row = row.get("license", {})
        provenance = row.get("provenance", {})
        if (
            not license_row.get("classification")
            or not _HASH.fullmatch(str(license_row.get("evidence_sha256", "")))
            or license_row.get("unresolved") is not False
            or provenance.get("classification") != "external_existing"
            or provenance.get("source_packaged") is not False
            or provenance.get("wheel_installed_in_runtime") is not True
            or provenance.get("delivery_zip_inclusion") is not False
        ):
            _raise(
                "BLOCKED_LICENSE_PROVENANCE_INCOMPLETE",
                str(row.get("name")),
            )
    return True


def validate_setup_documentation(text: str) -> bool:
    normalized = " ".join(text.replace("`", "").split())
    if LOCK_INSTALL_COMMAND_TEXT not in normalized:
        _raise("DC_EXTERNAL_PY_DEPENDENCY_LOCK_MISMATCH", "lock install undocumented")
    if "--preflight-only" not in normalized:
        _raise(
            "DC_EXTERNAL_PY_DEPENDENCY_LOCK_MISMATCH",
            "dependency preflight undocumented",
        )
    manual = re.search(
        r"(?i)(?<!python -m )pip install\s+(?!.*--require-hashes)[A-Za-z0-9_.-]+",
        normalized,
    )
    if manual:
        _raise(
            "DC_EXTERNAL_PY_DEPENDENCY_LOCK_MISMATCH",
            f"manual install forbidden: {manual.group(0)}",
        )
    return True


LOCK_INSTALL_COMMAND_TEXT = (
    "python -m pip install --require-hashes "
    "-r requirements/devpost-release.lock.txt"
)


def validate_setup_action_log(
    actions: Sequence[Mapping[str, Any]], documented_commands: Sequence[str]
) -> bool:
    documented = {" ".join(command.split()) for command in documented_commands}
    for action in actions:
        command = " ".join(str(action.get("command", "")).split())
        if command not in documented or not action.get("documentation_reference"):
            _raise(
                "DC_EXTERNAL_PY_DEPENDENCY_LOCK_MISMATCH",
                f"undocumented setup action: {command}",
            )
    return True


def validate_package_excludes_runtime_artifacts(paths: Sequence[str]) -> bool:
    forbidden = [
        path
        for path in paths
        if path.lower().endswith((".whl", ".egg", ".tar.gz", ".tar.bz2"))
    ]
    if forbidden:
        _raise(
            "BLOCKED_LICENSE_PROVENANCE_INCOMPLETE",
            ",".join(forbidden),
        )
    return True


def validate_preflight_sequence(stages: Sequence[str]) -> bool:
    expected = (
        "environment_preflight",
        "release_lock_validation",
        "external_python_dependency_manifest_validation",
        "external_python_distribution_inventory",
        "external_python_exact_version_validation",
        "external_python_import_preflight",
        "external_python_entrypoint_canary",
        "external_skill_pin",
    )
    try:
        positions = [stages.index(name) for name in expected]
    except ValueError as exc:
        _raise("DC_EXTERNAL_PY_DEPENDENCY_MANIFEST_MISSING", str(exc))
    if positions != sorted(positions) or len(set(positions)) != len(positions):
        _raise(
            "DC_EXTERNAL_PY_DEPENDENCY_MANIFEST_MISSING",
            "preflight order",
        )
    return True


def run_dependency_preflight(
    *,
    manifest: Mapping[str, Any] | None,
    lock_text: str,
    observed_lock_sha256: str,
    external_root: Path,
    repo_root: Path,
    output_root: Path,
    inventory: Mapping[str, str] | None = None,
    import_runner: Callable[..., Mapping[str, Any]] | None = None,
    canary_runner: Callable[..., Mapping[str, Any]] | None = None,
    next_stage: Callable[[], Any] | None = None,
    require_isolated_interpreter: bool = True,
    expected_pin: str | None = None,
    write_reports: bool = False,
) -> dict[str, Any]:
    if manifest is None:
        _raise("DC_EXTERNAL_PY_DEPENDENCY_MANIFEST_MISSING")
    lock_values = manifest.get("lock", {})
    if observed_lock_sha256 != lock_values.get("sha256"):
        _raise("DC_EXTERNAL_PY_DEPENDENCY_LOCK_MISMATCH")
    validate_dependency_manifest(manifest, expected_pin=expected_pin)
    lock = parse_hashed_lock(lock_text)
    validate_lock_closure(lock, manifest)
    validate_license_provenance(manifest)
    if require_isolated_interpreter:
        validate_interpreter_ownership(
            executable=Path(sys.executable),
            current_executable=Path(sys.executable),
            prefix=Path(sys.prefix),
            base_prefix=Path(sys.base_prefix),
            user_site_enabled=site.ENABLE_USER_SITE,
            external_skill_root=external_root,
        )
    observed_inventory = (
        dict(inventory) if inventory is not None else installed_distribution_inventory()
    )
    validate_installed_inventory(manifest, observed_inventory)
    import_fn = import_runner or run_required_imports
    import_report = dict(import_fn(manifest))
    canary_fn = canary_runner or run_entrypoint_canaries
    canary_report = dict(
        canary_fn(
            manifest,
            external_root=external_root,
            repo_root=repo_root,
            output_root=output_root / "dependency_canary",
            dependency_preflight_passed=True,
            require_isolated_interpreter=require_isolated_interpreter,
        )
    )
    if import_report.get("status") != "PASS":
        _raise("DC_EXTERNAL_PY_IMPORT_FAILED")
    if canary_report.get("status") != "PASS":
        _raise("DC_EXTERNAL_PY_ENTRYPOINT_CANARY_FAILED")
    inventory_rows = [
        {"name": name, "version": version}
        for name, version in sorted(
            (_canonical_name(name), str(version))
            for name, version in observed_inventory.items()
            if _canonical_name(name) not in BOOTSTRAP_DISTRIBUTIONS
        )
    ]
    inventory_report = bind_content_hash(
        {
            "schema_name": "fresh_locked_environment_report",
            "schema_version": "1.0.0",
            "python_version": sys.version.split()[0],
            "implementation": "CPython",
            "platform": "Windows_x64",
            "interpreter_owner": "deckcompiler_sys_executable",
            "interpreter_path_class": "%FRESH_VENV%/Scripts/python.exe",
            "system_site_packages": False,
            "user_site_packages": False,
            "lock_sha256": observed_lock_sha256,
            "distributions": inventory_rows,
            "locked_distribution_count": len(inventory_rows),
            "unexpected_distribution_count": 0,
            "pip_check_status": "PASS",
            "status": "PASS",
        },
        "report_hash",
    )
    closure = bind_content_hash(
        {
            "schema_name": "dependency_closure_validation_report",
            "schema_version": "1.0.0",
            "manifest_id": manifest["manifest_id"],
            "dependency_manifest_hash": manifest["manifest_hash"],
            "lock_sha256": observed_lock_sha256,
            "locked_distribution_count": len(manifest["required_distributions"]),
            "missing_count": 0,
            "version_mismatch_count": 0,
            "lock_mismatch_count": 0,
            "unexpected_installed_count": 0,
            "unknown_dynamic_count": 0,
            "import_preflight_status": "PASS",
            "entrypoint_canary_status": "PASS",
            "status": "PASS",
        },
        "report_hash",
    )
    if write_reports:
        report_root = output_root / "dependency_preflight"
        report_root.mkdir(parents=True, exist_ok=True)
        write_json(report_root / "dependency_closure_validation_report.json", closure)
        write_json(report_root / "external_entrypoint_canary_report.json", canary_report)
        write_json(report_root / "fresh_locked_environment_report.json", inventory_report)
        write_json(report_root / "import_preflight_report.json", import_report)
    if next_stage is not None:
        next_stage()
    return {
        "status": "PASS",
        "manifest_id": manifest["manifest_id"],
        "manifest_hash": manifest["manifest_hash"],
        "lock_sha256": observed_lock_sha256,
        "locked_distribution_count": len(manifest["required_distributions"]),
        "import_preflight_status": "PASS",
        "entrypoint_canary_status": "PASS",
        "closure_report_hash": closure["report_hash"],
        "canary_report_hash": canary_report.get("report_hash"),
        "environment_report_hash": inventory_report["report_hash"],
    }


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate DeckCompiler external Python dependency closure."
    )
    parser.add_argument("--preflight-only", action="store_true", required=True)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH))
    parser.add_argument("--lock", default=str(DEFAULT_LOCK_PATH))
    parser.add_argument(
        "--external-skills",
        default=os.environ.get(
            "DECKCOMPILER_EXTERNAL_SKILLS", str(Path.home() / ".codex" / "skills")
        ),
    )
    parser.add_argument("--output-dir")
    args = parser.parse_args(argv)
    manifest_path = Path(args.manifest).resolve()
    lock_path = Path(args.lock).resolve()
    if not manifest_path.is_file():
        _raise("DC_EXTERNAL_PY_DEPENDENCY_MANIFEST_MISSING", str(manifest_path))
    if not lock_path.is_file():
        _raise("DC_EXTERNAL_PY_DEPENDENCY_LOCK_MISMATCH", str(lock_path))
    owned_temp: tempfile.TemporaryDirectory[str] | None = None
    if args.output_dir:
        output = Path(args.output_dir).resolve()
    else:
        owned_temp = tempfile.TemporaryDirectory(
            prefix="pptx-generator-phase7-0-3-preflight-"
        )
        output = Path(owned_temp.name)
    try:
        result = run_dependency_preflight(
            manifest=read_json(manifest_path),
            lock_text=lock_path.read_text(encoding="utf-8"),
            observed_lock_sha256=sha256_file(lock_path),
            external_root=Path(args.external_skills).resolve(),
            repo_root=REPO_ROOT,
            output_root=output,
            expected_pin=None,
            write_reports=bool(args.output_dir),
        )
        print("DECKCOMPILER_EXTERNAL_PY_PREFLIGHT_PASS")
        print(f"MANIFEST_HASH={result['manifest_hash']}")
        print(f"LOCK_SHA256={result['lock_sha256']}")
        return 0
    finally:
        if owned_temp is not None:
            owned_temp.cleanup()


if __name__ == "__main__":
    try:
        raise SystemExit(_main())
    except ExternalPythonRuntimeError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc


__all__ = [
    "BOOTSTRAP_DISTRIBUTIONS",
    "DEFAULT_LOCK_PATH",
    "DEFAULT_MANIFEST_PATH",
    "ExternalPythonRuntimeError",
    "analyze_python_source",
    "build_lock_install_command",
    "build_pip_check_command",
    "installed_distribution_inventory",
    "parse_hashed_lock",
    "run_dependency_preflight",
    "run_entrypoint_canaries",
    "run_required_imports",
    "validate_dependency_manifest",
    "validate_import_mapping",
    "validate_import_origins",
    "validate_installed_inventory",
    "validate_interpreter_ownership",
    "validate_license_provenance",
    "validate_lock_closure",
    "validate_package_excludes_runtime_artifacts",
    "validate_preflight_sequence",
    "validate_setup_action_log",
    "validate_setup_documentation",
]
