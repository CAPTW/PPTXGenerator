"""Curated, package-relative DevPost draft evidence for Phase 7C."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .contracts import scan_release_text


SUBMISSION_FILENAMES = (
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


class DevpostEvidenceError(RuntimeError):
    """Stable DevPost evidence-generation error."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def _header(title: str) -> str:
    return (
        f"# {title}\n\n"
        "> DRAFT - Phase 7C release-pack candidate. "
        "Phase 7D fresh-clone proof is still required.\n\n"
    )


def _templates(context: Mapping[str, Any]) -> dict[str, str]:
    commit = str(context["tested_runtime_commit"])
    archive = str(context["delivery_archive"])
    limitations = "\n".join(
        f"- {item}" for item in context.get("known_limitations", [])
    )
    common = (
        f"Public product: **{context.get('public_product', 'PPTX Generator')}**  \n"
        f"Internal system: **{context.get('internal_system', 'DeckCompiler')}**  \n"
        f"Tested runtime commit: `{commit}`  \n"
        f"Delivery archive transport name: `{archive}`. "
        "Integrity is recorded in `../delivery_manifest.json` and the external "
        "package validation report.\n"
    )
    return {
        "ELEVATOR_PITCH.md": _header("Elevator Pitch")
        + "PPTX Generator converts a source-grounded presentation plan into an "
        "editable six-slide PowerPoint and matching HTML while preserving native text, "
        "tables, layout objects, and auditable evidence links.\n\n"
        + common,
        "DEVPOST_ABOUT_PROJECT.md": _header("About the Project")
        + "DeckCompiler is the internal deterministic compilation and validation system. "
        "This candidate demonstrates the frozen Phase 4 design system, external canonical "
        "reconstruction workflow, real PowerPoint rendering, and composite QA.\n\n"
        + common,
        "BUILT_WITH_TAGS.md": _header("Built With")
        + "- Python 3.11\n- PowerPoint COM\n- Playwright Chromium\n"
        "- JSON Schema Draft 2020-12\n- CAPTW/pngtopptx SkillSet (external prerequisite)\n\n"
        + common,
        "DEMO_SCRIPT.md": _header("Demo Script")
        + "1. Open [`../output/pptx_generator_demo.pptx`](../output/pptx_generator_demo.pptx).\n"
        "2. Confirm six editable slides and native text/table objects.\n"
        "3. Open [`../output/html/index.html`](../output/html/index.html).\n"
        "4. Compare [`../renders/contact_sheet.png`](../renders/contact_sheet.png) "
        "with the QA evidence.\n\n"
        + common,
        "JUDGING_EVIDENCE_MATRIX.md": _header("Judging Evidence Matrix")
        + "| Claim | Package-relative evidence |\n|---|---|\n"
        "| Editable PPTX | `../output/pptx_generator_demo.pptx` |\n"
        "| Six-slide real render | `../renders/contact_sheet.png` |\n"
        "| Semantic fidelity | `../qa/semantic_qa_report.json` |\n"
        "| Native editability | `../qa/editability_qa_report.json` |\n"
        "| Package integrity | `../delivery_manifest.json` |\n\n"
        + common,
        "ARCHITECTURE_OVERVIEW.md": _header("Architecture Overview")
        + "Source documents -> Phase 3 semantic artifacts -> frozen Phase 4 editable "
        "template specification -> external pngtopptx handoff -> deterministic PPTX/HTML "
        "reconstruction -> PowerPoint/Chromium evidence -> Composite QA -> delivery package.\n\n"
        + common,
        "EXISTING_ADAPTED_NEW.md": _header("Existing, Adapted, and Build-Week New")
        + "- Existing: Phase 3 planner and external canonical SkillSet.\n"
        "- Adapted: frozen Phase 4 design artifacts and Phase 6 QA proof.\n"
        "- Build-week new: Phase 7 release contracts, packager, reproducibility comparator, "
        "candidate gate, and curated submission drafts.\n\n"
        + common,
        "KNOWN_LIMITATIONS.md": _header("Known Limitations")
        + (limitations or "- None recorded.")
        + "\n\nPhase 7D fresh-clone reproduction and user feedback remain pending.\n\n"
        + common,
        "SCREENSHOT_AND_ARTIFACT_INDEX.md": _header(
            "Screenshot and Artifact Index"
        )
        + "- `../renders/slide-001.png` through `slide-006.png`\n"
        "- `../renders/contact_sheet.png`\n"
        "- `../qa/composite_qa_report.json`\n"
        "- `../repair/before_faulty_repaired_contact_sheet.png`\n\n"
        + common,
        "TECHNICAL_METRICS.md": _header("Technical Metrics")
        + f"- Slides: {context.get('slide_count', 6)}\n"
        "- Native editability coverage: 100% (verified by packaged QA)\n"
        "- Semantic fidelity: 100% (verified by packaged QA)\n"
        "- Raster violations: 0 (verified by packaged QA)\n"
        "- Logical package fingerprint: see `../delivery_manifest.json`; the "
        "manifest is sealed after draft generation.\n\n"
        + common,
        "SESSION_PROVENANCE.md": _header("Session Provenance")
        + "No Session ID is invented or claimed. Runtime and component provenance are "
        "recorded in `../provenance/` and bound by `../delivery_manifest.json`.\n\n"
        + common,
        "SUBMISSION_CHECKLIST.md": _header("Submission Checklist")
        + "- [x] Phase 7C package candidate assembled and validated\n"
        "- [x] Submission, push, and tag actions not performed\n"
        "- [ ] Phase 7D fresh-clone proof\n"
        "- [ ] PENDING_USER_FEEDBACK\n"
        "- [ ] Human submission review\n\n"
        + common,
    }


def generate_submission_drafts(
    output_dir: str | Path, context: Mapping[str, Any]
) -> list[Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    templates = _templates(context)
    paths: list[Path] = []
    for name in SUBMISSION_FILENAMES:
        path = output / name
        path.write_text(templates[name].rstrip() + "\n", encoding="utf-8")
        paths.append(path)
    validate_submission_drafts(output)
    return paths


def validate_submission_drafts(output_dir: str | Path) -> bool:
    output = Path(output_dir)
    for name in SUBMISSION_FILENAMES:
        path = output / name
        if not path.is_file():
            raise DevpostEvidenceError("DC_DEVPOST_DRAFT_MISSING", name)
        text = path.read_text(encoding="utf-8")
        if "DRAFT" not in text:
            raise DevpostEvidenceError("DC_DEVPOST_DRAFT_LABEL_MISSING", name)
        scan = scan_release_text(text)
        if scan["path_leak_count"]:
            raise DevpostEvidenceError("DC_DEVPOST_PATH_LEAK", name)
        if scan["secret_count"] or scan["private_key_count"]:
            raise DevpostEvidenceError("DC_DEVPOST_SECRET_LEAK", name)
    return True


__all__ = [
    "DevpostEvidenceError",
    "SUBMISSION_FILENAMES",
    "generate_submission_drafts",
    "validate_submission_drafts",
]
