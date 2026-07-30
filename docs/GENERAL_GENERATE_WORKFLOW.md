# General Prompt and PDF Workflow

`deckcompiler generate` is the resumable entrypoint for a user prompt plus zero
to six local, text-searchable PDFs. It keeps the existing six-slide editable
DeckCompiler contract and connects Phase 3 through Phase 6 without pretending
that repository code can invoke platform-managed Image Generation or the
external `CAPTW/pngtopptx` SkillSet by itself.

## 1. Start from a prompt and PDFs

Install the project into the prepared Python environment, then choose a new
empty runtime directory outside the repository:

```powershell
python -m pip install -e .

deckcompiler generate `
  --output-dir C:\runs\quarterly-risk-deck `
  --prompt "Create an executive decision brief from the attached reports." `
  --pdf C:\sources\operations.pdf `
  --pdf C:\sources\risk-review.pdf `
  --audience "executive leadership" `
  --purpose "investment decision" `
  --language English `
  --tone professional `
  --tone concise `
  --workflow executive_summary
```

Use `--prompt-file` instead of `--prompt` for a UTF-8 text file. PDF inputs are
copied into the isolated runtime and fingerprinted. Duplicate bytes, missing
files, scanned/image-only PDFs, unsafe workflow aliases, and more than six PDFs
fail closed.

The first call executes:

1. input collection and immutable local copies;
2. Phase 3 source extraction, Evidence Units, workflow resolution, strict
   six-slide planning, and Creative Template Architecture;
3. Phase 4 Semantic Sidecars, editable template specification, visual DNA, and
   13 platform image-request artifacts.

It then exits with code `2` and status `AWAITING_PHASE4_VISUALS`. Code `2` means
the workflow is valid and waiting at a declared external boundary, not that the
completed stages failed.

## 2. Supply the accepted Phase 4 visual bundle

Execute the prepared requests under
`phase4_preparation/preparation/prompts/` using the approved platform-managed
image workflow. Assemble the accepted Phase 4 bundle with:

- six 1664×936 PNG slide visual targets;
- six matching Semantic Sidecars;
- `input_provenance.json` bound to the exact Phase 3 run and artifact hashes;
- the design system, editable template spec, visual DNA, geometry report,
  generation provenance, regeneration history, target manifest, and Phase 4
  validation and acceptance records.

Resume and export the official PNGtoPPTX handoff:

```powershell
deckcompiler generate `
  --resume C:\runs\quarterly-risk-deck `
  --phase4-bundle C:\runs\quarterly-risk-phase4 `
  --external-skillset-pin C:\pins\pngtopptx-skillset-pin.json `
  --external-skill-root C:\skills\pngtopptx `
  --profile C:\skills\pngtopptx\slide-image-dual-render\styles\corporate-light.json `
  --node-path C:\runtime\node_modules
```

DeckCompiler validates target bytes, dimensions, Sidecar linkage, full-slide
raster prohibitions, and exact Phase 3 provenance before writing
`phase5_handoff/`. It does not invoke the external SkillSet. The call exits with
code `2` and records `EXECUTE_PHASE5_RECONSTRUCTION` plus the exact invocation
plan path in the workflow manifest.

The Phase 4 bundle may be registered first without the four Phase 5 runtime
options. In that case the status becomes `AWAITING_PHASE5_CONFIGURATION`; resume
again with the four options to create the handoff.

## 3. Resume with reconstructed outputs and run Phase 6

After the pinned external SkillSet produces the editable PPTX, HTML, object
manifests, semantic reports, crop evidence, and repair history, package those
artifacts as the Phase 5 bundle. Run the official read-only visual QA, then
resume:

```powershell
deckcompiler generate `
  --resume C:\runs\quarterly-risk-deck `
  --phase5-bundle C:\runs\quarterly-risk-phase5 `
  --external-visual-summary C:\runs\visual-qa\summary.json `
  --external-visual-exit-code 0 `
  --renders-dir C:\runs\powerpoint-renders `
  --renderer-version 16.0
```

Phase 6 hashes the supplied runtime bundles instead of comparing them to the
canonical demo Git-object authorities, while retaining the same semantic,
source-coverage, editability, package, raster, render, and PPTX/HTML parity
gates. A passing run returns code `0` and status `COMPLETED`; a completed QA run
that requires repair returns code `1` and status `NEEDS_REPAIR`.

## State and validation

Every transition is written atomically to:

```text
<runtime>\generate_workflow_manifest.json
```

The manifest contains input hashes, phase statuses, artifact directory
fingerprints, external-boundary instructions, history, and machine-readable
errors. Validate it at any time:

```powershell
deckcompiler validate-generate C:\runs\quarterly-risk-deck
```

The runtime is intentionally resumable but input-immutable. To change the
prompt or PDFs, start a new workflow directory.
