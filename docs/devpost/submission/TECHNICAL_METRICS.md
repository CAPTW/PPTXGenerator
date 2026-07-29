# Technical Metrics

| Metric | Result |
|---|---:|
| Public demo stages | 36/36 PASS |
| Prompt inputs | 1 |
| Searchable PDF inputs | 2 |
| Source Corpus records | 3 |
| Evidence Units | 29 |
| Slides | 6 |
| Editable text objects | 131 |
| Native tables | 1 |
| Picture objects | 0 |
| Full-slide raster violations | 0 |
| Semantic PPTX/HTML checks | 66/66 each |
| Number and unit checks | 79/79 |
| Citation checks | 30/30 |
| Source bindings | 48/48 |
| PowerPoint renders | 6/6 |
| Chromium captures | 6/6 |
| Unique layouts | 6 |
| Severe overlap / off-canvas | 0 / 0 |
| External Python entrypoints | 6 |
| Locked distributions | 38 |
| Installed distributions | 40, including `pip` and `setuptools` |
| Unexpected distributions | 0 |
| Historical Phase 7 full-workspace focused tests | 274 PASS |
| Historical Phase 7 full-workspace suite | 733 PASS |
| Current public minimal-snapshot suite | 490 PASS |
| Final release prerequisites | 81/81 PASS |
| Canonical-repeat divergence | 0 |
| Fresh-repeat divergence | 0 |
| Canonical-fresh divergence | 0 |
| Delivery files / bytes | 92 / 7,646,285 |
| Delivery ZIP bytes | 6,704,897 |
| Original Phase 4 tool invocations | 15 |
| Selected Phase 4 reference artifacts | 13 |
| Slide Visual Targets | 6 |
| Release CLI live Image Generation calls | 0 |

The 274/733 rows summarize immutable historical evidence from the full Phase 7
workspace. They are not a claim about the bounded test inventory published in
this release-minimal snapshot; the current public snapshot contains 490 tests.

The original platform-managed Phase 4 workflow executed Image Generation. Its
image-model identity was not exposed. The reproducible release CLI uses the
frozen verified bundle and makes no live Image Generation call.

## Environment authority

The certified fresh-clone environment is CPython 3.11.9 AMD64, Node.js
24.13.1, npm 11.11.0, PowerPoint 16.0 build 20131 x64, Playwright 1.61.0,
Chromium revision 1228, and Chrome for Testing 149.0.7827.55.

A later prerequisite recheck observed Node.js 24.14.0 and PowerPoint build
20228. These later values are not the certified canonical-run environment.

## Key fingerprints

- corrected runtime tree:
  `a69f5d3f8208ee91694ab9e46d70c81cb0b7ad7e8e3e0e193a63e4d5c7660d91`
- release lock:
  `4fde8f6fd2584f66e2c5f6c0f57f822da19809cb9d12259e35537d3d378a21dc`
- installed distribution inventory:
  `3c150c99c0d4f9721e8cd9e4ad5f69e714b1740349b56b3a67c9017af58f18f2`
- PPTX structural fingerprint:
  `24e74317a8c305831415807232366fb4050d87bc625e0f0d2f7341d462f1d807`
- HTML structural fingerprint:
  `d0682d1340267b25de212ff546ace56af87edd4b45ef2126f58b1e5790e38260`
- canonical package logical fingerprint:
  `987d743fb7e48a5ae5402bb503b6748f385c7289ce3eba597ab5a08800703ceb`
- cross-root normalized semantic package fingerprint:
  `5a6a005ae7f273f481fb61999c4fc67cd570c75bffffa54b3b66acef59be0fd2`
