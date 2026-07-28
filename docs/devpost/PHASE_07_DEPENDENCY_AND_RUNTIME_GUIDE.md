# Phase 7 Dependency and Runtime Guide

## Supported prepared machine

- Windows 11 x64, CPython 3.11.x.
- Microsoft PowerPoint COM is mandatory; the verified instance is PowerPoint
  16.0 build 20131 x64. LibreOffice is diagnostic only and is never a silent
  canonical fallback.
- Python Playwright 1.61.0 with browser revision 1228 and Chrome for Testing
  149.0.7827.55.
- Node.js 24.13.1. The external reconstruction package root must contain
  `pptxgenjs` 4.0.1, `sharp` 0.35.1, `react` 19.2.7, `react-dom` 19.2.7, and
  `react-icons` 5.6.0.
- The installed CAPTW/pngtopptx SkillSet stays at
  `%USERPROFILE%\.codex\skills` or an explicitly configured prepared-machine
  root and must match the committed read-only pin.
- `%PROGRAMFILES%\Tesseract-OCR` supplies the existing Cairo DLL search path.
  OCR remains disabled and scanned-PDF OCR is unsupported.

## Locked Python setup

Create the venv outside the repository or fresh clone. Do not use
`--system-site-packages` and do not install into the canonical workspace.

```powershell
python -m venv <external-venv>
& <external-venv>\Scripts\Activate.ps1
$env:PYTHONNOUSERSITE = '1'
python -m pip install --require-hashes -r requirements/devpost-release.lock.txt
```

The lock is generated from `requirements/devpost-release.in` and has SHA-256
`4fde8f6fd2584f66e2c5f6c0f57f822da19809cb9d12259e35537d3d378a21dc`.
Dependency installation requires a package index or a pre-seeded cache. The
canonical demo itself requires neither network access nor an API credential.

The activated isolated venv is the only Python execution environment for both
DeckCompiler and every external Skill Python entrypoint. DeckCompiler passes
its current `sys.executable`; PATH-based Python, a global interpreter, an
external Skill-local venv, user-site packages, and system-site packages are
forbidden. The 38 locked distributions include the observed external
reconstruction closure: NumPy, Pillow, pywin32, Playwright, scikit-image,
opencv-python-headless, and their required transitives.

Run the dependency-only preflight before the public demo:

```powershell
python -B -m presentation_agent.deckcompiler.release.external_python_runtime --preflight-only
```

This validates the release lock and dependency manifest, compares the complete
distribution inventory, imports every required external module from the active
venv, and runs all six pinned external entrypoint canaries. It must finish
before handoff or reconstruction.

## Supported Git checkout

The prepared release clone must set local `core.autocrlf=false` before
checkout. This is a runtime prerequisite for the declared exact-text
`slides.js` fixture; it is not part of Phase 4/5 repository identity. Do not
change `.gitattributes`, `core.eol`, or `core.safecrlf`, and do not renormalize
the repository.

Diagnostic `core.autocrlf=true` checkouts remain useful for proving that
`git_object_bundle_fingerprint_v1` is checkout-independent. Such a checkout
may be classified
`RUNTIME_MATERIALIZATION_UNSUPPORTED_FOR_EXACT_TEXT`; that status is separate
from both bundle authorities.

## External prerequisites

Before the demo, set only documented prepared-machine locations when the
defaults do not apply:

```powershell
$env:PATH = "$env:ProgramFiles\Tesseract-OCR;" + $env:PATH
$env:DECKCOMPILER_NODE_MODULES = '<prepared-node-modules>'
$env:PYTHONNOUSERSITE = '1'
```

`OPENAI_API_KEY`, access tokens, client secrets, and browser profiles are not
required and must not be supplied to the release demo. The demo validates the
frozen Phase 4 generation provenance but never invokes live Image Generation.
Do not run `npm install`, copy external Skill source, or download a different
browser silently.

## Verification

Verify Python and the lock before use:

```powershell
python --version
Get-FileHash requirements\devpost-release.lock.txt -Algorithm SHA256
python -m pip check
python -I -c "import numpy, PIL, win32com.client, playwright.sync_api, skimage.metrics, cv2"
python -B -m presentation_agent.deckcompiler.release.external_python_runtime --preflight-only
```

The public demo command and output rules are documented in the Phase 7B and
Phase 7C runbooks. Do not perform any single-package manual install. No
undocumented manual patch to a fresh clone is permitted.
