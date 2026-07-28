# GitHub Publication Plan

Planning status: `NOT AUTHORIZED — NO REMOTE ACTION PERFORMED`

## Current local publication audit

| Check | Result |
|---|---|
| Public title and root README | PPTX Generator identity, current release status, run command, boundaries, and limitations are explicit |
| Repository license | No root `LICENSE` file is present; public visibility would not grant reuse rights |
| Third-party notices | `THIRD_PARTY_NOTICES.md` present; external Skill and binary redistribution boundaries explicit |
| Release lock | `requirements/devpost-release.lock.txt` present; 38 exact hash-bearing distributions |
| Setup guide | `docs/devpost/PHASE_07_DEPENDENCY_AND_RUNTIME_GUIDE.md` present |
| Demo runbook | `docs/devpost/PHASE_07_DEMO_RUNBOOK.md` present |
| One-command demo | `presentation_agent.deckcompiler demo` documented |
| Known limitations | `docs/devpost/submission/KNOWN_LIMITATIONS.md` present and public-facing |
| Contribution policy | not present; optional for this P0 |
| Security policy | not present; optional for this P0 |
| Secret scan | no credential found; one intentional fake private-key marker exists in a delivery-package scanner test fixture |
| User-path scan | 1,608 machine-local path references remain in historical analysis/design evidence; submission documents and the canonical ZIP remain clean |
| Oversized tracked file | 0 files exceed 10 MiB; the canonical ZIP is the largest tracked file at 6,704,897 bytes |
| Generated cache | 0 tracked cache-directory entries |
| Protected historical outputs | absent |
| External Skill source | absent; pinned external source is not vendored |
| Git provenance | final evidence lineage retained; no history rewrite authorized |
| Current branch | `devpost/deckcompiler` |
| Current remote | `origin` is a sanitized local-filesystem remote; no public GitHub remote exists |
| Repository name authorization | not supplied |
| Visibility authorization | not supplied |

The technical package's dependency-license and provenance evidence is complete.
The missing root repository license is a separate owner choice. If the
repository is made public without one, the code remains all-rights-reserved by
default; no license is inferred here.

The repository-wide path result is not a package or submission-kit leak, and
the matched `USER` segments do not identify a live credential. It is still a
public-history hygiene issue. A full-history public push is therefore
conditional on either a separately authorized sanitation pass, an approved
scoped publication branch/history, or the owner's explicit acceptance after
review. Phase 8A does not rewrite or sanitize historical evidence.

## Repository name candidates

- Preferred: `pptx-generator`
- Alternative: `pptx-generator-deckcompiler`

Do not rename the local repository or choose a public name without explicit
owner approval.

## Visibility options

- public
- private until DevPost submission
- private permanently

Public visibility may help judges inspect evidence, but it is not selected by
this plan. The owner must explicitly approve visibility, path-history scope,
and any repository license change.

## Publication branch options

Current branch: `devpost/deckcompiler`

- push the current branch and make it the default branch;
- create a publication branch in a later authorized lane; or
- merge into `main` only through a separately authorized workflow.

No branch is created, renamed, merged, or selected here. Publishing the full
selected history may preserve useful Build Week provenance, but the
machine-local path inventory above makes a scoped or sanitized publication
branch the safer candidate. Its exact history scope must be approved before
push.

## Candidate release

| Item | Candidate |
|---|---|
| Tag | `v0.1.0-devpost` |
| GitHub Release title | `PPTX Generator — DevPost P0` |
| Release asset | `pptx_generator_devpost_delivery.zip` |
| Asset SHA-256 | `b5a17b8569239c002ab9d8566c8b5c88c828d3019d9849a055b5ba14b27fc2a2` |
| Asset bytes | 6,704,897 |

These are candidates only. No tag, release, or asset upload has been created.

## Build Week and ownership disclosure

The public history and release notes must retain the audited
Build Week/adapted/external boundary in
[`EXISTING_ADAPTED_NEW.md`](EXISTING_ADAPTED_NEW.md).

The external CAPTW/pngtopptx four-SkillSet was not created during Build Week.
PPTX Generator pins and orchestrates it through a verified handoff and release
contract.

A superseded repo-local duplicate/legacy Skill surface was removed after
contract detachment and quarantine. The external canonical CAPTW/pngtopptx
four-SkillSet was retained, pinned, and verified.

## Actions reserved for an authorized Phase 8B

1. confirm the GitHub owner or organization, final name, visibility, remote
   URL, publication branch, and default branch;
2. decide whether a root repository license will be added before public
   visibility;
3. create or approve the remote without rewriting the local history;
4. push only the approved history and branch;
5. create the approved tag and GitHub Release, if authorized;
6. upload only the canonical ZIP and verify its remote hash or downloaded bytes;
7. replace the repository placeholder in the DevPost payload only after the
   public or judge-accessible URL exists.

Until those decisions are explicit:

```text
github_remote_authorized = false
push_authorized = false
tag_authorized = false
github_release_authorized = false
```
