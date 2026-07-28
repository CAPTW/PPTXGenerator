# Screenshot and Artifact Index

All media candidates below are exact entries from the committed canonical ZIP:
[`pptx_generator_devpost_delivery.zip`](../evidence/phase7_final/pptx_generator_devpost_delivery.zip),
SHA-256
`b5a17b8569239c002ab9d8566c8b5c88c828d3019d9849a055b5ba14b27fc2a2`.
The `ZIP!/entry` notation identifies a repository evidence location without
introducing a machine-local path.

## Ordered media candidates

| Order | Public label | Source artifact | Package-relative location | Repository evidence location | Raw SHA-256 | Dimensions | What it proves | Allowed public claim | Prohibited inference | Alternate |
|---:|---|---|---|---|---|---:|---|---|---|---|
| 1 | Six-slide deck overview | PowerPoint contact sheet | `renders/contact_sheet.png` | `docs/devpost/evidence/phase7_final/pptx_generator_devpost_delivery.zip!/renders/contact_sheet.png` | `bc98b5ef65a528b6bda484f5ae0b85484ef209fc583e2efb1fe631453ab40adb` | 1824×800 | all six slides, order, palette, and module continuity | The canonical P0 produces one coherent six-slide deck. | General fidelity for arbitrary documents or platforms | slide 1 |
| 2 | Decision framing | PowerPoint render, slide 1 | `renders/slide-001.png` | `docs/devpost/evidence/phase7_final/pptx_generator_devpost_delivery.zip!/renders/slide-001.png` | `1d9753e704f776238d07862082540ee78dbc64630d50a8136e43151a28633684` | 1920×1080 | title hierarchy, decision framing, citations | The verified deck opens with a readable decision frame. | Generated-image final slide or universal template quality | contact sheet |
| 3 | System and process | PowerPoint render, slide 2 | `renders/slide-002.png` | `docs/devpost/evidence/phase7_final/pptx_generator_devpost_delivery.zip!/renders/slide-002.png` | `95da832e8af843baa86227eddd0933ee122d3238d4264a6fdd1647746c1df13e` | 1920×1080 | four-step process, arrows, native text hierarchy | The canonical output communicates the operating process in editable structure. | Proof of live system telemetry or animation | slide 6 |
| 4 | Evidence-backed risks | PowerPoint render, slide 3 | `renders/slide-003.png` | `docs/devpost/evidence/phase7_final/pptx_generator_devpost_delivery.zip!/renders/slide-003.png` | `8da4216332f596e20de3df53e34c1592c5b31818181f06e64b21f06ca2f2901f` | 1920×1080 | five sourced risk findings and citation footer | Claims in the P0 deck are bound to recorded source evidence. | Zero-hallucination or truth beyond the supplied synthetic sources | slide 4 |
| 5 | Response trade-offs | PowerPoint render, slide 4 | `renders/slide-004.png` | `docs/devpost/evidence/phase7_final/pptx_generator_devpost_delivery.zip!/renders/slide-004.png` | `855ae16e06b6e3c70aa795a7ce8feac03d699327135f2e5aff320c94e7a064a8` | 1920×1080 | comparison structure and native four-row table | The verified PPTX contains a native editable comparison table. | Spreadsheet equivalence or arbitrary data-chart support | slide 3 |
| 6 | Recommendation | PowerPoint render, slide 5 | `renders/slide-005.png` | `docs/devpost/evidence/phase7_final/pptx_generator_devpost_delivery.zip!/renders/slide-005.png` | `1a9ecda45b6d0d475425dd84b83b441deeb8f040357c3a97fc6af43caf5659e2` | 1920×1080 | recommendation, rationale, staged response | The canonical deck connects evidence to a readable recommendation. | Automated engineering approval or domain guarantee | slide 1 |
| 7 | Implementation and sources | PowerPoint render, slide 6 | `renders/slide-006.png` | `docs/devpost/evidence/phase7_final/pptx_generator_devpost_delivery.zip!/renders/slide-006.png` | `6f838b7d761103fea32ed7d90872db13d764ba088f6b0e3f7c159b5e160aa870` | 1920×1080 | implementation sequence and source-note closure | The story closes with an ordered implementation path and visible citations. | Deployment completion or production operational status | slide 2 |
| 8 | Controlled fault and repair | Phase 6 proof contact sheet | `repair/before_faulty_repaired_contact_sheet.png` | `docs/devpost/evidence/phase7_final/pptx_generator_devpost_delivery.zip!/repair/before_faulty_repaired_contact_sheet.png` | `57c30bcca3d2e7b69afd8782357925395b230754f2cb13cdb026a66d68d584b0` | 2512×526 | baseline, intentional off-canvas fault, repaired state | The bounded repair evidence converged in one upstream repair wave without direct final-output patching. | A live fault reinjection in the default demo or universal self-healing | contact sheet |

The faulty state is never uploaded alone; it appears only in the labeled
before/faulty/repaired context.

## Delivery candidates

| Artifact | Repository path | Raw SHA-256 | Bytes | Public use |
|---|---|---|---:|---|
| Canonical delivery ZIP | `docs/devpost/evidence/phase7_final/pptx_generator_devpost_delivery.zip` | `b5a17b8569239c002ab9d8566c8b5c88c828d3019d9849a055b5ba14b27fc2a2` | 6,704,897 | Candidate GitHub Release asset after explicit authorization |
| Editable PPTX inside ZIP | `ZIP!/output/pptx_generator_demo.pptx` | `d592581a34a72befe2d463eab98489cb7af45c3231f5bd1b4082742372a21c97` | 261,527 | Manual demonstration and editability review |
| Companion HTML inside ZIP | `ZIP!/output/html/index.html` | `b1f161bed4d1dc37be576eceda0cf01d125580df4a767c4722582c8671983085` | 85,014 | Local companion presentation; no hosted URL is claimed |

## Review notes

The contact sheet, all six PowerPoint renders, and the repair proof were
manually reviewed at their native dimensions. Titles, body copy, tables,
citations, slide order, and visual hierarchy remain readable; no blocking
clipping, overlap, or off-canvas defect was found. PowerPoint opened the PPTX
read-only as six slides with zero off-canvas objects. The package's Chromium QA
evidence reports six HTML slides, correct order, one native table, zero missing
assets, zero machine paths, and zero external network dependencies.
