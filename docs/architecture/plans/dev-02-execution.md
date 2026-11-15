# DEV-02 — Repository Structure Audit and Legacy Cleanup: Execution Plan

Prepared 15 November 2026 (Africa/Cairo). Original preimplementation plan; execution results are recorded in the DEV-02 technical document.

Task: https://app.notion.com/p/4137de83a91b810c8acdc3a2586e1de1
Repository: https://github.com/HusseinElhaddad/Sawakli-AI
Assignee: Hussein Elhaddad. Base Points: 3. Remaining Effort: 10 active hours; plausible range 8–12 hours. Status remains To Do; no deadline or start/completion date is invented.

## 1. Verified baseline and authority

- Current main: `8c7dd678c808f0760285c39eed364887faed960c`, merging AI-06 PR #35. AI-06 is now on main; its pipeline, persistence, evidence scripts and tests are active code, not empty scaffolds.
- Current-main CI run 43749890626 is completed/success: https://github.com/HusseinElhaddad/Sawakli-AI/actions/runs/43749890626. No open pull requests were returned by the GitHub open-PR listing at assessment time. Recheck both before editing; unsubmitted branches are not covered by that observation.
- Compose and Dockerfiles build `apps/backend` and `apps/web`. API entry: `sawakli.api.main:app`. Worker entry: `python -m sawakli.worker`, implemented in `worker/__main__.py`; API and Worker share the backend image. Keep this modular monolith.
- Six legacy root trees contain 52 tracked files: agent 6, api 6, connector 6, database 9, ui 19, worker 6. The legacy UI includes a separate package/lockfile and default Next.js assets. This is an audit count, not blanket deletion approval.
- Current source/config searches found no active build/import reference to those legacy runtime trees. Root README and documentation governance still mention legacy paths. A complete pre-deletion reference sweep is required; a search alone does not prove an external consumer cannot exist.
- Other candidates: empty Makefile and infrastructure placeholders; empty backend api/dependencies.py next to real api/deps.py; api/v1/__init__.py; empty worker/main.py next to the actual __main__.py entry; redundant .gitkeep files in populated directories; two assert-True placeholder tests.
- Keep intentional package and typing markers, including __init__.py and py.typed. Empty ai/evaluation, db/repositories, shared/contracts, tests/e2e and future frontend feature directories need explicit retain/remove reasoning; no automatic deletion based on size.
- The root README's dated snapshot says AI-02 is unmerged, ai/pipeline.py is empty, simulations are scaffolds, TEST_DATABASE_URL is unset in CI and contract validators are unwired. These statements do not describe current main. Current CI has validators/negative cases, real integration DB setup, a zero-skips gate and a migration round-trip.
- Read README, CONTRIBUTING, root/nested AGENTS, docs/DOCUMENTATION_STANDARD.md, the 17-section task template, accepted ADR 0001 and current contracts. ADR 0001 FU-11 already names root-skeleton cleanup. The user's assignment makes Hussein the DEV-02 implementer; preserve the ADR's historical proposed-owner record. Request affected-owner review without claiming it has happened. ADR 0002 remains prepared for review; no lifecycle rewrite is part of cleanup.

## 2. Estimate and points rationale

The team's rubric uses effort, complexity, impact and review burden; points are not hours. Three contribution points reflect a bounded cross-layer cleanup with moderate regression risk and substantial documentation/verification, without new product algorithms or architectural redesign. For comparison, DEV-01 carries 5 points, QA-00 2 points/8 estimated hours and DOC-01 4 points/12 estimated hours. Those are calibration references, not a mathematical conversion.

| Work package | Active hours |
|---|---:|
| Refresh baseline, instructions and coordination | 0.5 |
| Inventory and dependency/reference audit | 2.0 |
| Minimal cleanup and necessary reference fixes | 1.5 |
| README/layout guide and technical documentation | 2.0 |
| Backend/frontend/contracts/Compose verification and bounded fixes | 2.0 |
| Diff review, PR, evidence and review-response allowance | 1.0 |
| Contingency for path/build issues | 1.0 |
| Total | 10.0 |

Elapsed time also depends on image builds, CI queues and reviewer availability. A normal 12-hour contribution week could accommodate the active estimate if capacity is available; this is not a scheduling commitment. Re-estimate if hidden consumers require an API/package migration, infrastructure is unavailable, or scope expands beyond structural cleanup.

## 3. Phase A — Establish the exact starting point

1. Inspect git status, preserve user changes, fetch main and record the actual SHA. Create a focused `chore/dev-02-repository-cleanup` branch from current main, using a separate worktree if needed. Do not reuse or modify AI-06 work as an unrelated change.
2. Re-read applicable instructions, manifests, Compose/CI/pre-commit scripts and ADRs at that SHA. Record Python >=3.12,<3.13 and Node 24 from existing sources; preserve dependency choices.
3. Recheck open PRs and ask affected owners only when a candidate path has a real unresolved consumer. Do not block the whole audit on a hypothetical branch. Existing assignment does not authorize silently moving another task's implementation.
4. Capture relevant baseline checks on dedicated test databases and the actual head. Existing green main CI is reference evidence, not DEV-02 test results.

Deliverable: exact base/branch, clean-worktree evidence, current entry-point map and baseline verification register.

## 4. Phase B — Produce a keep/remove/retain inventory

Create `docs/architecture/DEV-02-repository-structure-cleanup.md` from the complete current 17-section template, with section 5 after Architecture and before Inputs. Add an inventory appendix in that document or `docs/architecture/repository-layout.md`.

For every candidate record: tracked path/file count, current purpose, build/runtime/import/script/document consumers, owning task/affected owner, keep/remove/consolidate decision, evidence, risk and reversal method.

| Candidate | Planned treatment and decision rule |
|---|---|
| Root agent/api/connector/database/ui/worker | Remove only after confirming no active consumer and inspecting unique content; preserve useful unique material in the canonical location if genuinely needed. Legacy database SQL must be distinguished from immutable active Alembic history. |
| Backend api/dependencies.py | Remove if still empty and unreferenced; keep the implemented api/deps.py and its public names. No speculative renaming. |
| Backend api/v1 and worker/main.py | Check route registration, import paths, CLI references and task contracts; remove only confirmed abandoned placeholders. Never remove worker/__main__.py. |
| Empty Makefile/infrastructure placeholders | Remove or document as intentionally reserved; do not invent a new command framework or fill them with unrelated work. |
| Populated-directory .gitkeep files | Remove only redundant markers; keep a marker when an intentional empty directory must remain tracked. |
| Two assert-True placeholder tests | Identify explicitly as obsolete placeholders; remove if substantive suites cover the relevant paths. Explain the expected collection-count decrease; preserve all meaningful tests and gates. Do not add vacuous tests to restore a historical count. |
| __init__.py, py.typed and downstream-owned package placeholders | Retain by default; document their packaging/type/future-task purpose. Any removal needs affirmative evidence rather than an empty-file rule. |
| Real apps/web features, hooks, lib, services and types | Keep active files regardless of remaining .gitkeep markers; dashboard features and API/session helpers already exist. |
| Root tests/contracts and scripts | Keep validators, negative cases, fixtures, integration harness and real AI evidence scripts. Root tests is not an abandoned test tree. |

Use rg for code/path references; inspect configuration and Python/TypeScript import resolution where string searches are ambiguous. Separate active references, historical evidence links and intentionally future-facing references. Do not rewrite historical reports solely to erase old paths.

Exit gate: every proposed deletion has documented evidence and a reversible Git diff; unresolved candidates are retained with a reason and named follow-up.

## 5. Phase C — Implement the smallest justified cleanup

1. Delete only inventory-approved files in small logical groups; inspect each diff before proceeding.
2. Fix live imports, package discovery, Docker COPY/build contexts, scripts or links only if a confirmed cleanup affects them. Current apps paths already work; avoid unnecessary moves or configuration rewrites.
3. Keep governance coverage at least as strong as before. Removing obsolete path names is optional; never weaken the implementation/documentation trigger or exempt DEV-02 from its task document.
4. Preserve API routes, tenant isolation, AI formulas/thresholds/scores, Worker lifecycle, database schema and historical migration files. No Python/Node version or dependency/lockfile upgrade belongs here. Deleting the separate unused legacy UI lockfile is removal of an obsolete tree, not an upgrade to the active frontend lockfile.
5. Record any discovered security/dependency, runtime-role, Worker-dispatch or product gap as separately owned follow-up; do not absorb it to make an empty folder appear implemented.

Deliverable: focused structural diff, no unrelated feature changes, updated inventory decisions and clear expected test-count effects.

## 6. Phase D — Reconcile current documentation

1. Update root README overview/layout/runtime commands to current main. Distinguish merged module implementation from unfinished product wiring. AI-06 exists; production WORK-04 dispatch and some API/UI integrations remain separate work.
2. Correct current CI descriptions using the actual workflow: root contract validators plus negative cases, TEST_DATABASE_URL setup, zero-skips enforcement and PostgreSQL migration round-trip. Do not copy historical CI gaps as current facts.
3. Provide one maintained layout map covering apps/backend, apps/web, root scripts, root tests/contracts and docs. Explain actual API/Worker entry points and the retained query-only metadata/migration convention.
4. Update docs/README.md and CONTRIBUTING.md only where paths or guidance are affected. Keep shared behavior in canonical contracts; a structural cleanup should not change those contracts merely to simplify the diff.
5. Preserve dated historical evidence and ADR status. An ADR follow-up can be linked to its implementation evidence as a factual lifecycle note without rewriting the accepted decision or inventing approval.
6. Include acceptance-to-file/test mapping, actual commands/results, limitations and affected-owner review expectations in the 17-section technical document.

Deliverables: current README, maintained layout guide/inventory and DEV-02 technical document; no unsupported claims that all product features are integrated.

## 7. Phase E — Verify with the existing gates

Use the repository's declared toolchains. Prepare separate disposable PostgreSQL databases using scripts/integration_harness.py; fresh-db must target guarded *_test names and confirmed servers. Never run destructive setup on development/production. The existing client fixture deletes seeded organizations, so recreate the regression database before repeating a full suite. The full downgrade/upgrade harness requires a separate disposable PostgreSQL server because historical downgrade drops cluster-wide roles.

From the backend directory, with the correctly prepared DATABASE_URL and TEST_DATABASE_URL:

```bash
ruff check .
ruff format --check .
mypy src
pytest -rs --junitxml=/tmp/dev02-pytest-results.xml
```

Preserve the CI zero-skips check. Compare collection results with baseline, explaining any deliberate removal of the two assert-True placeholders. Do not weaken the AI benchmark, delete meaningful tests, loosen allowlists or introduce skips.

From the frontend directory:

```bash
npm ci
npm run lint
npm run type-check
npm test
npm run build
```

From repository root:

```bash
node scripts/run-contracts.mjs
python scripts/integration_harness.py roundtrip
bash .github/scripts/check-documentation-governance.sh <actual-PR-base-SHA> HEAD
git diff --check
```

Set ROUNDTRIP_DATABASE_URL before the roundtrip command as required by the existing harness. Use the backend Python environment on PATH for root contract extraction. Recheck retained API/Worker imports and deleted-path references.

For Compose, inspect `docker compose config`, build, start PostgreSQL, run migrations, start the stack with --wait, inspect health, then exercise host-to-API and Web-to-API `/health` requests. Use a dedicated Compose project/volumes; current fixed container_name values prevent parallel Sawakli stacks with the same names, so coordinate rather than removing unrelated containers. Use existing local env configuration without printing secrets. Container health proves infrastructure smoke behavior, not full Worker-to-AI dispatch.

Record every check as PASS, FAIL or NOT RUN with its exact reason. If a baseline issue appears, distinguish it from a cleanup regression; fix only bounded in-scope regressions and escalate/re-estimate genuine scope growth. No executed DEV-02 build/test result is claimed by this plan.

## 8. Phase F — Review, publish and accept

1. Review git status and the final diff for unrelated changes, source loss, accidental exports and secrets. Confirm active migration history and contract fixtures are preserved. Re-run only checks justified by subsequent changes.
2. Commit focused changes and push a draft PR. Include actual base/head, full deletion/retention inventory, paths updated, architecture unchanged, expected collection-count delta, verification evidence and limits.
3. Verify CI on the exact final head; a prior green main/PR run is not final-head evidence. Investigate failures without disabling gates. Do not merge automatically.
4. Request review from affected owners: API/backend, frontend, Worker/Compose and QA as relevant. El-Farouk is an affected reviewer for ADR FU-11/CI/Worker paths, not a newly assigned implementer. An independent reviewer is required; no acceptance is fabricated.
5. Attach PR, documents, command results and before/after inventory to the existing DEV-02 task. Mark Done only when implementation, evidence, affected-owner review and merge requirements are satisfied. Record actual completion time then, not during this planning update.

## 9. Acceptance checklist and exclusions

- Clear active entry points/layout and complete evidence-backed keep/remove inventory.
- Confirmed obsolete scaffolds removed; retained/future-task paths explicitly justified.
- No broken active import/build/script/document paths or loss of meaningful tests.
- Current README/CI guidance plus complete 17-section DEV-02 technical document.
- Applicable backend, frontend, contract, migration and Compose gates pass on the final head; infrastructure limits are stated truthfully.
- Affected-owner review and merged focused PR before task completion.

Excluded: dependency vulnerability remediation and lockfile policy changes; microservices/monorepo-framework/Clean Architecture migration; API/Worker/AI feature implementation; runtime DB roles/RLS; historical migration rewrites; sweeping formatting; rewriting old reports to make history appear current. Base points and effort must be reconsidered before adding these independent workstreams.
