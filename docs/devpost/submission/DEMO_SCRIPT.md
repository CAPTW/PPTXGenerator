# 🎬 Demo Script

> [Submission hub](README.md) · [Documentation hub](../../README.md) · [Project README](../../../README.md) · [Final evidence](../evidence/phase7_final/)

> **Goal:** demonstrate a real source-to-editable-deck run—not a staged transcript.

---

## 0. Setup

Use the certified Windows x64 prepared-machine profile:

- CPython 3.11.9
- PowerPoint COM
- Playwright Chromium
- Node.js + Cairo
- network access for the first verified external Skill installation

```powershell
python -m venv <venv-outside-clone>
<venv-outside-clone>\Scripts\python.exe -m pip install `
  --require-hashes `
  -r requirements/devpost-release.lock.txt
```

No user-site packages, system-site packages, manual NumPy installation, API key, or clone-local venv is part of the proof.

---

## 1. Run

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_demo.ps1 `
  -Python <venv-outside-clone>\Scripts\python.exe `
  -OutputDir <new-empty-output-directory-outside-repo>
```

The wrapper verifies or installs the pinned `CAPTW/pngtopptx` four-SkillSet
before starting the offline canonical demo.

---

## 2. Walkthrough — 12 scenes

| Scene | Show | Explain |
|---:|---|---|
| 1 | `demo.yaml`, prompt, two PDFs | exact canonical input |
| 2 | dependency preflight | 38 locked distributions, six external canaries |
| 3 | Source Corpus + Evidence Registry | 3 sources, 29 Evidence Units |
| 4 | Presentation Architecture | 3 modules, 3 batches, 6 slides |
| 5 | frozen visual bundle | original Image Generation happened earlier; release CLI does not rerun it |
| 6 | editable PPTX | edit native text and one native table cell without saving over evidence |
| 7 | companion HTML | matching six-slide presentation |
| 8 | contact sheet + renders | PowerPoint render 6/6 |
| 9 | Composite QA | semantic, source, editability, raster, visual, parity gates |
| 10 | repair proof | controlled off-canvas failure and one-wave upstream repair |
| 11 | fresh-clone evidence | historical Phase 7: 274 focused + 733 full; current public snapshot: 490 tests |
| 12 | known limits | bounded P0, no OCR, no arbitrary cross-platform or perfect conversion claim |

---

## 3. Expected result

```text
exit code: 0
stages: 36 / 36 PASS
PowerPoint renders: 6 / 6
Chromium captures: 6 / 6
Composite QA: PASS
ZIP CRC: PASS
Final gate: ELIGIBLE_FOR_DEVPOST_SUBMISSION
```

## 4. Publication closing line

> The repository is public on GitHub. A tag, GitHub Release, and DevPost submission have not yet been performed.
