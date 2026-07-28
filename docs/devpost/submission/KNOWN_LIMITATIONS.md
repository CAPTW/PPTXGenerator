# Known Limitations

- The canonical P0 is one source-controlled six-slide demo, not proof for every
  document, template, or presentation length.
- The canonical input is one prompt plus exactly two distinct text-searchable
  PDFs.
- Scanned or image-only PDF OCR is unsupported. The image-only fixture is a
  negative test that must fail before planning.
- Arbitrary-volume document ingestion has not been proven.
- The release CLI validates and consumes a frozen verified visual bundle; it
  does not rerun live Image Generation and needs no API key.
- The prepared machine must provide Microsoft PowerPoint, Playwright Chromium,
  Node.js/Cairo prerequisites, and the pinned external CAPTW/pngtopptx
  four-SkillSet.
- Windows x64 is the certified profile. Other operating systems and interpreter
  combinations are outside this release proof.
- No Google Slides fidelity claim is made.
- No arbitrary PNG-to-perfect-PPTX conversion claim is made.
- No arbitrary cross-platform PowerPoint fidelity claim is made.
- Exact runtime model identity is not claimed when the platform tool does not
  expose it.
- Pixel comparison remains a non-authoritative diagnostic. Composite acceptance
  also requires semantic, structural, editability, source, parity, geometry,
  and human-readable visual evidence.
- The Phase 6 controlled fault is not reinjected by the default demo. Its
  immutable detection and one-wave upstream-repair proof is packaged as
  evidence.
- The committed canonical ZIP is the immutable Phase 7C delivery payload used
  by the later physical fresh-clone proof. Its internal README and limitation
  note preserve their time-scoped Phase 7C status; the repository-level
  `final_release_gate.json` is the current technical-status authority.
- DevPost submission is not automatic. GitHub publication, push, tag, GitHub
  Release creation, and actual DevPost submission have not been performed or
  authorized.
- The Codex Session ID remains `PENDING_USER_FEEDBACK` until the user supplies
  the actual `/feedback` value. No identifier has been inferred or invented.
