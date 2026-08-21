# Production & QA Reference

## Table of Contents
1. [Slide Production Standards](#slide-production-standards)
2. [Final QA Checklist](#final-qa-checklist)
3. [Export & Deliverable Requirements](#export--deliverable-requirements)
4. [Revision Protocol](#revision-protocol)
5. [Prohibitions](#prohibitions)

---

## Slide Production Standards

Once the blueprint is approved, produce final slides or production-ready specifications.

### Per Slide Output

| Field | Content |
|-------|---------|
| Slide number / title | |
| Slide purpose | |
| On-slide copy | The actual text that appears on the slide |
| Main body elements | As many as the approved content and layout require; verify hierarchy and legibility |
| Layout pattern used | From the layout library |
| Visual type | Chart / diagram / icon grid / infographic / image |
| Why this layout was selected | Strategic rationale |
| Visual / layout instructions | Spatial, concrete directions for production |
| Presenter notes | What the speaker says (not what's on the slide) |
| Source / evidence note | Citation or data source if relevant |
| Readability / frame-fit note | Does it work in the declared viewing context? |

### For Infographic-Heavy Slides, Also Include

| Field | Content |
|-------|---------|
| Infographic specification | Type, nodes, labels, reading path |
| Frame-fit note | Does it work at slide scale? |
| Readability check | Labels scannable? Reading path clear? |
| Fallback option | Split-into-two-slides version if needed |

---

## Final QA Checklist

Before calling any deck complete, verify all of these.

### Standard QA (All Decks)

| Category | Check |
|----------|-------|
| Audience fit | Does tone/depth match the target audience? |
| Message clarity | Is the core message unmistakable? |
| Story logic | Does the narrative flow make sense? |
| Section pacing | Are sections balanced in length and weight? |
| Tone consistency | Same voice throughout? |
| Terminology consistency | Same terms for same concepts? |
| Design consistency | Same visual system on every slide? |
| Visual hierarchy | Is the most important element most prominent? |
| Slide-frame fit | Does every visual fit the declared ratio? |
| Infographic readability | Can each infographic be understood in seconds? |
| Chart / table clarity | Are axes labeled? Are comparisons clear? |
| Text density | No text walls? Concise enough for delivery mode? |
| Evidence integrity | Are data points accurate and sourced? |
| Source completeness | All claims backed where required? |
| Numbering consistency | Sequential, no gaps, no duplicates? |
| Appendix boundary | Clear separation between main story and backup? |
| Actionability | Does the final slide drive action or next steps? |
| PPTX readiness | Will this render correctly in PowerPoint? |
| Google Slides compat | Will layout survive Google Slides import? |
| Presenter notes | Complete and useful where needed? |
| Source-image fidelity | Does each reconstructed slide preserve the approved reference's hierarchy, spacing, density, and meaningful detail rather than collapsing into a generic template? |
| Native editability | Are readable text and structural elements native, with crops limited to justified photoreal/continuous-tone regions? |
| Per-slide isolation evidence | Does every source image have one hash-bound fresh-context job, worker receipt, and official integration record? |
| High-fidelity acceptance | Are all remaining Visual QA issues limited to the explicitly allowed native-renderer diagnostics? |
| QA profile identity | Is `default-visual-qa-profile.json` passed explicitly to visual comparison, and kept distinct from the deck design profile in `styles/active.json`? |
| On-demand icon evidence | Does each isolated worker declare `icon_usage.json`, does the integrator write the union manifest, and does the renderer bind its icon cache manifest? |
| One-slide fast cache | On a cache hit, are authoring inputs reused only when every hash still matches while final dual render, hardlocks, source-mapped Visual QA, and one-process acceptance validation still run? Does the accepted evidence bind both PPTX raster and HTML screenshot plus their hash-bound metadata? |

### Large Deck QA (Additional)

| Category | Check |
|----------|-------|
| Cross-batch consistency | Same design system across all batches? |
| Numbering audit | Slide numbers correct after all batches? |
| Terminology audit | No concept drift across batches? |
| Design-drift audit | No style changes without notice? |
| Repetition / gap audit | No unintended duplicates? No missing topics? |
| Assembly order | All batches in correct final sequence? |
| Navigation elements | Section dividers, recaps, roadmaps in place? |

---

## Export & Deliverable Requirements

### Default Target
A **downloadable PPTX file** whenever the environment supports file generation.

### Alternative Target
A Google Slides–ready or export-ready deck when directly supported.

### Compatibility Rules
- The deck must transfer cleanly into PowerPoint or Google Slides
- PPTX compatibility is the baseline requirement
- Do not rely on fragile layout tricks likely to break on import
- Favor robust layout logic, standard-safe composition, predictable asset placement
- Keep slide ratio explicitly locked
- When choosing fonts, charts, tables, and visual treatments, prefer choices that survive PPTX and Google Slides workflows

### If Direct File Export Is Unavailable

Produce an import-ready production package preserving:
- Slide order and titles
- On-slide copy
- Presenter notes
- Layout pattern
- Image / chart / infographic placement intent
- Section structure
- Numbering logic
- Appendix boundaries

### Final Delivery Statement

Always clearly state which format is being delivered:
- Downloadable PPTX
- Google Slides exportable deck
- Import-ready production package (if direct export unavailable)

---

## Revision Protocol

When revising a deck, assess ripple effects before making changes.

### Ripple Effect Assessment

Check impact on:
- Numbering
- Cross-references
- Repeated examples
- Layout consistency
- Section balance
- Story logic
- Summary slides
- Appendix references

### Revision Classification

| Classification | Scope | Action Required |
|---------------|-------|-----------------|
| Local Change Only | Single slide, no downstream effects | Fix in place |
| Section-Level Reflow | Affects numbering/flow within one section | Recheck section pacing and transitions |
| Deck-Level Reflow | Affects overall story, numbering, or design | Full recheck of cross-references, summaries, navigation |

### Revision Communication

State clearly:
- What changed
- What stays locked
- What must be updated elsewhere

---

## Prohibitions

Do not:
- Produce final slides before blueprint approval
- Force a fixed multi-phase template on every project
- Prioritize trendiness over communication purpose
- Mimic one template or one brand too closely
- Reject an infographic, dashboard, table, card grid, or poster-influenced
  composition solely because of its category; evaluate purpose, legibility,
  reconstruction feasibility, and audience fit instead
- Use generic adjectives without operationalizing them
- Ask the user to manage large-deck batching manually (unless requested)
- Lose continuity across batches
- Inflate slide count without a communication reason
- Bury the main message under supporting detail
- Rely on fragile layout tricks that may break in PowerPoint or Google Slides
- Output only text when the environment supports a real presentation file
- Pass a deck design profile to `compare_slide_images.py --profile`; only the
  hash-bound `slide-visual-polish-qa` calibration profile is valid
- Treat a one-slide cache hit as permission to skip final PPTX/HTML rendering,
  PowerPoint openability, hardlocks, or source-mapped Visual QA
