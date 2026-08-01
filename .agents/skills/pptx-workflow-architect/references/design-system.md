# Design System Reference

## Table of Contents
1. [Visual Strategy & Rendering Module](#visual-strategy--rendering-module)
2. [Anti-Generic Design Rule](#anti-generic-design-rule)
3. [Master Design System Specification](#master-design-system-specification)
4. [Infographic Rules](#infographic-rules)
5. [Slide Frame Optimization](#slide-frame-optimization)
6. [Reference-Driven Design Intelligence](#reference-driven-design-intelligence)

---

## Visual Strategy & Rendering Module

When design quality matters strongly, activate this module. Behave like a global-caliber art director and presentation information architect.

### A. Trend Scan & Visual DNA

Analyze the topic, audience, purpose, delivery mode, credibility level, and brand constraints. Scan relevant reference families when available. Define **3 Visual DNA Principles** for this deck.

Per principle include:
- Principle name
- What visual behavior it means
- Why it fits this presentation
- Overuse risk

### B. Master Design System

Convert Visual DNA into measurable deck-wide design rules. Use tables where helpful. Define color, type, spacing, grid, layout, chart, table, icon, screenshot, and infographic systems. Large decks must lock the design system before production.

### C. Rendering Blueprint

Convert the approved slide blueprint into slide-level visual implementation plans. Per slide or cluster specify:

| Field | Description |
|-------|-------------|
| Slide # and topic | |
| Slide purpose | |
| Layout pattern | |
| Grid layout | |
| Typography & color hierarchy | |
| Visual asset direction | |
| Infographic/chart type | |
| Motion cue (only if useful) | |
| Readability/frame-fit note | |
| Asset dependency | |
| Fallback simpler version | |

**Writing style for rendering blueprints:** Use direct, implementation-friendly language. Be spatial, concrete, and visual. Do not hide behind vague adjectives. Give reproducible layout logic, not empty style words.

---

## Anti-Generic Design Rule

Never stop at vague adjectives. If the user says any of these, translate into explicit visual behavior:

| Vague Term | Translate Into |
|------------|---------------|
| "professional" | Level of formality, corporate vs editorial tone, density |
| "clean" | Whitespace ratio, element count per slide, spacing scale |
| "modern" | Modern vs conservative feel, title scale, section-divider style |
| "premium" | Contrast strategy, image dependence, typography weight |
| "simple" | Density, data emphasis, icon simplicity |
| "tech-forward" | Chart style, icon style (line vs filled), color temperature |
| "elegant" | Serif vs sans-serif, whitespace, muted palette |
| "bold" | Degree of visual boldness, accent color intensity, type weight |

Always specify: level of formality, density, editorial vs corporate tone, modern vs conservative feel, whitespace usage, title scale, contrast strategy, image dependence, data emphasis, icon style, chart style, section-divider behavior.

---

## Master Design System Specification

The blueprint must define all of these as deck-wide rules. Use tables for reviewability.

### Color System

| Token | Hex | Usage | Ratio |
|-------|-----|-------|-------|
| Background | | | |
| Surface | | | |
| Primary text | | | |
| Secondary text | | | |
| Accent | | | |
| Secondary accent | | | |
| Data viz colors | | | |
| Status colors (if needed) | | | |

Include: suggested usage ratio, pairings to avoid.

### Typography Hierarchy

| Element | Font Family | Size | Weight | Tracking | Line-height | Emphasis Rule |
|---------|------------|------|--------|----------|-------------|---------------|
| Hero title | | | | | | |
| Section title | | | | | | |
| Headline | | | | | | |
| Body | | | | | | |
| Caption | | | | | | |
| Data label | | | | | | |

### Spatial System

Define: target slide ratio, safe area, margin rule, spacing scale, alignment logic, grid logic, section divider behavior.

### Visual System Rules

Define: icon style, chart style, table style, screenshot treatment, callout style, highlight method, corner radius / border / shadow guidance, infographic rule, animation/motion rule (only when truly useful).

### Layout Library

Define 6–12 reusable layout patterns. For each:

| Field | Content |
|-------|---------|
| Layout name | |
| Best use case | |
| Composition logic | |
| Density guidance | |
| Fit risks | |

Typical patterns: cover, section divider, agenda/roadmap, concept explainer, comparison, process/flow, timeline, framework/model, evidence/chart, case study, quote/insight, summary/next step, appendix/reference, infographic-heavy slide.

Each slide should map to a named layout pattern unless there is a justified exception. Variety comes from content emphasis, not random composition changes.

---

## Infographic Rules

Use infographics only when they clarify the message faster than bullets, tables, or plain text.

### Principles
- Every infographic must be **slide-native**, not poster-like
- Design for the target slide frame from the beginning
- Readability is the highest priority; decorative complexity is secondary
- Never place a portrait infographic onto a landscape slide without redesigning
- If dense or hard to read → redesign or split into multiple slides
- Prefer one dominant idea per infographic
- Use a clear reading path
- Keep labels concise and scannable
- Speaker notes carry nuance; the slide carries the core message

### Supported Types
- Process / flow
- Timeline
- Hierarchy
- Comparison
- Before vs after
- System map
- Framework
- Metric summary
- Decision path

Do not force an infographic when a chart, table, or simple comparison is clearer.

### Infographic Plan Format

Per slide where infographic is proposed:

| Field | Content |
|-------|---------|
| Slide number | |
| Infographic type | |
| Purpose | |
| Core message | |
| Required data / labels | |
| Why infographic > bullets | |
| Frame-fit considerations | |
| Fallback simpler version | |

---

## Slide Frame Optimization

Always design for the declared slide ratio first (typically 16:9).

### Rules
- Compose every visual for the actual slide frame
- Never solve fit problems by shrinking everything
- Preserve safe margins and breathing room
- Do not place critical labels too close to edges
- When a visual is too dense: simplify first → split second → shrink last
- For live presentations, optimize for rapid distance-view comprehension

### 3-Second Comprehension Test

Every visual slide must pass:
1. Is the main point obvious?
2. Is the reading path obvious?
3. Are labels scannable?
4. Is anything competing with the main message?

---

## Reference-Driven Design Intelligence

Design must never be generated from vague taste alone. When browsing or reference scanning is available, run a **mandatory Template Reference Scan** before locking the visual system.

### Process
1. Scan 3–5 reputable template ecosystems or deck references
2. Prioritize current, professional sources suited to the presentation type
3. Source families may include: Microsoft PowerPoint templates, Canva professional templates, Slidesgo, Beautiful.ai, Pitch, or other credible ecosystems

### Rules
- Do not copy one template
- Do not imitate one brand too closely
- Do not recreate proprietary slides verbatim
- Synthesize patterns across multiple sources

### Extract Patterns For
- Layout logic and hierarchy
- Whitespace behavior
- Section divider style
- Chart and diagram treatment
- Color / accent strategy
- Icon / illustration treatment
- Pacing across slides
- Title behavior
- Editorial vs corporate tone

This is per-project reference analysis only. Never claim permanent learning.
