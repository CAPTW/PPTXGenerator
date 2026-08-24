# Cold unseen slide and font-contract acceptance — 2026-08-24

## Scope

- Input was a newly generated, previously unconverted 16:9 Edge AI architecture slide.
- Source SHA-256: `8c22ed8a99fba325745989c5b749a4d61dc4d3c8c185cb0fc1334b14d208528d`.
- Canonical reconstruction dependency: `CAPTW/pngtopptx` at
  `d414d45a3c4e5881ac3262c451d4f84fd98d4c19`.
- Local evidence root:
  `D:/dev/repos/PPTXlocal/design_runs/cold_unseen_edge_ai_font_contract_20260824`.

## Acceptance result

- Final editable PPTX and standalone HTML were produced and opened/rendered by
  Microsoft PowerPoint automation.
- Native editable objects: 233.
- Native text boxes: 49.
- Full-slide raster surfaces: 0.
- Raster crops: 0.
- Visual QA: fail 0, blocking 0, needs-polish 1. The one accepted diagnostic was
  limited to the calibrated native-renderer palette/edge classes; manual
  source/PPTX/HTML inspection found no content, hierarchy, clipping, typography,
  or meaningful-detail defect.
- Source/PPTX SSIM: approximately 0.6442.
- Source/HTML SSIM: approximately 0.6465.
- PPTX/HTML SSIM: approximately 0.7597.

## Font result

- Original font: `Pretendard`.
- Resolved font: `Pretendard` from the per-user font inventory.
- Resolution: exact.
- Automatic installation attempted: false.
- The conversion emitted `font_resolution_manifest.json` and continued without
  fallback because the exact family was installed.

## Repository gates

- Relevant DeckCompiler regression tests: 62 passed.
- Fresh `deckcompiler generate` runs against both the active installation and a
  clean exact copy of the public SkillSet produced a schema 1.9.0 execution plan
  with `pptx-workflow-architect` first,
  `font_preflight.js` bound, install decision `ask`, automatic installation
  forbidden, and font arguments on preview, final, one-slide cached, and repair
  render commands.
- The clean public four-Skill tree matched combined aggregate
  `7cce8f28a8ebc92b1ade1e33df10adc054066693243755c8f6d6c711722950b4`.
- Protected PPTXlocal canonical outputs were unchanged.
