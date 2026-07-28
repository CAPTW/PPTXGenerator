# Phase 7 DeckCompiler Demo Runbook

## Scope

This runbook executes the canonical prepared-machine DeckCompiler demo. It
regenerates Phase 3 from one repository prompt and two searchable PDFs,
validates the frozen Phase 4 visual bundle and committed Phase 6 repair proof,
performs a fresh official PNGtoPPTX reconstruction, and produces fresh editable
PPTX, HTML, render, screenshot, QA, and delivery artifacts.

The release profile is `devpost_p0_frozen_visuals`. It does not perform live
Image Generation, OCR, provider transport, credential lookup, or remote source
fetching. No API key is required or permitted.

## Prepared-machine prerequisites

- Windows x64 with CPython 3.11.9.
- Microsoft PowerPoint 16.0 COM automation available. LibreOffice is not a
  silent release fallback.
- Dependencies installed from `requirements/devpost-release.lock.txt` using
  `--require-hashes`; lock SHA-256 is
  `4fde8f6fd2584f66e2c5f6c0f57f822da19809cb9d12259e35537d3d378a21dc`.
- Playwright 1.61.0 and browser revision 1228, Chrome for Testing
  149.0.7827.55.
- Git access to the public `CAPTW/pngtopptx` repository during the setup step.
  The installer provisions four Skills under the prepared user's Codex Skill
  root. Their combined aggregate must be
  `027336f1a61641bfb6e891199fe24ab77aee0c31287c7e8d88613a458310e529`.
- Node 24.13.1 and a prepared external Node dependency directory containing
  `pptxgenjs` 4.0.1, `sharp` 0.35.1, React/React DOM 19.2.7, and React Icons
  5.6.0.
- Tesseract/Cairo DLL discovery may use the prepared Tesseract directory. OCR
  remains disabled and scanned PDFs are unsupported by this release profile.
- The clone-local `core.autocrlf` value is `false`. Phase 4 and Phase 5
  identities come from their Git-object authority manifests; runtime
  compatibility and the exact `slides.js` hash are checked separately.

From a repository-root PowerShell, activate the isolated locked Python
environment and set the documented process-local paths:

```powershell
$env:PYTHONPATH = (Resolve-Path 'src').Path
$env:PYTHONNOUSERSITE = '1'
$env:DECKCOMPILER_NODE_MODULES = '<prepared-external-node-modules-directory>'
$env:PLAYWRIGHT_BROWSERS_PATH = '<prepared-playwright-browser-root>'
$env:PATH = 'C:\Program Files\Tesseract-OCR;' + $env:PATH
```

`PYTHONPATH` points only at this clone's source tree. The Node, browser, and
Cairo paths are prepared-machine prerequisites; none is copied into the clone
or delivery package. The setup wrapper installs a missing pinned external
SkillSet and the generation stages thereafter validate it in place without
modification.

## Exact command

Choose a new or empty ordinary directory outside the repository, external
Skill tree, `.codex`, and credential directories. The runner never clears or
deletes an existing directory.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_demo.ps1 `
  -Python <locked-venv>\Scripts\python.exe `
  -OutputDir <new-empty-directory-outside-repo>
```

The wrapper performs the networked, pinned Skill installation before invoking
the canonical offline demo. Existing mismatched Skill directories are not
overwritten unless `-BackupAndReplaceSkills` is explicitly supplied.

No optional flag, API credential, remote URL, hidden temp path, generated
`outputs/` artifact, canonical Phase 5 PPTX/HTML, or Phase 6 repaired output is
required as input.

## Serial stage and output contract

`demo_run_manifest.json` records all 36 ordered stages with status,
started/completed timestamps, input/output hashes, source commit, route,
external pin, renderer, browser, errors, remediation, and verdict. The strict
route is always `editable_pngtopptx`; `auto`, legacy, screenshot, raster, copied
Phase 5, and silent compiler fallbacks are forbidden.

Runtime files remain below the supplied root:

```text
<output-root>/
  run/
    phase3/
    qa/
    reconstruction/
  delivery/
  demo_run_manifest.json
  final_run_report.json
  package_validation_report.json
  pptx_generator_devpost_delivery.zip
```

The reconstruction subtree contains a fresh handoff, crop contract, official
project, PPTX, HTML, six PowerPoint renders, six Chromium screenshots, official
final gate, and fresh Composite QA. The default demo validates the committed
Phase 6 controlled-repair proof; it does not rerun the fault.

Before any handoff or reconstruction stage, the command validates the
38-distribution hash lock, the versioned external Python dependency manifest,
the exact installed inventory and versions, required module origins, six
external entrypoint canaries, and the read-only external Skill pin. It then
validates
`bundle_fingerprint_policy.json`, both bundle authority manifests, both
supported-checkout compatibility reports, and the immutable legacy correction
bridge. Legacy Phase 4/5 raw working-tree aggregates are not current release
authority.

## Success output

Before physical fresh-clone proof, a passing canonical run prints:

```text
DECKCOMPILER_DEMO_GO
VERDICT=ELIGIBLE_FOR_FRESH_CLONE_PROOF
DELIVERY_PACKAGE=<path>
DELIVERY_ARCHIVE=<path>
PPTX=<path>
HTML=<path>
CONTACT_SHEET=<path>
DELIVERY_MANIFEST=<path>
RELEASE_CANDIDATE_GATE=<path>
```

These markers do not perform DevPost submission, push, or tag creation. Final
submission eligibility is decided only by the later physical-clone and final
release gates.

## Platform limitation

The canonical release path is Windows x64 and requires desktop PowerPoint COM.
It is not certified as a cross-platform or headless Office workflow. Browser
and PowerPoint automation need a prepared machine capable of launching those
installed applications.
