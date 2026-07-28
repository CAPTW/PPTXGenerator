# Session Provenance

| Field | Value |
|---|---|
| Public product | PPTX Generator |
| Internal system | DeckCompiler |
| Phase 7 starting HEAD | `9388d42427de305ed6e9d2bbe536eb9ee894d6a0` |
| Phase 7 starting tree | `63c9178acdd225aba7a9abcd927b340b114df5e1` |
| Runtime Commit R1 | `bc38504a49623be0c8d7600fa17af409807799af` |
| Runtime correction | `5d845d373ae2255b5d490c45ce4e3435107c3d08` |
| Tested runtime commit | `5d845d373ae2255b5d490c45ce4e3435107c3d08` |
| Final evidence commit | `23862977a0c8ac9084af007f5213223f445b0672` |
| Corrected runtime tree | `a69f5d3f8208ee91694ab9e46d70c81cb0b7ad7e8e3e0e193a63e4d5c7660d91` |
| Canonical run IDs | `phase7run_4e36616cd03ce7bff6a7`, `phase7run_5f242f8f1eacff54d148` |
| Fresh run IDs | `phase7run_a3587992bf9c29755b4a`, `phase7run_6cbf43e04e0a337a4031` |
| Release profile | `devpost_p0_frozen_visuals` |
| Original Phase 4 Image Generation | executed by the platform-managed tool; provenance and selected hashes recorded |
| Release CLI Image Generation | not executed; frozen verified bundle consumed; no API key required |
| Image-model identity | not exposed; not claimed |
| Submission / push / tag | not performed / not performed / not created |
| Codex Session ID | `PENDING_USER_FEEDBACK` |

## Certified fresh-clone environment

CPython 3.11.9 AMD64; Node.js 24.13.1; npm 11.11.0; Microsoft
PowerPoint 16.0 build 20131 x64; Playwright 1.61.0; Chromium revision 1228;
Chrome for Testing 149.0.7827.55.

## Later live prerequisite recheck

Node.js 24.14.0 and Microsoft PowerPoint build 20228 were observed later. They
are not the certified canonical-run environment.

The final evidence commit is represented as `resolved_by_git_metadata` inside
self-contained gate artifacts to avoid commit self-reference. The Phase 8A
submission-document commit, if present, is likewise resolved from current Git
metadata and must preserve the runtime-tree hash above.

Run `/feedback` after review to obtain the actual Codex Session ID. Do not
replace historical pending values with an inferred value or with an ID from a
different session.
