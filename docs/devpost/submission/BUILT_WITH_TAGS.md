# Built With and DevPost Tags

## Built with

- CPython 3.11.9 AMD64
- `python-pptx` 1.0.2
- PyMuPDF 1.28.0
- Pillow 11.3.0
- NumPy 2.2.6
- OpenCV headless 4.12.0.88
- scikit-image 0.26.0 and SciPy 1.17.0
- JSON Schema Draft 2020-12 contracts
- Microsoft PowerPoint COM
- Playwright 1.61.0, Chromium revision 1228, and Chrome for Testing
  149.0.7827.55
- Node.js and npm for the external reconstruction contract
- OpenAI Codex for planning, orchestration, and review
- platform-managed Image Generation for the original frozen design-reference
  bundle
- the pinned external `CAPTW/pngtopptx` four-SkillSet

The original platform-managed Phase 4 Image Generation workflow executed and
recorded provenance and selected-image hashes. Its image-model identity was not
exposed and is not claimed. The release CLI uses the frozen verified bundle,
does not call live Image Generation, and needs no API key.

The external CAPTW/pngtopptx four-SkillSet was not created during Build Week.
PPTX Generator pins and orchestrates it through a verified handoff and release
contract.

## Certified fresh-clone environment

| Component | Certified value |
|---|---|
| CPython | 3.11.9 AMD64 |
| Node.js | 24.13.1 |
| npm | 11.11.0 |
| Microsoft PowerPoint | 16.0 build 20131 x64 |
| Playwright | 1.61.0 |
| Chromium | revision 1228 |
| Chrome for Testing | 149.0.7827.55 |

## Later live prerequisite recheck

| Component | Later observed value |
|---|---|
| Node.js | 24.14.0 |
| Microsoft PowerPoint | build 20228 |

The later recheck is not the certified canonical-run environment.

## DevPost tags (20)

`python`, `powerpoint`, `html`, `document-automation`, `generative-ai`,
`openai`, `codex`, `image-generation`, `playwright`, `chromium`,
`json-schema`, `pymupdf`, `python-pptx`, `numpy`, `opencv`, `scikit-image`,
`reproducibility`, `design-systems`, `developer-tools`, `accessibility`
