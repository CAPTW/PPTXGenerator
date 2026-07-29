# ⚠️ Known Limitations

> [Submission hub](README.md) · [Documentation hub](../../README.md) · [Project README](../../../README.md) · [Final evidence](../evidence/phase7_final/)

> These limits are part of the certified release boundary, not hidden caveats.

---

## Input and scale

- The canonical P0 proves one source-controlled six-slide workflow.
- Input is one prompt plus exactly two distinct text-searchable PDFs.
- Arbitrary-volume document ingestion has not been proven.
- Scanned or image-only PDF OCR is unsupported; negative fixtures must fail before planning.

## Generation and editing

- The release CLI validates and consumes a frozen visual bundle; it does not rerun live Image Generation.
- No API key is required.
- No arbitrary PNG-to-perfect-PPTX conversion claim is made.
- The default demo validates immutable Phase 6 repair proof instead of reinjecting the controlled fault.

## Platform

- Windows x64 is the certified profile.
- PowerPoint, Chromium, Node.js/Cairo/Tesseract prerequisites, and the locked Python runtime must be prepared on the machine.
- The setup wrapper can install the pinned external `CAPTW/pngtopptx` Skills; the first installation requires network access.
- No Google Slides fidelity or arbitrary cross-platform PowerPoint fidelity claim is made.
- Exact model identity is not claimed when a platform tool does not expose it.

## QA interpretation

- Pixel comparison is diagnostic, not the sole authority.
- Release acceptance also requires semantic, structural, editability, source, parity, geometry, and human-readable visual evidence.

## Publication state

| Action | State |
|---|---|
| GitHub repository publication | ✅ Complete |
| `main` push | ✅ Complete |
| Git tag | ⏳ Not created |
| GitHub Release / asset | ⏳ Not created |
| DevPost submission | ⏳ Not yet submitted |
| Codex Session ID | `PENDING_USER_FEEDBACK` |

The committed canonical ZIP preserves its time-scoped Phase 7C internal notes. The repository-level `final_release_gate.json` remains the current technical-status authority.
