# 🧰 Built With and DevPost Tags

> [Submission hub](README.md) · [Documentation hub](../../README.md) · [Project README](../../../README.md) · [Final evidence](../evidence/phase7_final/)

---

## Core stack

| Area | Technology |
|---|---|
| Runtime | CPython 3.11.9 AMD64 |
| Presentation | `python-pptx` 1.0.2 · Microsoft PowerPoint COM |
| Documents | PyMuPDF 1.28.0 · Pillow 11.3.0 |
| Visual analysis | NumPy 2.2.6 · OpenCV headless 4.12.0.88 · scikit-image 0.26.0 · SciPy 1.17.0 |
| Contracts | JSON Schema Draft 2020-12 |
| Browser evidence | Playwright 1.61.0 · Chromium revision 1228 · Chrome for Testing 149.0.7827.55 |
| External reconstruction | Node.js / npm + pinned `CAPTW/pngtopptx` four-SkillSet |
| Agent workflow | OpenAI Codex + platform-managed Image Generation |

> The release CLI uses the frozen verified visual bundle. It does not call live Image Generation and needs no API key.

---

## Certified fresh-clone environment

| Component | Certified value | Later recheck |
|---|---:|---:|
| CPython | 3.11.9 AMD64 | — |
| Node.js | 24.13.1 | 24.14.0 |
| npm | 11.11.0 | — |
| PowerPoint | 16.0 build 20131 x64 | build 20228 |
| Playwright | 1.61.0 | — |
| Chromium | revision 1228 | — |
| Chrome for Testing | 149.0.7827.55 | — |

The later values are not the certified canonical-run environment.

---

## DevPost tags — 20 / 25

`python` · `powerpoint` · `html` · `document-automation` · `generative-ai` ·
`openai` · `codex` · `image-generation` · `playwright` · `chromium` ·
`json-schema` · `pymupdf` · `python-pptx` · `numpy` · `opencv` ·
`scikit-image` · `reproducibility` · `design-systems` · `developer-tools` ·
`accessibility`
