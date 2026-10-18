"""Derive optional surface-call accounting from explicit renderer sourceRefs.

Tags transport unauthenticated claims, not semantic or serialization proof.
No tags keeps PR22's manual-ledger/absence behavior. A present malformed tag
fails closed. Unclaimed sources and untagged calls stay explicitly unresolved;
no overlap, text matching, or source-code interpretation creates attribution.
"""
from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from ..errors import DeckCompilerError
from ..identity import canonical_json_bytes, content_sha256
from ..manifest_io import write_json
from .region_classification_review import (
    CANDIDATE_COLLECTION, _bound_path, _exact, _json_object, _nonempty,
    _observations, bind_region_classification_review,
)
from .surface_call_accounting import (
    ACCOUNTING_NAME, AUTHORITY, _local_bytes, _sha,
    _validate_surface_call_accounting_data, validate_surface_call_accounting,
)


SCHEMA = "slide-image-dual-render.source-refs.v1"
COLLECTIONS = {"text_blocks", "suppressed_text", CANDIDATE_COLLECTION}
CLAIM_REASON = "Derived from explicit surface sourceRefs; semantic claims remain unverified"
_TRANSACTION = ContextVar("surface_call_accounting_transaction", default=None)


def _error(path, exc):
    return DeckCompilerError(
        code="DC_SURFACE_CALL_ACCOUNTING_INVALID", stage="reconstruction_completion",
        message=f"surface-call accounting sourceRefs are invalid: {exc}", artifact_path=path.as_posix())


def _file_identity(path):
    stat = path.stat()
    return stat.st_dev, stat.st_ino


def _owned_file(path, identity, digest):
    """A replaced or edited file is not ours, even when its bytes are equal."""
    try:
        return (not path.is_symlink() and path.is_file() and _file_identity(path) == identity
                and _sha(path.read_bytes()) == digest and _file_identity(path) == identity)
    except OSError:
        return False


def _record_write(path, identity, digest):
    transaction = _TRANSACTION.get()
    if transaction is not None:
        transaction["writes"][path] = (identity, digest)


def _manifest(root):
    path = root / "pngtopptx-project/out/native_object_manifest.json"
    if not path.exists() and not path.is_symlink():
        return None
    return _json_object(_local_bytes(root, path))


def _has_tags(native, slide):
    slides = native.get("slides") if isinstance(native, dict) else None
    row = slides.get(str(slide)) if isinstance(slides, dict) else None
    objects = row.get("objects") if isinstance(row, dict) else None
    return isinstance(objects, list) and any(isinstance(obj, dict) and "sourceRefs" in obj for obj in objects)


def _source(value, observations):
    _exact(value, {"collection", "observation_id"}, "sourceRefs source")
    _nonempty(value["collection"], "sourceRefs collection")
    _nonempty(value["observation_id"], "sourceRefs observation_id")
    ident = (value["collection"], value["observation_id"])
    if ident[0] not in COLLECTIONS or ident not in observations:
        raise ValueError("sourceRefs names an unknown namespaced observation")
    return ident


def _claim(tag, slide, bindings, observations):
    _exact(tag, {"schemaVersion", "slide", "bindings", "claim", "authority"}, "sourceRefs")
    if tag["schemaVersion"] != SCHEMA or type(tag["slide"]) is not int or not 0 < tag["slide"] <= 2**53 - 1 or tag["slide"] != slide:
        raise ValueError("sourceRefs schema/slide mismatch")
    _exact(tag["bindings"], set(bindings), "sourceRefs bindings")
    if content_sha256(tag["bindings"]) != content_sha256(bindings):
        raise ValueError("sourceRefs digests do not bind this job, image, inventory and review")
    _exact(tag["authority"], set(AUTHORITY), "sourceRefs authority")
    if any(v is not False for v in tag["authority"].values()):
        raise ValueError("sourceRefs must grant no authority")
    if len(canonical_json_bytes(tag)) > 65536:
        raise ValueError("sourceRefs exceeds the renderer's 64 KiB transport bound")
    claim = tag["claim"]
    if not isinstance(claim, dict):
        raise ValueError("sourceRefs claim must be an object")
    if claim.get("kind") == "extra":
        _exact(claim, {"kind", "groupId", "purpose"}, "sourceRefs extra")
        if claim["purpose"] not in ("decorative", "background", "unresolved"):
            raise ValueError("sourceRefs extra purpose is unsupported")
        identities = []
    else:
        _exact(claim, {"kind", "groupId", "source", "glyphMembers", "disposition"}, "sourceRefs observation")
        if claim["kind"] != "observation" or claim["disposition"] not in ("linked", "unresolved", "deferred"):
            raise ValueError("sourceRefs kind/disposition is unsupported")
        primary = _source(claim["source"], observations)
        members = claim["glyphMembers"]
        if not isinstance(members, list):
            raise ValueError("sourceRefs glyphMembers must be an array")
        identities = [primary]
        for member in members:
            ident = _source(member, observations)
            if ident[0] != CANDIDATE_COLLECTION or ident in identities:
                raise ValueError("sourceRefs duplicate or invalid glyph member")
            identities.append(ident)
        if members and (primary[0] == CANDIDATE_COLLECTION or claim["disposition"] != "linked"):
            raise ValueError("sourceRefs glyph members require a linked protected-text primary")
    _nonempty(claim["groupId"], "sourceRefs groupId")
    return claim, identities


def derive_surface_call_accounting(root: Path, job: dict, work_dir: Path) -> dict | None:
    """Return a consumer-validated deterministic ledger, without writing files."""
    root = root.resolve()
    path = work_dir / ACCOUNTING_NAME
    try:
        native = _manifest(root)
        if not _has_tags(native, job.get("slide_number")):
            if "source_ref_authoring" in job:
                raise ValueError("opted-in source-ref authoring requires at least one tagged surface row")
            return None
        if job.get("content_hash") != content_sha256({k: v for k, v in job.items() if k != "content_hash"}):
            raise ValueError("sourceRefs job content_hash is stale")
        review = bind_region_classification_review(root, job, work_dir)
        if review is None or content_sha256(review) != content_sha256(job.get("region_classification_review")):
            raise ValueError("sourceRefs requires the unchanged job-bound classification review")
        inventory_ref = job["vector_preflight"]["measurement_inventory"]
        inventory = _json_object(_bound_path(root, inventory_ref, "measurement_inventory").read_bytes())
        observations = _observations(inventory)
        slide = job["slide_number"]
        if type(slide) is not int or slide <= 0:
            raise ValueError("slide_number must be a positive integer")
        project = root / "pngtopptx-project"
        native_data = _local_bytes(root, project / "out/native_object_manifest.json")
        native = _json_object(native_data)
        trace_data = _local_bytes(root, project / "out/render_trace.json")
        trace = _json_object(trace_data)
        bindings = {
            "source_png_sha256": job["source_png"]["sha256"],
            "measurement_inventory_sha256": inventory_ref["sha256"],
            "review_artifact_sha256": review["review_artifact"]["sha256"],
            "fragment_sha256": _sha(_local_bytes(root, work_dir / f"s{slide}.fragment.js")),
            "integrated_slides_sha256": _sha(_local_bytes(root, project / "lib/slides.js")),
            "native_manifest_sha256": _sha(native_data), "render_trace_sha256": _sha(trace_data),
        }
        if (native.get("source") != "actual-render-surface-calls"
                or trace.get("projectRoot") != project.resolve().as_posix()
                or not isinstance(trace.get("hashes"), dict)
                or trace["hashes"].get("slidesJs") != bindings["integrated_slides_sha256"]
                or trace.get("nativeObjectManifestHash") != bindings["native_manifest_sha256"]):
            raise ValueError("sourceRefs manifest/trace/source binding mismatch")
        expected = {"jobContentHash": job["content_hash"], "sourcePngSha256": bindings["source_png_sha256"],
            "measurementInventorySha256": inventory_ref["sha256"], "reviewArtifactSha256": bindings["review_artifact_sha256"]}
        objects = native["slides"][str(slide)]["objects"]
        groups, owners = {}, {}
        # Validate every tag and its source identity before deriving any pointers.
        for index, obj in enumerate(objects):
            if not isinstance(obj, dict):
                raise ValueError("surface object must be an object")
            if "sourceRefs" not in obj:
                continue
            claim, identities = _claim(obj["sourceRefs"], slide, expected, observations)
            key = claim["groupId"]
            if key in groups and content_sha256(groups[key]["claim"]) != content_sha256(claim):
                raise ValueError("sourceRefs group claims conflict")
            for ident in identities:
                if ident in owners and owners[ident] != key:
                    raise ValueError("sourceRefs observation has duplicate group ownership")
                owners[ident] = key
            groups.setdefault(key, {"claim": claim, "indices": []})["indices"].append(index)
        ledger = {"schema_name": "codex_surface_call_accounting", "schema_version": "1.0.0",
            "job_id": job["job_id"], "job_content_hash": job["content_hash"], "slide_number": slide,
            "bindings": bindings, "groups": [], "unresolved": [], "extras": [], "authority": AUTHORITY.copy()}

        def pointer(index):
            return {"pointer": f"/slides/{slide}/objects/{index}", "object_sha256": content_sha256(objects[index])}

        for key, group in groups.items():
            claim = group["claim"]
            refs = [pointer(i) for i in group["indices"]]
            if claim["kind"] == "extra":
                ledger["extras"].extend({"object": r, "purpose": claim["purpose"], "reason": CLAIM_REASON} for r in refs)
            elif claim["disposition"] == "linked":
                ledger["groups"].append({"group_id": key, "source": claim["source"], "glyph_members": claim["glyphMembers"],
                    "objects": refs, "reason": CLAIM_REASON})
            else:
                ledger["unresolved"].append({"source": claim["source"], "disposition": claim["disposition"],
                    "objects": refs, "reason": CLAIM_REASON})
        for collection, ident in sorted(set(observations) - set(owners)):
            ledger["unresolved"].append({"source": {"collection": collection, "observation_id": ident},
                "disposition": "unresolved", "objects": [], "reason": "No explicit surface sourceRefs claim for this observation"})
        ledger["extras"].extend({"object": pointer(i), "purpose": "unresolved",
            "reason": "Surface call has no explicit sourceRefs; no attribution inferred"}
            for i, obj in enumerate(objects) if "sourceRefs" not in obj)
        _validate_surface_call_accounting_data(root, job, work_dir, canonical_json_bytes(ledger))
        return ledger
    except (OSError, ValueError, TypeError, KeyError, OverflowError, DeckCompilerError) as exc:
        raise _error(path, exc) from exc


def validate_source_ref_accounting(root: Path, job: dict, work_dir: Path) -> dict | None:
    """Completion rechecks annotations; it never creates missing accounting."""
    ledger = derive_surface_call_accounting(root, job, work_dir)
    result = validate_surface_call_accounting(root, job, work_dir)
    if ledger is not None:
        path = work_dir / ACCOUNTING_NAME
        try:
            if result is None:
                raise ValueError("annotated surface calls require a prepared ledger")
            if content_sha256(_json_object(_local_bytes(root.resolve(), path))) != content_sha256(ledger):
                raise ValueError("existing ledger disagrees with deterministic sourceRefs accounting")
        except (OSError, ValueError) as exc:
            raise _error(path, exc) from exc
    return result


def prepare_surface_call_accounting(root: Path, job: dict, work_dir: Path) -> dict | None:
    """Materialize only a fully validated absent ledger; never replace disagreement."""
    ledger = derive_surface_call_accounting(root, job, work_dir)
    path = work_dir / ACCOUNTING_NAME
    if ledger is None or path.exists() or path.is_symlink():
        return validate_source_ref_accounting(root, job, work_dir)
    ownership = None
    try:
        # Link an already atomically written staging file without replacing a
        # ledger that appeared after the absence check.
        with tempfile.TemporaryDirectory(dir=work_dir, prefix=".source-refs-") as staging:
            staged = write_json(Path(staging) / ACCOUNTING_NAME, ledger)
            # Capture the inode we created before exposing its name. The
            # destination may already be another writer's replacement afterward.
            ownership = (_file_identity(staged), _sha(staged.read_bytes()))
            os.link(staged, path)
            _record_write(path, *ownership)
        return validate_source_ref_accounting(root, job, work_dir)
    except (OSError, ValueError, DeckCompilerError) as exc:
        if ownership is not None and _owned_file(path, *ownership):
            path.unlink()
        raise _error(path, exc) from exc


def write_source_ref_receipt(path: Path, payload: dict) -> Path:
    """Track only this transaction's receipt write for conditional rollback."""
    transaction = _TRANSACTION.get()
    if transaction is None:
        return write_json(path, payload)
    try:
        before = transaction["before"][path]

        def unchanged():
            if before is None:
                return not path.exists() and not path.is_symlink()
            return _owned_file(path, before[1], _sha(before[0]))

        if not unchanged():
            raise ValueError("worker receipt changed during accounting finalization")
        with tempfile.TemporaryDirectory(dir=path.parent, prefix=".source-refs-receipt-") as staging:
            staged = write_json(Path(staging) / path.name, payload)
            ownership = (_file_identity(staged), _sha(staged.read_bytes()))
            if not unchanged():
                raise ValueError("worker receipt changed before accounting commit")
            if before is None:
                os.link(staged, path)
            else:
                staged.replace(path)
            _record_write(path, *ownership)
        return path
    except (OSError, ValueError, KeyError) as exc:
        raise _error(path, exc) from exc


@contextmanager
def source_ref_accounting_transaction(root: Path, manifest_name: str):
    """On opt-in finalization failure, restore ledger/receipt bytes only.

    Existing QA artifact transaction behavior is unchanged. No existing ledger
    is replaced during preparation, and all derived data passes the consumer
    before the atomic writer is called.
    """
    root = root.resolve()
    saved = {}
    try:
        native = _manifest(root)
        slides = native.get("slides", {}) if isinstance(native, dict) else {}
        active = isinstance(slides, dict) and any(_has_tags(native, slide) for slide in slides)
        if active:
            manifest = _json_object(_local_bytes(root, root / "pngtopptx-project/work" / manifest_name))
            for row in manifest["jobs"]:
                job_path = _bound_path(root, row["job"], "reconstruction job")
                for name in (ACCOUNTING_NAME, "worker_receipt.json"):
                    path = job_path.parent / name
                    if path.exists() or path.is_symlink():
                        data = _local_bytes(root, path)
                        identity = _file_identity(path)
                        if not _owned_file(path, identity, _sha(data)):
                            raise ValueError("accounting target changed while taking its snapshot")
                        saved[path] = (data, identity)
                    else:
                        saved[path] = None
    except (OSError, ValueError, TypeError, KeyError, DeckCompilerError) as exc:
        raise _error(root / "pngtopptx-project/work", exc) from exc
    transaction = {"before": saved, "writes": {}} if active else None
    token = _TRANSACTION.set(transaction)
    try:
        yield
    except BaseException:
        for path, ownership in transaction["writes"].items() if transaction else ():
            # No write record means no ownership. A competing link target or
            # later replacement must never be removed or restored over.
            if not _owned_file(path, *ownership):
                continue
            before = saved[path]
            if before is None:
                path.unlink()
            else:
                handle, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".rollback")
                try:
                    with os.fdopen(handle, "wb") as stream:
                        stream.write(before[0]); stream.flush(); os.fsync(stream.fileno())
                    if _owned_file(path, *ownership):
                        Path(name).replace(path)
                finally:
                    Path(name).unlink(missing_ok=True)
        raise
    finally:
        _TRANSACTION.reset(token)
