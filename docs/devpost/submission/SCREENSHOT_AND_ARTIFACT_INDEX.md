# 🖼️ Screenshot and Artifact Index

> [Submission hub](README.md) · [Documentation hub](../../README.md) · [Project README](../../../README.md) · [Final evidence](../evidence/phase7_final/)

> All media candidates are exact entries from the committed canonical ZIP. The faulty state is never shown alone; it appears only in the labeled before/faulty/repaired proof.

**Canonical ZIP SHA-256:** `b5a17b8569239c002ab9d8566c8b5c88c828d3019d9849a055b5ba14b27fc2a2`

---

## Recommended upload order

| # | Public label | Artifact | SHA-256 | Dimensions | What it proves |
|---:|---|---|---|---:|---|
| 1 | Six-slide deck overview | `renders/contact_sheet.png` | `bc98b5ef65a528b6bda484f5ae0b85484ef209fc583e2efb1fe631453ab40adb` | 1824×800 | order, palette, module continuity |
| 2 | Decision framing | `renders/slide-001.png` | `1d9753e704f776238d07862082540ee78dbc64630d50a8136e43151a28633684` | 1920×1080 | hierarchy, thesis, citations |
| 3 | System and process | `renders/slide-002.png` | `95da832e8af843baa86227eddd0933ee122d3238d4264a6fdd1647746c1df13e` | 1920×1080 | native process structure |
| 4 | Evidence-backed risks | `renders/slide-003.png` | `8da4216332f596e20de3df53e34c1592c5b31818181f06e64b21f06ca2f2901f` | 1920×1080 | sourced risk findings |
| 5 | Response trade-offs | `renders/slide-004.png` | `855ae16e06b6e3c70aa795a7ce8feac03d699327135f2e5aff320c94e7a064a8` | 1920×1080 | native editable comparison table |
| 6 | Recommendation | `renders/slide-005.png` | `1a9ecda45b6d0d475425dd84b83b441deeb8f040357c3a97fc6af43caf5659e2` | 1920×1080 | evidence-to-action narrative |
| 7 | Implementation and sources | `renders/slide-006.png` | `6f838b7d761103fea32ed7d90872db13d764ba088f6b0e3f7c159b5e160aa870` | 1920×1080 | roadmap and visible source notes |
| 8 | Controlled fault and repair | `repair/before_faulty_repaired_contact_sheet.png` | `57c30bcca3d2e7b69afd8782357925395b230754f2cb13cdb026a66d68d584b0` | 2512×526 | bounded repair without direct final-output patching |

---

## Delivery artifacts

| Artifact | Repository location | SHA-256 | Bytes |
|---|---|---|---:|
| Canonical ZIP | `docs/devpost/evidence/phase7_final/pptx_generator_devpost_delivery.zip` | `b5a17b8569239c002ab9d8566c8b5c88c828d3019d9849a055b5ba14b27fc2a2` | 6,704,897 |
| Editable PPTX | `ZIP!/output/pptx_generator_demo.pptx` | `d592581a34a72befe2d463eab98489cb7af45c3231f5bd1b4082742372a21c97` | 261,527 |
| Companion HTML | `ZIP!/output/html/index.html` | `b1f161bed4d1dc37be576eceda0cf01d125580df4a767c4722582c8671983085` | 85,014 |

---

## Review result

- titles, body copy, tables, citations, and visual hierarchy remain readable;
- no blocking clipping, overlap, or off-canvas defect was found;
- PowerPoint opened the PPTX read-only as six slides;
- HTML evidence reports six slides, one native table, no missing assets, no machine paths, and no external network dependencies.
