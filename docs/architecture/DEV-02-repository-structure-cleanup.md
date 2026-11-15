# DEV-02 — Repository Structure Audit and Legacy Cleanup

## 1. Overview

DEV-02 removes abandoned runtime prototypes and clarifies the active modular-monolith layout. Audit base: main 8c7dd678c808f0760285c39eed364887faed960c. Implementation is on chore/dev-02-repository-cleanup; independent review and merge remain required.

## 2. Scope

Remove 52 legacy-root files and 17 redundant placeholders/markers; update current README and layout guidance. Exclude dependency upgrades, runtime-role rollout, unfinished feature implementation and architecture redesign.

## 3. Prerequisites

Read root/backend/frontend/docs AGENTS, README, CONTRIBUTING, documentation standard/template, manifests, Compose, CI, imports and ADRs. [ADR 0001](../adr/0001-runtime-boundaries-and-database-roles.md) is Accepted and records FU-11; ADR 0002 remains prepared for review. Current Notion owner assignment supersedes suggested implementation ownership without rewriting ADR history.

## 4. Architecture

Next.js Web, FastAPI API, Python Worker and PostgreSQL remain the runtime services. API and Worker share apps/backend; internal AI/Connector/Data modules are not separate services. [Layout/inventory](repository-layout.md) identifies actual entry points, retention decisions and every deletion. No active package relocation or changed public interface was needed.

## 5. Step-by-Step Implementation Walkthrough

### Practical outcome

Developers use one active source/build tree and current setup instructions, rather than competing prototypes.

| Acceptance | Implementation | Verification |
|---|---|---|
| Evidence-backed audit | Layout inventory and removed manifest | Entry-point/import/config searches and full diff review |
| Obsolete scaffolds removed | 69 selected tracked deletions | Git deletion manifest; no runtime consumers found |
| Intentional placeholders retained | Package/type/future-task retention table | Import/type/collection checks and CI |
| Current paths/docs | README, docs index and layout guide | Local link resolution and documentation governance |
| Working stack | Existing unmodified CI gates | Exact-head results recorded in PR/handoff |

### Step 1 — Inspect consumers before deletion

**What:** distinguish obsolete prototypes from real extension points. **Where:** Compose, Dockerfiles, manifests, CI, scripts and source imports. **How:** source/config search plus content inspection identifies health-only root services, default UI starter and prototype SQL; no unique feature needs migration. **Testing:** record entry points and compare manifest against Git diff.

### Step 2 — Remove only justified paths

**What:** remove six unused root trees, empty duplicate deps/v1/worker files, no-op command scaffolds, redundant markers and two vacuous tests. **Where:** exact inventory appendix. **How:** use tracked git rm operations; preserve all active __init__.py/type markers and Alembic files. **Testing:** collection changes by exactly two; meaningful tests and validators remain.

### Step 3 — Explain the current repository

**What:** replace stale current-state claims with source-backed guidance. **Where:** README and layout guide. **How:** distinguish implemented AI-06 from pending WORK-04 dispatch, real API paths from mocked AI-output services, and actual CI gates from historical gaps. **Testing:** validate documentation paths and governance; retain historical ADR/report statements.

### Step 4 — Verify and hand off

**What:** prove structural cleanup does not alter runtime behavior. **Where:** existing backend/frontend/contracts/Compose CI and technical evidence. **How:** run applicable checks, inspect final diff and publish draft PR. **Testing:** exact-head CI; no gate changes or fabricated human review. [Preimplementation plan](plans/dev-02-execution.md) remains the execution appendix.

## 6. Inputs

Tracked files and current source/configuration at the recorded base; current Notion task and accepted ADR boundaries. No customer data, tokens or production database inputs are required for the audit.

## 7. Outputs

69 deleted tracked files, maintained README, [layout/decision manifest](repository-layout.md), documentation index links and this 17-section technical document. No schema, REST or analytical output shape changes.

## 8. Rules and Semantics

Empty files are not universally obsolete. Keep __init__.py, py.typed, future feature/package homes and active tests/contracts. Remove two assert-True placeholders because they assert no product behavior; expected test collection changes from 487 to 485. This is not permission to remove valid tests or weaken benchmark/skip/contract gates. Preserve ADR lifecycle and dated evidence.

## 9. Public Interfaces

Unchanged: uvicorn sawakli.api.main:app; python -m sawakli.worker; Next.js npm scripts; ai.pipeline.run_pipeline. Removed root apps were not part of these active entry points. No compatibility shim is needed for a repository-internal consumer; external unsubmitted work remains a review limitation.

## 10. Data Ownership

Reads: source/configuration and synthetic/disposable verification data only. Writes: audited repository paths and documentation. Must never read: real credentials, provider payloads or customer facts for this task. Must never write: production/development facts, Worker state, AI output formulas or applied migrations. The removed database/db prototype SQL was never active Alembic history.

## 11. Security

Tenant checks, secrets handling and runtime permissions are unchanged. No dependency remediation is claimed. Verification logs/exports remain outside git; no real env contents are included. Runtime logins/RLS remain separately owned under ADR 0001.

## 12. Error and Edge-Case Behavior

Unresolved path consumer: retain and document rather than delete speculatively. Broken reference caused by cleanup: fix the reference or restore selected files from the base. Existing unrelated failure: identify baseline versus regression and keep separate scope. Missing Docker/database access: use existing CI route and report local NOT RUN. No destructive test setup against non-test databases.

## 13. Testing

No new tests mirror file deletion. Existing meaningful suites and negative contract cases remain unchanged. Removed unit/test_placeholder.py and integration/test_placeholder.py each contained only assert True. Compare baseline/post-change collection; run Ruff, formatting, strict mypy, unit/backend regression, frontend lint/type/test/build, root validators, migration round-trip and Compose smoke via available local/CI routes.

## 14. Verification

Executed locally on 15 November 2026 using CPython 3.12.3, Node 24.22.3 and unchanged dependency manifests. Backend tools were installed in /tmp/dev02-venv; frontend used npm ci from the existing lockfile. No runtime dependency update is part of this change.

| Check | Result |
|---|---|
| Ruff lint / format | PASS - 182 files formatted |
| Strict mypy src | PASS - 100 source files |
| Baseline/post-cleanup collection | PASS - 487 / 485, exactly two assert-True placeholders removed |
| Frontend npm ci, lint, type-check, test, build | PASS - 83 tests in 13 files; lint has one existing unused-argument warning, zero errors |
| Root contracts and negative cases | PASS - all six commands; deviation allowlist unchanged |
| Changed document links and removed manifest | PASS - every one of 69 removed paths documented |
| Whitespace | PASS - git diff --check |
| Local PostgreSQL/round-trip/Compose | NOT RUN — daemon access denied and sudo requires interactive authentication; unchanged CI services execute these gates on the PR head |

Backend unit execution and exact-head full CI results are recorded in the PR and Notion handoff after completion. Previous green main CI is baseline reference only, never substituted for DEV-02 verification.

```bash
# apps/backend
ruff check .
ruff format --check .
mypy src
pytest --collect-only -q
pytest tests/unit -q
# apps/web
npm ci
npm run lint
npm run type-check
npm test
npm run build
# root with backend Python on PATH
node scripts/run-contracts.mjs
bash .github/scripts/check-documentation-governance.sh 8c7dd678c808f0760285c39eed364887faed960c HEAD
git diff --check
```

Local Docker attempt: NOT RUN — daemon socket permission denied; sudo -n requires interactive authentication. PostgreSQL/full migration/Compose execution is delegated to the unchanged CI services for the actual PR head; final results belong to the PR/handoff. No local PostgreSQL success is claimed.

## 15. Known Limitations

A static reference audit cannot prove absence of unpublished external branch consumers. Historical reports intentionally retain legacy paths. Worker real dispatch and some AI-output UI services remain incomplete by their own task scope. Removing prototype dependencies is not remediation of the active dependency tree. Review and merge acceptance remain open.

## 16. Follow-Up Tasks

Affected API/frontend/Worker/QA owners: independent review of structural cleanup and documentation. WORK-04/API-05/AI-07 retain existing delivery scope. Dependency/security and runtime-role changes require separate focused tasks. No new assignment or approval event is invented.

## 17. References and Evidence

- [Notion DEV-02](https://app.notion.com/p/4137de83a91b810c8acdc3a2586e1de1)
- [Execution plan](plans/dev-02-execution.md)
- [Layout/inventory](repository-layout.md)
- [Documentation standard](../DOCUMENTATION_STANDARD.md)
- [ADR 0001](../adr/0001-runtime-boundaries-and-database-roles.md)
- PR and exact-head CI: recorded in the published handoff; no preceding-head run substitutes for it.
