from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .content_types import REQUIRED_PART_CONTENT_TYPES
from .relationships import (
    parse_relationships_xml,
    resolve_relationship_target,
    source_part_for_rels,
)


A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

NS = {"a": A_NS, "ct": CT_NS, "p": P_NS, "rel": REL_NS}

REQUIRED_PARTS = [
    "[Content_Types].xml",
    "_rels/.rels",
    "docProps/core.xml",
    "docProps/app.xml",
    "ppt/presentation.xml",
    "ppt/_rels/presentation.xml.rels",
    "ppt/slides/slide1.xml",
    "ppt/slides/_rels/slide1.xml.rels",
    "ppt/slideMasters/slideMaster1.xml",
    "ppt/slideMasters/_rels/slideMaster1.xml.rels",
    "ppt/slideLayouts/slideLayout1.xml",
    "ppt/slideLayouts/_rels/slideLayout1.xml.rels",
    "ppt/theme/theme1.xml",
    "ppt/presProps.xml",
    "ppt/viewProps.xml",
    "ppt/tableStyles.xml",
]

REQUIRED_REL_TYPES = {
    "_rels/.rels": {"officeDocument", "core-properties", "extended-properties"},
    "ppt/_rels/presentation.xml.rels": {"slideMaster", "slide", "theme", "presProps", "viewProps", "tableStyles"},
    "ppt/slides/_rels/slide1.xml.rels": {"slideLayout"},
    "ppt/slideLayouts/_rels/slideLayout1.xml.rels": {"slideMaster"},
    "ppt/slideMasters/_rels/slideMaster1.xml.rels": {"slideLayout", "theme"},
}


def sha256_file(path: str | Path) -> str | None:
    file_path = Path(path)
    if not file_path.is_file():
        return None
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_powerpoint_openability_static(pptx_path: str | Path) -> dict[str, Any]:
    path = Path(pptx_path)
    gaps: list[dict[str, str]] = []
    warnings: list[str] = []
    missing_content_type_parts: list[str] = []
    broken_targets: list[dict[str, str]] = []
    xml_parse_errors: list[dict[str, str]] = []
    names: set[str] = set()

    if not path.is_file():
        return _result(path, False, "OPENABILITY_BLOCKED_MISSING_REQUIRED_PART", [{"severity": "FATAL_POWERPOINT_OPENABILITY", "part": str(path), "message": "PPTX file is missing."}], [], [], [], [], False)

    try:
        with zipfile.ZipFile(path) as package:
            names = set(package.namelist())
            _check_required_parts(names, gaps)
            parsed = _parse_xml_parts(package, names, xml_parse_errors)
            _check_content_types(parsed.get("[Content_Types].xml"), names, gaps, missing_content_type_parts)
            _check_relationships(package, names, gaps, broken_targets)
            _check_xml_minimums(parsed, gaps, warnings)
            media_parts = [name for name in names if name.startswith("ppt/media/")]
            if media_parts:
                gaps.append(
                    {
                        "severity": "HIGH_RISK_POWERPOINT_OPENABILITY",
                        "part": "ppt/media",
                        "message": "Controlled minimal compatibility PPTX should not contain media parts.",
                    }
                )
    except zipfile.BadZipFile:
        gaps.append({"severity": "FATAL_POWERPOINT_OPENABILITY", "part": str(path), "message": "PPTX is not a readable ZIP package."})
    except OSError as exc:
        gaps.append({"severity": "FATAL_POWERPOINT_OPENABILITY", "part": str(path), "message": str(exc)})

    fatal_count = sum(1 for gap in gaps if gap.get("severity") == "FATAL_POWERPOINT_OPENABILITY")
    high_count = sum(1 for gap in gaps if gap.get("severity") == "HIGH_RISK_POWERPOINT_OPENABILITY")
    static_pass = fatal_count == 0 and high_count == 0 and not xml_parse_errors
    if static_pass and warnings:
        decision = "OPENABILITY_COMPATIBLE_WITH_WARNINGS"
    elif static_pass:
        decision = "OPENABILITY_COMPATIBLE"
    else:
        decision = _blocked_decision(gaps)
    return _result(path, static_pass, decision, gaps, warnings, missing_content_type_parts, broken_targets, xml_parse_errors, True)


def run_powerpoint_open_only_check(pptx_path: str | Path, *, force_unavailable: bool = False) -> dict[str, Any]:
    static = validate_powerpoint_openability_static(pptx_path)
    if not static["static_openability_pass"]:
        return {
            "schema": "powerpoint_open_only_check.v1",
            "pptx_path": str(pptx_path),
            "com_test_ran": False,
            "openability_status": static["decision"],
            "static_openability": static,
            "source_hash_before": sha256_file(pptx_path),
            "source_hash_after": sha256_file(pptx_path),
            "source_hash_unchanged": True,
            "errors": ["Static openability failed; COM open-only was not attempted."],
        }
    if force_unavailable:
        return {
            "schema": "powerpoint_open_only_check.v1",
            "pptx_path": str(pptx_path),
            "com_test_ran": False,
            "openability_status": "STATIC_OPENABILITY_PASS_COM_UNAVAILABLE",
            "static_openability": static,
            "source_hash_before": sha256_file(pptx_path),
            "source_hash_after": sha256_file(pptx_path),
            "source_hash_unchanged": True,
            "errors": [],
        }
    before = sha256_file(pptx_path)
    try:
        from ...render.powerpoint_com_diagnostics import run_powerpoint_com_diagnostics
    except Exception as exc:
        return {
            "schema": "powerpoint_open_only_check.v1",
            "pptx_path": str(pptx_path),
            "com_test_ran": False,
            "openability_status": "STATIC_OPENABILITY_PASS_COM_UNAVAILABLE",
            "static_openability": static,
            "source_hash_before": before,
            "source_hash_after": sha256_file(pptx_path),
            "source_hash_unchanged": before == sha256_file(pptx_path),
            "errors": [f"PowerPoint COM diagnostics import unavailable: {exc}"],
        }
    diagnostics = run_powerpoint_com_diagnostics(pptx_path)
    after = sha256_file(pptx_path)
    open_success = diagnostics.get("open_success") is True and diagnostics.get("slide_count") == 1
    return {
        "schema": "powerpoint_open_only_check.v1",
        "pptx_path": str(pptx_path),
        "com_test_ran": bool(diagnostics.get("win32com_available")),
        "openability_status": "POWERPOINT_OPENABLE" if open_success else "POWERPOINT_OPEN_FAIL",
        "static_openability": static,
        "powerpoint_com_diagnostics": diagnostics,
        "source_hash_before": before,
        "source_hash_after": after,
        "source_hash_unchanged": before == after,
        "errors": [] if open_success else diagnostics.get("exceptions", []),
    }


def verify_c02b_claim(claim: str, *, patched_pptx_exists: bool = False, powerpoint_openable: bool = False) -> dict[str, Any]:
    lowered = claim.lower()
    if "product pass" in lowered:
        status = "OVERCLAIMED"
    elif "unlock" in lowered and any(stage in lowered for stage in ["e03", "e04", "d08"]):
        status = "BLOCKED_BY_SCALEOUT_LOCK"
    elif "promoted" in lowered or "golden" in lowered:
        status = "BLOCKED_BY_POLICY"
    elif "source-bound" in lowered:
        status = "CONTRADICTED"
    elif "openability" in lowered or "openable" in lowered:
        status = "VERIFIED" if powerpoint_openable else "INSUFFICIENT_EVIDENCE"
    elif "patched pptx" in lowered or "patched controlled" in lowered:
        status = "VERIFIED" if patched_pptx_exists else "INSUFFICIENT_EVIDENCE"
    else:
        status = "INSUFFICIENT_EVIDENCE"
    return {"schema": "c02b_claim_verification.v1", "claim": claim, "status": status, "product_pass": False}


def c02b_scaleout_lock_status() -> dict[str, dict[str, Any]]:
    return {
        "E03": {"allowed": False, "reason": "C02B does not unlock E03."},
        "E04": {"allowed": False, "reason": "E03 has not passed."},
        "D08": {"allowed": False, "reason": "E04 has not passed."},
        "C11": {"allowed": False, "reason": "Scaleout remains locked."},
        "bulk": {"allowed": False, "reason": "Bulk generation remains locked."},
        "canonical_promotion": {"allowed": False, "reason": "Canonical promotion is blocked by policy."},
    }


def _result(
    path: Path,
    static_pass: bool,
    decision: str,
    gaps: list[dict[str, str]],
    warnings: list[str],
    missing_content_type_parts: list[str],
    broken_targets: list[dict[str, str]],
    xml_parse_errors: list[dict[str, str]],
    zip_readable: bool,
) -> dict[str, Any]:
    return {
        "schema": "powerpoint_openability_static.v1",
        "pptx_path": str(path),
        "exists": path.is_file(),
        "sha256": sha256_file(path),
        "zip_readable": zip_readable,
        "static_openability_pass": static_pass,
        "decision": decision,
        "gaps": gaps,
        "gap_count": len(gaps),
        "fatal_gap_count": sum(1 for gap in gaps if gap.get("severity") == "FATAL_POWERPOINT_OPENABILITY"),
        "high_risk_gap_count": sum(1 for gap in gaps if gap.get("severity") == "HIGH_RISK_POWERPOINT_OPENABILITY"),
        "warnings": warnings,
        "missing_content_type_parts": missing_content_type_parts,
        "broken_relationship_targets": broken_targets,
        "broken_relationship_count": len(broken_targets),
        "xml_parse_errors": xml_parse_errors,
        "xml_parse_error_count": len(xml_parse_errors),
        "product_pass": False,
        "render_generated": False,
    }


def _check_required_parts(names: set[str], gaps: list[dict[str, str]]) -> None:
    for part in REQUIRED_PARTS:
        if part not in names:
            gaps.append({"severity": "FATAL_POWERPOINT_OPENABILITY", "part": part, "message": "Required package part is missing."})


def _parse_xml_parts(package: zipfile.ZipFile, names: set[str], errors: list[dict[str, str]]) -> dict[str, ET.Element]:
    parsed: dict[str, ET.Element] = {}
    for name in names:
        if not name.endswith(".xml"):
            continue
        try:
            parsed[name] = ET.fromstring(package.read(name))
        except ET.ParseError as exc:
            errors.append({"part": name, "message": str(exc)})
    return parsed


def _check_content_types(
    root: ET.Element | None,
    names: set[str],
    gaps: list[dict[str, str]],
    missing_content_type_parts: list[str],
) -> None:
    if root is None:
        gaps.append({"severity": "FATAL_POWERPOINT_OPENABILITY", "part": "[Content_Types].xml", "message": "Content types XML missing or unparseable."})
        return
    defaults = {node.attrib.get("Extension"): node.attrib.get("ContentType") for node in root.findall("ct:Default", NS)}
    if defaults.get("rels") != "application/vnd.openxmlformats-package.relationships+xml":
        gaps.append({"severity": "FATAL_POWERPOINT_OPENABILITY", "part": "[Content_Types].xml", "message": "Missing rels default content type."})
    if defaults.get("xml") != "application/xml":
        gaps.append({"severity": "FATAL_POWERPOINT_OPENABILITY", "part": "[Content_Types].xml", "message": "Missing XML default content type."})
    overrides = {node.attrib.get("PartName"): node.attrib.get("ContentType") for node in root.findall("ct:Override", NS)}
    for part, content_type in REQUIRED_PART_CONTENT_TYPES.items():
        bare_part = part.lstrip("/")
        if bare_part not in names:
            continue
        if overrides.get(part) != content_type:
            missing_content_type_parts.append(bare_part)
            gaps.append({"severity": "FATAL_POWERPOINT_OPENABILITY", "part": bare_part, "message": "Required content type override is missing."})


def _check_relationships(
    package: zipfile.ZipFile,
    names: set[str],
    gaps: list[dict[str, str]],
    broken_targets: list[dict[str, str]],
) -> None:
    for rels_part, required_types in REQUIRED_REL_TYPES.items():
        if rels_part not in names:
            continue
        rels = parse_relationships_xml(package.read(rels_part))
        suffixes = {rel.rel_type.rsplit("/", 1)[-1] for rel in rels}
        for required in required_types:
            if required not in suffixes:
                gaps.append({"severity": "FATAL_POWERPOINT_OPENABILITY", "part": rels_part, "message": f"Required relationship type is missing: {required}."})
        source_part = source_part_for_rels(rels_part)
        for rel in rels:
            target = resolve_relationship_target(source_part, rel.target)
            if rel.target.startswith("http://") or rel.target.startswith("https://"):
                continue
            if target not in names:
                broken_targets.append({"part": rels_part, "relationship_id": rel.rel_id, "target": rel.target, "resolved_target": target})
                gaps.append({"severity": "FATAL_POWERPOINT_OPENABILITY", "part": rels_part, "message": f"Broken relationship target: {rel.target}."})


def _check_xml_minimums(parsed: dict[str, ET.Element], gaps: list[dict[str, str]], warnings: list[str]) -> None:
    presentation = parsed.get("ppt/presentation.xml")
    if presentation is not None:
        for path, message in [
            ("p:sldMasterIdLst", "Presentation is missing slide master list."),
            ("p:sldIdLst", "Presentation is missing slide list."),
            ("p:sldSz", "Presentation is missing slide size."),
            ("p:notesSz", "Presentation is missing notes size."),
            ("p:defaultTextStyle", "Presentation is missing default text style."),
        ]:
            if presentation.find(path, NS) is None:
                gaps.append({"severity": "HIGH_RISK_POWERPOINT_OPENABILITY", "part": "ppt/presentation.xml", "message": message})

    slide = parsed.get("ppt/slides/slide1.xml")
    if slide is not None:
        if slide.find("p:cSld/p:spTree", NS) is None:
            gaps.append({"severity": "FATAL_POWERPOINT_OPENABILITY", "part": "ppt/slides/slide1.xml", "message": "Slide is missing cSld/spTree."})
        if slide.find(".//a:t", NS) is None:
            gaps.append({"severity": "HIGH_RISK_POWERPOINT_OPENABILITY", "part": "ppt/slides/slide1.xml", "message": "Slide has no editable text run."})
        if slide.find("p:clrMapOvr", NS) is None:
            gaps.append({"severity": "WARNING", "part": "ppt/slides/slide1.xml", "message": "Slide is missing clrMapOvr."})

    master = parsed.get("ppt/slideMasters/slideMaster1.xml")
    if master is not None:
        for path, message in [
            ("p:cSld/p:spTree", "Slide master is missing cSld/spTree."),
            ("p:clrMap", "Slide master is missing clrMap."),
            ("p:sldLayoutIdLst", "Slide master is missing layout list."),
            ("p:txStyles", "Slide master is missing text style defaults."),
        ]:
            if master.find(path, NS) is None:
                gaps.append({"severity": "HIGH_RISK_POWERPOINT_OPENABILITY", "part": "ppt/slideMasters/slideMaster1.xml", "message": message})

    layout = parsed.get("ppt/slideLayouts/slideLayout1.xml")
    if layout is not None:
        if layout.find("p:cSld/p:spTree", NS) is None:
            gaps.append({"severity": "HIGH_RISK_POWERPOINT_OPENABILITY", "part": "ppt/slideLayouts/slideLayout1.xml", "message": "Slide layout is missing cSld/spTree."})
        if layout.find("p:clrMapOvr", NS) is None:
            gaps.append({"severity": "WARNING", "part": "ppt/slideLayouts/slideLayout1.xml", "message": "Slide layout is missing clrMapOvr."})
        if layout.attrib.get("type") != "blank":
            warnings.append("Slide layout type is not blank.")

    theme = parsed.get("ppt/theme/theme1.xml")
    if theme is not None:
        for path, message in [
            (".//a:clrScheme", "Theme is missing clrScheme."),
            (".//a:fontScheme", "Theme is missing fontScheme."),
            (".//a:fmtScheme", "Theme is missing fmtScheme."),
        ]:
            if theme.find(path, NS) is None:
                gaps.append({"severity": "FATAL_POWERPOINT_OPENABILITY", "part": "ppt/theme/theme1.xml", "message": message})
        fmt = theme.find(".//a:fmtScheme", NS)
        if fmt is not None:
            minimum_counts = {"fillStyleLst": 3, "lnStyleLst": 3, "effectStyleLst": 3, "bgFillStyleLst": 3}
            for tag, minimum_count in minimum_counts.items():
                node = fmt.find(f"a:{tag}", NS)
                if node is None or len(list(node)) == 0:
                    gaps.append({"severity": "FATAL_POWERPOINT_OPENABILITY", "part": "ppt/theme/theme1.xml", "message": f"Theme fmtScheme {tag} is empty."})
                elif len(list(node)) < minimum_count:
                    gaps.append({"severity": "FATAL_POWERPOINT_OPENABILITY", "part": "ppt/theme/theme1.xml", "message": f"Theme fmtScheme {tag} has fewer than {minimum_count} entries."})


def _blocked_decision(gaps: list[dict[str, str]]) -> str:
    messages = " ".join(gap.get("message", "") for gap in gaps).lower()
    if "relationship" in messages:
        return "OPENABILITY_BLOCKED_MISSING_RELATIONSHIP"
    if "required package part" in messages:
        return "OPENABILITY_BLOCKED_MISSING_REQUIRED_PART"
    if "theme" in messages:
        return "OPENABILITY_BLOCKED_INVALID_THEME"
    if "master" in messages or "layout" in messages:
        return "OPENABILITY_BLOCKED_INVALID_MASTER_LAYOUT"
    return "OPENABILITY_BLOCKED_INVALID_PRESENTATION"
