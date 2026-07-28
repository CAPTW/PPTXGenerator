# Public Snapshot Boundary

This repository is a release-minimal public snapshot of PPTX Generator. It is
not the project's complete development history.

## Included

- The source, documentation, schemas, examples, tests, and locked release
  evidence needed to review the public DevPost candidate.
- The canonical delivery ZIP and its committed verification evidence.
- The path-neutral external Skill fingerprint pin required by the demo; local
  installation paths are represented as `<external-skill-root>`.
- Publication-only metadata: this boundary notice and the root `LICENSE`.

## Deliberately omitted

- Git history predating this public snapshot.
- Machine-local paths, credentials, tokens, and authentication material.
- Repository files outside the reviewed release-minimal publication allowlist,
  including unrelated development assets and tests.
- Nine release-authority tests whose fixtures require omitted Git history or
  machine-local paths.
- External CAPTW/pngtopptx Skill source, Python environments, Node modules,
  browser binaries, font binaries, Microsoft Office binaries, and
  Tesseract/Cairo binaries.

The omitted external Skill source and installed software are prerequisites, not
part of this repository. Their own licenses and terms continue to apply.

## License scope

Files in this published snapshot are provided under the Apache License 2.0
unless a file or third-party notice states otherwise. This repository license
does not grant rights to omitted material or replace terms governing external
software, dependencies, or services. Adding this license does not record or
imply acceptance of any separate license terms on behalf of any person or
system.

See `THIRD_PARTY_NOTICES.md` for dependency and redistribution boundaries.
