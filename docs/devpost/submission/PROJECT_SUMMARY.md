# PPTX Generator — Project Summary

PPTX Generator turns a prompt and local source documents into a polished,
evidence-linked, editable PowerPoint deck and companion HTML presentation. Its
internal system, DeckCompiler, separates content planning, frozen visual
direction, editable reconstruction, deterministic packaging, and
evidence-backed quality gates.

The DevPost release candidate is a six-slide reference workflow that produces
fresh PPTX and HTML outputs from one prompt plus exactly two text-searchable
PDFs. The intake becomes three sources and 29 Evidence Units. Real text remains
PowerPoint text, the table remains native, and the deck contains no full-slide
raster backgrounds.

The original platform-managed Phase 4 workflow executed Image Generation and
recorded provenance and selected-image hashes. The release CLI validates and
uses that frozen visual bundle; it does not invoke live Image Generation,
require an API key, or claim an unexposed image-model identity.

Phase 7.0.3 closed the last fresh-clone blocker. DeckCompiler now owns an exact,
hash-locked Python environment for the external scripts it launches with its
own interpreter. The lock contains 38 distributions, including NumPy and every
reached transitive requirement. Six external Python entrypoints are pinned by
source hash and exercised by preflight canaries.

The corrected runtime was proved in two environments:

- a canonical workspace, with two independent output roots; and
- a brand-new physical `--no-local --no-checkout` clone, with a brand-new
  isolated virtual environment and two more independent output roots.

All four runs completed 36 of 36 stages. Canonical-repeat, fresh-repeat, and
canonical-fresh comparisons found zero unexplained semantic divergence. The
fresh clone passed 274 focused tests and the full 733-test DeckCompiler suite.

The release evidence is collected in
[`../evidence/phase7_final/`](../evidence/phase7_final/). The final gate is
`ELIGIBLE_FOR_DEVPOST_SUBMISSION`, while actual submission, push, and tag
creation remain intentionally unperformed.
