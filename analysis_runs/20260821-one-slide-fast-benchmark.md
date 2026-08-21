# One-slide high-fidelity fast-path benchmark

Date: 2026-08-21
Source SHA-256: `2972d609eac202b2b6adaee9d889bde052df2222961d8c9ef4836ad428c467f0`
Canonical SkillSet: `CAPTW/pngtopptx@2b6120d39a5a51457615b77521e39cb272344672`

## Scope

This benchmark measures the official PNGtoPPTX compile, hardlocks, PowerPoint
rasterization, HTML capture, source/PPTX/HTML comparisons, high-fidelity
acceptance, evidence closure, package validation, and final gate for an already
verified editable one-slide reconstruction. It does not claim that a previously
unseen arbitrary image can be reasoned about and authored from scratch in under
two minutes.

## Result

| Run | Total | PPTX compile | PPTX raster | HTML capture | Comparison | Quality floor |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Verified authoring, cold HTML capture | 42.224 s | 10.236 s | 4.805 s | 18.969 s | 2.702 s | 4.264 s |
| Exact-input cache hit | 11.762 s | 0.754 s | 3.366 s | 0.111 s | 2.398 s | 4.222 s |

Both runs are below the 120-second target. The cached run used the
`slide-visual-polish-qa.html-capture-cache.v1` exact-binding contract rather
than skipping HTML QA.

## Quality invariants

The benchmark output remained identical to the accepted Terra reconstruction
for all recorded comparison metrics:

| Comparison | SSIM | Edge delta | Palette drift | Delta from accepted output |
| --- | ---: | ---: | ---: | ---: |
| PPTX vs source | 0.5788593683 | 0.1205661543 | 0.1325075380 | 0 |
| HTML vs source | 0.5882054302 | 0.1154236306 | 0.1834751537 | 0 |
| PPTX vs HTML | 0.8348168833 | 0.0737362014 | 0.0864898637 | 0 |

Editability also remained unchanged: 284 editable objects, 102 native text
objects, 1,102 editable text characters, and zero full-slide crops.

## Main-workflow decision

- Default authoring profile: `terra-max`.
- A slide enters the fast lane only when source PNG, Semantic Sidecar,
  measured-vector receipt, authoring files, crop plan, renderer/QA profiles, and
  both final render surfaces match their sealed hashes.
- On a cache miss, changed input, missing evidence, or quality rejection, the
  slide returns to the full `terra-max` quality lane. There is no threshold
  weakening or automatic acceptance.
- Measurement and bounded SVG preflight run per accepted image before the
  reconstruction worker starts, so ImageGen and reconstruction still overlap.
- Expensive measurement is outside the short streaming-state lock; immutable
  per-slide receipts prevent the final batch seal from rewriting earlier jobs.

The under-two-minute goal is therefore a verified-authoring/cache-hit SLA. A
first-time arbitrary image remains quality-first and is reported with its real
duration until a future deterministic authoring system proves the same bound.
