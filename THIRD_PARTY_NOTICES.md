# 🧾 Third-Party Notices

> This document explains redistribution and ownership boundaries. It is not a replacement for upstream license texts.

---

## 📦 What the delivery package does **not** redistribute

- external `CAPTW/pngtopptx` Skill source;
- Node modules;
- Python virtual environments or wheels;
- browser binaries;
- font binaries;
- Microsoft Office binaries;
- Tesseract / Cairo binaries.

Those components remain prepared-machine prerequisites or package-index dependencies.

---

## 🧩 External reconstruction boundary

The setup wrapper downloads the pinned external
[`CAPTW/pngtopptx`](https://github.com/CAPTW/pngtopptx) four-SkillSet into the
user-selected external Skill root, validates its upstream commit, subtree OIDs,
and file hashes, and then invokes it through a verified handoff. The upstream
project is licensed under the MIT License; its license and notices continue to
apply. Its source is not copied into this repository or the delivery package.

| External component | Relationship |
|---|---|
| `slide-editable-deck-orchestrator` | external existing Skill |
| `slide-text-layer-inpaint` | external existing Skill |
| `slide-image-dual-render` | external existing Skill |
| `slide-visual-polish-qa` | external existing Skill |
| Microsoft PowerPoint | installed COM prerequisite; not redistributed |
| Playwright / Chrome for Testing | automation and rendering prerequisite; browser binary not included |
| Tesseract directory / Cairo DLLs | runtime DLL discovery only; OCR remains disabled |

---

## 🐍 External Python reconstruction dependency closure

DeckCompiler installs the following lock-owned distributions to run canonical external reconstruction and visual-QA entrypoints. Exact versions and artifact hashes are bound in the release lock and dependency manifest.

| Distribution | Version | License classification |
|---|---:|---|
| ImageIO | 2.37.2 | BSD-2-Clause |
| lazy_loader | 0.4 | BSD-3-Clause |
| NetworkX | 3.6.1 | BSD-3-Clause |
| NumPy | 2.2.6 | BSD-3-Clause; bundled notices also apply |
| opencv-python-headless | 4.12.0.88 | MIT wrapper; Apache-2.0 OpenCV and bundled notices also apply |
| packaging | 25.0 | Apache-2.0 OR BSD-2-Clause |
| scikit-image | 0.26.0 | BSD-3-Clause; bundled notices also apply |
| SciPy | 1.17.0 | BSD-3-Clause; bundled notices also apply |
| tifffile | 2026.1.14 | BSD-3-Clause |

> Wheels are installed into the prepared runtime but are **not** copied into the delivery ZIP.

Installing or using an external component remains subject to that component's
own terms. This notice and the repository's Apache-2.0 license do not record or
imply acceptance of separate third-party terms on behalf of any user or system.

---

## 🎨 Fixture and generated-asset provenance

- Canonical prompt and PDF fixtures are repository-authored synthetic material.
- Original Phase 4 design-reference artifacts were generated through a platform-managed Image Generation workflow.
- Provenance and selected hashes are recorded in `examples/deckcompiler_demo/phase4/generation_provenance.json`.
- The release CLI validates and consumes that frozen bundle; it does not rerun live Image Generation.

---

## 🔍 Evidence sources

- [`requirements/devpost-release.lock.txt`](requirements/devpost-release.lock.txt)
- [`external_python_runtime_dependency_manifest.json`](examples/deckcompiler_demo/phase7/contract/external_python_runtime_dependency_manifest.json)
- [`PUBLICATION_BOUNDARY.md`](PUBLICATION_BOUNDARY.md)
- [`LICENSE`](LICENSE)
