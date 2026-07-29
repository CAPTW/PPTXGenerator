# 🎛️ Documentation Style Guide

This guide keeps public-facing Markdown visually consistent while protecting immutable technical evidence.

---

## 1. Visual hierarchy

Every public document should use:

1. one clear `#` title;
2. a short status or purpose block;
3. a compact navigation row;
4. an “at a glance” table before long prose;
5. diagrams or tables for relationships;
6. `<details>` for secondary depth;
7. a final status or next-action section.

## 2. Reusable navigation

For files under `docs/devpost/submission/`:

```markdown
> [Documentation hub](../../README.md) ·
> [Project README](../../../README.md) ·
> [Final evidence](../evidence/phase7_final/)
```

## 3. Status vocabulary

Use exact states:

- `ELIGIBLE_FOR_DEVPOST_SUBMISSION`
- `READY_FOR_MANUAL_SUBMISSION — NOT YET SUBMITTED`
- `Published`
- `Not created`
- `Not yet submitted`
- `PENDING_USER_FEEDBACK`

Do not use vague states such as “finished,” “ready enough,” or “basically complete.”

## 4. Information density

- Prefer tables for comparisons and inventories.
- Prefer Mermaid for pipelines and ownership.
- Keep paragraphs under 5 lines where possible.
- Place hashes and deep evidence in collapsible sections.
- Put limitations near claims, not in a hidden appendix.

## 5. Immutable evidence boundary

Do **not** visually rewrite:

- final gate JSON;
- package validation JSON;
- fingerprint manifests;
- hash-bound phase evidence;
- committed delivery ZIP;
- machine-readable run manifests.

Instead, link to them from a human-oriented index.

## 6. Public-state freshness

After publication events, update these documents together:

- `README.md`
- `PUBLICATION_BOUNDARY.md`
- `docs/devpost/submission/DEVPOST_FORM_PAYLOAD.md`
- `docs/devpost/submission/KNOWN_LIMITATIONS.md`
- `docs/devpost/submission/GITHUB_PUBLICATION_PLAN.md`
- `docs/devpost/submission/SUBMISSION_CHECKLIST.md`
- `docs/devpost/submission/FINAL_HUMAN_REVIEW_CHECKLIST.md`
