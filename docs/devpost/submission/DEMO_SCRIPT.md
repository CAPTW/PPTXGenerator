# Demo Script

## Setup

Use the prepared Windows x64 environment with CPython 3.11.9, Microsoft
PowerPoint, Playwright Chromium, Node.js, Cairo, and the pinned external
four-SkillSet. The canonical configuration selects one repository-authored
prompt and exactly two text-searchable PDFs.

Create an isolated virtual environment and a new empty output directory outside
the clone:

```powershell
python -m venv <venv-outside-clone>
<venv-outside-clone>\Scripts\python.exe -m pip install --require-hashes -r requirements/devpost-release.lock.txt
```

No user-site package, system-site package, global Python import, manual NumPy
install, API key, or clone-local virtual environment is part of the proof.

## Run

```powershell
<venv-outside-clone>\Scripts\python.exe -B -m presentation_agent.deckcompiler demo `
  --config examples/deckcompiler_demo/demo.yaml `
  --output-dir <new-empty-output-directory-outside-repo>
```

Do not stage a terminal transcript or simulate success. Show the command and
the fresh output produced in the current recording.

## Walkthrough

1. Show `demo.yaml`, the one prompt, and the two searchable PDF inputs.
2. Run the canonical one-command demo and show the dependency preflight:
   38 locked distributions, no fallback site, and six external entrypoint
   canaries.
3. Open `delivery/source/source_corpus.json` and
   `delivery/source/evidence_unit_registry.json`; point out three sources and
   29 Evidence Units.
4. Open `delivery/architecture/presentation_architecture.json`; explain the
   three-module, three-batch, six-slide Module–Batch–Slide plan.
5. Explain that the original platform-managed Phase 4 workflow executed Image
   Generation, while this release command only validates and consumes the
   frozen verified visual bundle. It performs no live Image Generation and
   needs no API key.
6. Open `delivery/output/pptx_generator_demo.pptx` in PowerPoint. Confirm six
   slides, then edit one native text object and one cell in the native table.
   Do not save over the verified artifact.
7. Open `delivery/output/html/index.html` and show the matching six-slide HTML
   presentation.
8. Review `delivery/renders/contact_sheet.png` and the six individual
   PowerPoint renders.
9. Review `delivery/qa/composite_qa_report.json` and summarize the semantic,
   source, editability, raster, visual, and parity gates.
10. Show `delivery/repair/before_faulty_repaired_contact_sheet.png`. Explain
    that the controlled off-canvas fault was rejected and the upstream owner
    converged in one repair wave; the default demo does not reinject the fault.
11. Show the physical fresh-clone evidence and the canonical delivery ZIP.
    State that 274 focused and 733 full-suite tests passed and that canonical
    and fresh runs had zero unexplained divergence.
12. Close with the known limits: one source-controlled six-slide P0, exactly
    two searchable PDFs, no scanned-PDF OCR, no live Image Generation rerun,
    prepared-machine prerequisites, and no arbitrary cross-platform or
    PNG-to-perfect-PPTX claim.
13. State the publication boundary: the technical release is eligible, but no
    GitHub push, tag, release, or DevPost submission has been performed.

## Expected result

- exit code 0
- 36/36 stages PASS
- six PowerPoint renders and six Chromium captures
- Composite QA PASS
- package validation and ZIP CRC PASS
- final repository gate `ELIGIBLE_FOR_DEVPOST_SUBMISSION`

The repository-level
[`final_release_gate.json`](../evidence/phase7_final/final_release_gate.json)
combines the demo, physical fresh-clone, dependency, package, and publication
control evidence. These expected values are review checkpoints, not substitutes
for showing the actual run.
