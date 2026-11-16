# AI-07 — AI Security, Organization Isolation and Model Tests: Execution Plan

Prepared: 16 November 2026, Africa/Cairo. **Planning deliverable; implementation has not started in this session.**

Saved Notion plan: [Detailed execution plan and readiness assessment](https://app.notion.com/p/41a7de83a91b81c0ae8bd5bf5ee6674c).

Task: [AI-07 in Notion](https://app.notion.com/p/3bc7de83a91b819abef2d495bd4c051a). Owner: Hussein Elhaddad; independent AI/security acceptance reviewer: Mohamed Hassan, with database and Worker review for their affected boundaries. Existing task status In Progress, 4 base points, 8h estimate, start date 23 October and deadline 19 November 2026 at 23:59 Africa/Cairo are preserved. This plan does not change scoring, dates, assignments or prerequisite relations.

## 1. Outcome and readiness

Prove that the real AI-01 through AI-06 path reads authorized canonical facts, excludes sensitive data, leaves canonical inputs unchanged, and publishes correctly linked organization/run outputs. Make the original AI-package code-coverage target an enforced CI check. Reuse existing analytical tests and add security evidence where it is missing.

**Ready to begin:** source-boundary checks, tenant/identity tests, input immutability tests, coverage measurement and test-only role-fixture preparation. Production runtime-login rollout is not required to start these activities: accepted ADR 0001 explicitly permits the FU-09 test-login fallback.

**Conditional acceptance:** restricted-login tests must use the privileges actually installed by migrations. Existing role drift cannot be hidden with fixture-only grants/revokes. If full pipeline execution needs an upstream privilege/context change, demonstrate it, name the owner, and keep that acceptance slice open until the owning change lands or an explicit approved scope decision is recorded. Passing superuser tests does not prove database permission enforcement.

## 2. Verified repository snapshot

- Fetched current main and independently checked GitHub: `8590e23846801d16fe559809f6698a80a6af4b2f` (15 November supervisor-name correction). Re-fetch at implementation start.
- [AI-06 PR #35](https://github.com/HusseinElhaddad/Sawakli-AI/pull/35) is merged at `8c7dd678c808f0760285c39eed364887faed960c`. Its old Notion handoff and some contract lifecycle paragraphs still say draft/feature branch; those sentences are historical publication state, not evidence that code is absent. ADR 0002 still remains prepared for affected-owner review.
- DEV-02 PR #36 is merged through `207a503516b748b2813886aae414cd2cbbff6114`. Active code is under `apps/backend` and `apps/web`; obsolete root runtimes are gone. No open PRs were returned at this assessment snapshot.
- [Main CI run 43753608319](https://github.com/HusseinElhaddad/Sawakli-AI/actions/runs/43753608319) completed successfully at the exact SHA above. Backend: **485 passed, zero skipped**; Contracts, Frontend and Compose Integration passed. Documentation governance was skipped on this push event by its PR-only condition. This is baseline evidence, not an AI-07 result.
- Python 3.12; FastAPI, SQLAlchemy 2, PostgreSQL 18 CI services; existing pytest, Ruff and strict mypy. No coverage dependency, coverage configuration, coverage report or >=70% gate is currently declared in the backend manifest/workflow.
- Existing checkout was clean on `chore/dev-02-repository-cleanup`; only README differs from fetched main. It was inspected read-only. Do not implement AI-07 on that completed task's branch.

## 3. Prerequisites and handoff map

| Source / task | Observed state | Consequence for AI-07 |
|---|---|---|
| [AI-06](https://app.notion.com/p/3bc7de83a91b816ab854eafc14663119) | GitHub merged; Notion historical handoff still contains draft wording | Real callable, persistence and fixtures are usable. Do not infer approval history from merge or rewrite another task's status here. |
| [DATA-01](https://app.notion.com/p/3bc7de83a91b814fa5baf3765b9e4e64) | Notion Done/Historical; migrations create NOLOGIN permission bundles | Schema prerequisite exists. This does not mean runtime LOGIN identities or least privilege are deployed. |
| [ADR 0001](https://github.com/HusseinElhaddad/Sawakli-AI/blob/8590e23846801d16fe559809f6698a80a6af4b2f/docs/adr/0001-runtime-boundaries-and-database-roles.md) / [ARCH-01](https://app.notion.com/p/3e57de83a91b81f8a737c7ecd0fbf9f7) | ADR Accepted; ARCH-01 Done | Governs process identities, in-process limitations, role drift and FU-09 test fallback. Follow-ups remain deferred; no new rollout card was approved by that ADR. |
| [ARCH-03](https://app.notion.com/p/3e57de83a91b819b8dedc15885353d2e), ADR 0002, pipeline contract | Task Done; ADR prepared for review; typed/runtime implementation merged | Use current `PipelineRequest`, `PipelineOutcome`, cancellation and persistence contract. Do not promote ADR status. |
| [ARCH-05](https://app.notion.com/p/3e57de83a91b81a79d84d19d8aa8c32b), [WORK-04](https://app.notion.com/p/3bc7de83a91b81d99a37cb0126bb6000) | Architecture task Done; WORK-04 To Do; executor still simulates outcomes | Worker owns job transitions, reservation/dispatch, cancellation initiation and timeout reconciliation. AI-07 can test the real pipeline via existing fixture reservation; production Worker-to-AI acceptance remains WORK-04. No new AI-07→WORK-04 hard prerequisite is invented. |
| ADR 0001 FU-01/02/04/05/08/09 | Grant reconciliation, context setup and credentials remain separate concerns | Database owner coordinates successor grants; API owner owns request context/fail-closed configuration; Worker owner owns per-job context. Hussein/Mohamed own role-scoped test evidence. |
| [QA-05](https://app.notion.com/p/3bc7de83a91b81caba91ea9c04333398) | Backlog; consumes AI-07 | Deliver reusable tests, threat model, role matrix, actual coverage and precise residual risks; do not add a reverse dependency. |

AI-07's Completion Gates list AI-06 and DATA-01. Its legacy and directional relation fields differ; preserve both fields during this task rather than migrating the tracker schema. Use “Prerequisites” in new documentation and the actual task acceptance/entry contract when explaining readiness. Old task-body schedule windows differ from the current due-date property; keep history labeled, do not silently reschedule.

## 4. Reconcile the original AI report with current authority

Read the attached `Sawakli_AI_Layer_Design_Document.pdf` on the [historical AI-layer page](https://app.notion.com/p/3b97de83a91b8078b95ce21212b6e78a): sections 1.10, 6.1–6.4 and CI.1–CI.3. Its coverage requirement is **code coverage >=70% for `ai/`**. It is not predictive accuracy or a whole-backend threshold.

| Original requirement | Current interpretation / test obligation |
|---|---|
| S.1–S.4: separate AI read/write logins | ADR 0001 supersedes the per-module production-login architecture: API/Worker identities inherit bundles. Inspect actual `ai_layer_role`; create isolated test logins under FU-09. Do not introduce new production AI services/logins. |
| S.5–S.6: sensitive-table denial | Explicitly probe `users`, `oauth_connections`, `connector_tokens` and `raw_api_responses` using restricted connections. AI must not read these through its code path. Probe actual effective process privileges separately; shared Connector/Data privileges cannot establish a Python-module sandbox. |
| S.7 / ST.6–ST.7: reads cannot write facts | Loader executes SELECT-only canonical reads; analytical input transaction is READ ONLY. Restricted AI role cannot INSERT/UPDATE/DELETE canonical inputs. The same AI role legitimately writes AI outputs. Do not assert that it is universally read-only. |
| AS.1 / ST.1: required organization | Validate missing, null, malformed and foreign identities at typed request and loader boundaries, using current validation errors/safe outcome codes. Do not introduce an HTTP endpoint or replacement `SecurityError` API. |
| AS.2 / ST.2 / ST.5: campaign ownership and audit | Current pipeline contract rejects foreign/inconsistent selection with nonretryable `invalid_input`; it does not skip foreign campaigns and continue. Preserve that behavior. Do not create a run under a forged identity to satisfy an old `skipped_campaigns` example. |
| AS.3: immutable canonical input | SQL operation audit, immutable-object assertions and before/after database snapshots across success/failure/cancellation/replay. |
| AS.4: output INSERT-only | Four published output tables are inserted atomically. `model_runs` legitimately uses lifecycle UPDATEs; replay must not mutate successful outputs or human recommendation decisions. |
| AS.5 / CI.1: no secret/network access | Add narrowly scoped static checks and real-path query auditing; test the checker with forbidden/allowed examples. Mere imports of shared ORM metadata are not database reads. |
| AS.6: append-only model runs | Current canonical contract allows RUNNING finalization and eligible FAILED retry with stable run ID. Preserve the audit identity and required lifecycle; no blanket UPDATE prohibition, trigger or per-attempt table. |
| AS.7: credential handling | Use existing environment/configuration boundaries; exclude credentials from AI DTOs, outputs, evidence and logs. Environment variables are configuration transport, not proof of encryption at rest. Production secrets management is outside this task. |
| 1.10 / CI.2–CI.3 | Reuse real model/unit/integration suites; add security tests, measure the entire AI source package and enforce >=70% statement coverage in CI. |

These interpretations follow accepted ADR 0001 and the current [pipeline contract](https://github.com/HusseinElhaddad/Sawakli-AI/blob/8590e23846801d16fe559809f6698a80a6af4b2f/docs/contracts/ai-pipeline-and-persistence.md), not an unrecorded redesign. Escalate only genuinely unresolved changes to shared grants, contracts or architecture.

## 5. Current implementation and reusable evidence

| File / area | Existing behavior and reuse |
|---|---|
| `ai/contracts.py` | Frozen, strict request/outcome/evidence models; unknown fields rejected; safe error/warning codes. |
| `ai/features/loaders.py` | `DatabaseDataLoader` joins campaign and metric organization IDs, filters both tenants, parameterizes queries; CSV loader is local input support. |
| `ai/features/schemas.py`, `engineering.py` | Frozen metric/feature dataclasses; validation, calendar windows, missing values and deterministic features. |
| `ai/integration.py` | `validate_feature_scope`, `to_anomaly_signal`, `persistable_forecasts`, `job_status_for`. |
| `ai/pipeline.py` | `run_pipeline(request, *, cancellation)`; `_load` uses REPEATABLE READ/READ ONLY; computation releases the connection; `_publish` locks/rechecks jobs and atomically publishes. |
| `ai/persistence.py` | Registration/claim validation, model-run ownership, safe lifecycle finalization, exact terminal replay. One run-owner lookup is ID-only before the fully tenant-filtered read; audit this narrow identity check explicitly rather than confusing it with returning foreign run data. |
| `tests/unit/ai/` | Real feature, detector, benchmark, forecast/evaluation, recommendation, simulator and contract tests. |
| `tests/integration/ai/test_pipeline.py` | Existing tags/FKs, foreign job/run/campaign, malformed data, rollback, retry limits, cancellation, separate-session races, human decision replay, fixed cutoff and read-snapshot tests. Extend evidence instead of cloning this suite. |
| `tests/fixtures/ai06.py` | Real Data ingestion, Worker claim query and explicit test-only run reservation. Reuse without claiming production WORK-04 dispatch. |
| `scripts/ai02_benchmark.py`, `scripts/ai06_evidence.py` | Existing deterministic benchmark and actual stored/replayed synthetic run procedures. |

AI database loading currently consumes `campaigns` and `daily_metrics`; optional GA fields remain unavailable in database mode. Do not add `ga_events`, raw payload or credential reads just to satisfy an older table list. `ai/evaluation/__init__.py` is intentionally empty: existing evaluation is in the benchmark fixture and forecasting package, so do not create an unnecessary evaluation framework.

Proposed implementation files, to confirm after baseline coverage and role probes:

| Path | Proposed change |
|---|---|
| `scripts/check_ai_security.py` | Small AST-based source-boundary checker; no production runtime hook. |
| `apps/backend/tests/unit/test_ai_security_guard.py` | Checker positive/negative examples, including aliases and harmless metadata. |
| `apps/backend/tests/unit/ai/test_security_boundaries.py` | Missing scope, immutable inputs, cross-tenant adaptation and safe DTO/error cases not already covered. |
| `apps/backend/tests/fixtures/ai07.py` | Synthetic two-tenant fixtures, SQL observation, restricted test-login creation/cleanup and actual privilege inspection; admin/runtime connections remain separate. |
| `apps/backend/tests/integration/ai/test_security_isolation.py` | Real-path access audit, canonical snapshots, restricted-role/RLS controls and sanitized failure evidence. |
| Existing `tests/unit/ai/*`, `tests/integration/ai/test_pipeline.py` | Extend only demonstrated gaps; retain existing meaningful tests. |
| `apps/backend/pyproject.toml`, `.github/workflows/ci.yml` | Development-only coverage dependency/configuration, security/coverage checks and CI artifacts. |
| `docs/ai/AI-07-security-isolation-and-model-tests.md`, `docs/ai/plans/ai-security-execution.md`, `docs/README.md` | Technical evidence, maintained execution plan and index links. |

Production AI code changes are conditional on a demonstrated security defect. Keep `run_pipeline(request, *, cancellation)` stable and fix the owning boundary without changing analytical formulas. Grants/context changes outside AI require their owning task/review; no historical migration rewrite is authorized by this plan.

## 6. Security claims and limits

Prove four distinct claims and report each separately:

1. **Code boundary:** supported AI execution never queries sensitive tables or invokes provider/network operations, and never changes canonical facts or jobs.
2. **Application isolation:** requested organization/campaign/job/run ownership is checked; no other tenant contaminates computation, outputs, evidence or errors.
3. **Database enforcement:** actual restricted logins deny forbidden statements and enforce migrated RLS policies. Positive own-tenant controls must pass, so empty results cannot masquerade as isolation.
4. **Runtime deployment:** record current API/Worker superuser configuration and deferred rollout. A test login proves test-database enforcement only; no production enforcement claim follows.

AI and Connector/Data share a Worker process when invoked there. Arbitrary Python code in that process is not isolated by an SQL role, and may share process configuration. Static checks are guardrails, not a sandbox. Scope the evidence to supported AI paths and the privileges actually exercised. No new microservice, queue, ORM, secrets platform, model framework or runtime isolation mechanism is proposed.

## 7. Execution phases

### A. Refresh baseline and construct acceptance register

1. Inspect git status; preserve user work. Fetch main, recheck open PRs, record SHA and create `feat/ai-07-security-tests` from the appropriate current base.
2. Read root/backend/AI/docs AGENTS, README, CONTRIBUTING, documentation standard and 17-section template; re-read current contracts, migrations 0007–0013 and accepted ADR 0001. Verify ADR 0002 status.
3. Build the requirement-to-test register below, including existing tests and concrete uncovered branches. Capture baseline coverage before changing production logic.
4. Record actual role attributes, memberships, table/column privileges, RLS policies, schema ownership and effective login. Never print URLs/passwords or production secret values.

Exit: exact baseline, source-reconciliation matrix, missing-proof inventory and bounded edit list.

### B. Add source-boundary checks

1. Implement a small standard-library AST-based checker for AI source imports and direct sensitive-table references. Cover direct and aliased `requests`, `httpx`, provider clients, `urllib.request`/network paths, direct secret-model/repository use and obvious raw SQL references. Keep local CSV input supported.
2. Allow current SQLAlchemy, shared enums, Job identity metadata and session factory imports when justified by execution ownership. Importing a module that defines other models is not itself a SELECT on them. Avoid broad exemptions or brittle whole-file source snapshots.
3. Add positive and negative fixtures for aliases, from-imports, raw SQL/table symbols and harmless comments/metadata. Make deliberate violations fail CI. Document reflective/dynamic/transitive limits rather than claim complete static analysis.
4. During real pipeline execution, use test-local SQLAlchemy event/statement inspection to record statement kind and tables without binding values. Seed/migrate before attaching observers. Assert allowed reads and writes, and no secret/raw reads, canonical writes, jobs UPDATE, DDL or recommendation-status mutation. Use Core/ORM structure where possible; explicitly review the few raw SQL statements instead of building a SQL parser.

Exit: a checked boundary plus execution evidence, not a new database-access framework.

### C. Strengthen identity, isolation and input-immutability evidence

1. Seed two synthetic organizations with identical campaign names and distinct metric patterns. Exercise selected campaigns and all-campaign mode, alternating A/B/A and reordered inputs.
2. Cover null/missing organization, foreign job/run/campaign, inconsistent stored selection, mixed-tenant feature/evidence/baseline inputs, duplicates and cutoff leakage. Assert rejection before foreign outputs are read/returned, and no mutation to foreign rows.
3. Snapshot canonical rows, source metadata, jobs and existing human decisions before execution. Check exact values/identities after success, no-data/sparse-data, fault injection, cancellation and successful replay. AI lifecycle changes to `model_runs` are allowed; canonical facts and jobs are not.
4. Snapshot analytical Python inputs before/after real modules; test frozen DTO behavior and deterministic equivalent input ordering. Keep missing, zero and undefined-ratio semantics unchanged.
5. Assert tags on all five AI tables. `action_simulations` has no direct org/run fields: prove organization/run identity through its recommendation FK, and prove exactly three scenarios per published recommendation. Resolve anomaly FKs and campaign/rule correlations by actual keys.
6. Inject synthetic secret canaries into controlled failures and assert they do not appear in `PipelineOutcome`, stored errors, recommendation evidence, captured logs or exported reports. Do not log SQL bindings or real exceptions with credentials.

Exit: real module composition and persistence prove isolation/immutability; only focused faults are mocked.

### D. Prove migrated PostgreSQL privileges and RLS

1. Extend the existing integration harness with isolated test-login fixtures. Use an admin connection only for migrations/seeding/role setup/cleanup. Tests open separate real connections as uniquely named `LOGIN NOSUPERUSER NOBYPASSRLS` non-owner roles; assert those attributes and absence of privileged memberships. No production role changes.
2. First inherit the actual migrated `ai_layer_role` and test canonical reads, linked output INSERTs, denied users/OAuth/token/raw reads, denied canonical INSERT/UPDATE/DELETE, and denied recommendation status UPDATE. A separate read-only transaction proves loader write prevention without inventing a production `ai_layer_read` role.
3. Test RLS using own/foreign rows with organization A, B, missing and invalid transaction-local context. Include intentional raw statements without app filters to demonstrate RLS independently of application filtering. Own rows must be visible; foreign writes must be rejected. After commit/rollback and pooled reuse, context must not leak. Verify fail-closed behavior and SQLSTATE as appropriate; rollback each intentionally failed transaction.
4. Audit the actual Worker effective profile separately. `worker_role` currently grants `users` SELECT; do not inherit it and claim secret denial. AI-only grants also lack jobs access needed by registration's SELECT FOR UPDATE. Record the exact missing table/column/lock privileges before proposing a minimal successor migration to the database owner. Consider every transaction, including registration, read snapshot, publication and separate failure finalization, when evaluating organization context.
5. Full `run_pipeline` under a restricted execution profile is an acceptance target. Run it when the approved migrated profile/context supports it. A hypothetical fixture profile with convenient grants is exploratory evidence only. Do not silently revoke users/grant jobs in fixtures to manufacture a passing production-privilege claim. Keep independent AI-role/RLS tests moving while upstream deltas are reviewed.
6. Roles and role memberships are cluster-wide. Use a dedicated disposable PostgreSQL server for role tests or unique roles with coordinated cleanup; do not run role teardown concurrently with the separate migration round-trip. Dispose pools before DROP OWNED/role cleanup. Never modify a development or production server.

Exit: role matrix with actual PASS/FAIL/NOT RUN, positive controls and owner-linked residual grant/context gaps. A failing required privilege test is not skipped or relabeled success.

### E. Close meaningful model-test and coverage gaps

1. Reuse existing feature arithmetic, anomaly diagnostics/structured evidence, forecast backtests, recommendation rules/explanations and proportional simulator tests. Add tests only for uncovered behavior with a meaningful assertion.
2. Preserve `ai02-reference-v1`: seeds 20261015 and 20261016, 5,400 rows each; critical threshold >=0.80; event/day recall >=0.80 and clean-day/campaign false-positive rate <=0.05. Keep labels, digests, populations and denominators unchanged. Never tune formulas or thresholds to satisfy AI-07.
3. Forecast tests retain shared viable backtest targets, finite/missing behavior and deterministic models. Recommendation/simulation tests retain complete seven-calendar-day historical-repeat baselines, assumptions and scenario-specific unavailable-ratio markers. No new predictive-lift claim is made.
4. Propose **coverage.py as one development-only dependency**: pytest is already present; an additional pytest plugin is unnecessary. Record the reason and select a compatible bounded version under existing dependency policy at implementation. No runtime dependency is added.
5. Configure statement coverage for the complete `src/sawakli/ai` tree, including pipeline, persistence, integration and evaluation code. Include unexecuted source files; no handpicked modules, omit lists, new no-cover pragmas or fixture-only denominator. Report executable statements, misses and percentage per file and total; enforce total >=70 with `fail_under=70`. Branch coverage may be a separate diagnostic, not an invented replacement acceptance threshold.

Exit: meaningful tests and an actual reproducible >=70% AI-package coverage report. Coverage is not model accuracy or proof of all security properties.

### F. Integrate verification into existing CI

1. Add the security checker and negative tests to existing Backend verification; do not create a new service or duplicate parallel suite unnecessarily.
2. Run the full existing backend pytest suite once under coverage, retaining JUnit generation and the existing zero-skips check. Supply actual PostgreSQL role-creation capability through the disposable CI admin fixture; missing setup fails visibly.
3. Publish coverage XML/HTML and sanitized role/security result artifacts with explicit paths and retention. Reports, `.coverage`, JUnit, temporary credentials and exports stay out of Git. Ensure path ignores cover new generated files.
4. Preserve Ruff, strict mypy, contract validators/negative cases, frontend/build, Compose and migration round-trip gates. Do not loosen allowlists, introduce skips/xfails or weaken benchmark gates.
5. Check the exact final PR head. A green main snapshot or an earlier implementation head does not satisfy final-head verification.

### G. Document, review and hand off

1. Add `docs/ai/AI-07-security-isolation-and-model-tests.md` using the complete 17-section template. Section 5 is Step-by-Step Implementation Walkthrough. Include source reconciliation, claim boundaries, role matrix, acceptance mapping, commands/environment/SHA/results, coverage denominator, real PostgreSQL evidence and residual ownership.
2. Add this plan as `docs/ai/plans/ai-security-execution.md` in the implementation PR, reconcile it with actual execution, and link both from `docs/README.md`. Update a shared contract only if behavior changes; do not silently convert an ADR to Accepted or rewrite historical migrations.
3. Review the final diff for scope, secrets and generated artifacts. Publish a focused draft PR with exact verification. Obtain Mohamed's independent security/QA review and relevant database/Worker reviews; request reviews only when authorized to notify those people.
4. Update the existing AI-07 task with PR/docs, actual security results, coverage artifact and remaining gaps. Preserve scoring, dates and unrelated content. Do not mark Done until all applicable acceptance, review and merge gates are satisfied; do not merge automatically.
5. Hand QA-05 a reproducible command, fixture prerequisites, actual role profile, threats tested, coverage and limitations. WORK-04 owns later production dispatch/cancellation/timeout wiring; database rollout owners retain runtime enforcement.

## 8. Proposed file map

All additions below are proposed, not existing deliverables:

| Path | Planned purpose |
|---|---|
| `scripts/check_ai_security.py` | Small source-boundary checker callable in CI. |
| `apps/backend/tests/unit/ai/test_security_boundaries.py` | Checker negative/positive cases, strict identity and pure-module invariants; reuse existing tests where sufficient. |
| `apps/backend/tests/integration/ai/test_security_isolation.py` | Real execution SQL audit, two-tenant data preservation, secret-safe errors and linked output assertions. |
| `apps/backend/tests/integration/ai/test_role_permissions.py` | Actual restricted-login grants/RLS tests and effective-profile evidence. |
| `apps/backend/tests/fixtures/ai07_security.py` | Admin/restricted connection separation, synthetic fixtures and safe cleanup; reuse `ai06.py`. |
| Existing AI tests | Extend only identified gaps; do not duplicate the complete AI-06 suite. |
| `apps/backend/pyproject.toml` | Development-only coverage dependency and source/report settings. |
| `.github/workflows/ci.yml` | Existing test step measured under coverage, security check and sanitized artifacts. |
| `.gitignore` | Only if new report paths are not already ignored. |
| `docs/ai/AI-07-security-isolation-and-model-tests.md`, `docs/ai/plans/ai-security-execution.md`, `docs/README.md` | Technical evidence, execution plan and index. |
| AI source / successor migration | Only demonstrated defects within AI ownership; shared grant/context changes need affected-owner agreement and belong in the owning workstream. Historical migrations stay unchanged. |

## 9. Acceptance-to-test matrix

| Acceptance | Existing foundation | Required additional proof |
|---|---|---|
| No sensitive data access | Canonical loader and safe DTOs | Static negative cases; real execution SQL audit; restricted-login denial for users/OAuth/tokens/raw payloads; separately report Worker effective grants. |
| Canonical inputs immutable | READ ONLY snapshot; frozen records | Actual attempted write rejected inside input transaction; database before/after equality on both tenants across outcomes; role DML denial. |
| Missing/forged org rejected | Strict PipelineRequest, tenant joins, feature guard | Missing/null/malformed scope at exposed boundaries; mismatched stored identities; no foreign mutation or unsafe audit publication. |
| No cross-tenant contamination | AI-06 foreign-ID and loader tests | A/B/A, same names, all vs selected campaigns; model windows/fitting/evidence checked with clearly different populations. |
| All output tags/FKs valid | AI-06 real-chain test | Every table, simulation parent linkage, anomaly source identity, exact three scenarios, omissions and markers; no fabricated direct simulation tags. |
| Safe audit/failure handling | Safe codes and execution_metadata | Secret-canary failures; legitimate run lifecycle; no invented skipped-campaign field; no credential/SQL/trace leakage. |
| RLS proof | Migrated policies exist; tests currently use admin | Actual non-owner connections, own-tenant positive visibility, missing/invalid context, foreign reads/writes, commit/rollback/pool isolation. |
| Model reliability | Existing AI-01..06 suites and benchmark | Retain numerical gates; cover measured missing branches without behavior/threshold changes. |
| >=70% code coverage | No current instrumentation/gate | Whole-AI statement denominator, fresh data, XML/HTML report and CI failure below 70%; security tests independently mandatory. |
| Publication reliability preserved | AI-06 rollback/retry/race/replay tests | Re-run existing separate-session race, cancellation, post-commit replay and human-decision tests under the final changes. Use barriers/events, never timing sleeps. |

## 10. Reproducible verification procedure

Commands below are **planned**, not executed AI-07 results. Read current manifests at implementation time. Never print connection secrets. Use the declared Python environment and Node 24.

From repository root, point `DATABASE_URL` and `TEST_DATABASE_URL` at two explicitly disposable databases ending `_test`, then use the existing guard:

```bash
python scripts/integration_harness.py fresh-db DATABASE_URL TEST_DATABASE_URL
python scripts/check_ai_security.py
node scripts/run-contracts.mjs
```

The new security checker command becomes valid only after Phase B. Role tests must additionally verify the intended disposable server before creating roles; schema/database isolation alone does not isolate cluster-wide roles.

From `apps/backend`, after implementing the coverage configuration/dependency:

```bash
ruff check .
ruff format --check .
mypy src
python -m coverage erase
python -m coverage run -m pytest -rs --junitxml=/tmp/ai07-pytest.xml
python -m coverage report --show-missing --precision=2 --fail-under=70
python -m coverage xml -o /tmp/ai07-coverage.xml
python -m coverage html -d /tmp/ai07-htmlcov
python -c "import sys, xml.etree.ElementTree as ET; n=sum(int(s.get('skipped',0)) for s in ET.parse('/tmp/ai07-pytest.xml').getroot().iter('testsuite')); print(f'skipped tests: {n}'); sys.exit(bool(n))"
```

`[tool.coverage.run].source` must identify `src/sawakli/ai` so all reporting commands share the same scope. The source setting and `--fail-under` behavior are documented by [coverage.py execution](https://coverage.readthedocs.io/en/latest/commands/cmd_run.html) and [reporting](https://coverage.readthedocs.io/en/latest/commands/cmd_report.html). Avoid `--ignore-errors` or exclusions to inflate results.

Full regression includes the existing two-seed benchmark tests. For separate benchmark exports, from root with the backend environment on PATH:

```bash
PYTHONPATH=apps/backend/src:apps/backend python scripts/ai02_benchmark.py --seed 20261015 --export-dir /tmp/ai07-benchmark-20261015
PYTHONPATH=apps/backend/src:apps/backend python scripts/ai02_benchmark.py --seed 20261016 --export-dir /tmp/ai07-benchmark-20261016
```

Use `ROUNDTRIP_DATABASE_URL` on a separate disposable PostgreSQL server/database ending `_roundtrip`, then run `python scripts/integration_harness.py roundtrip` from root. Existing historical downgrade drops cluster-wide roles. Recreate the regression database before repeating the full suite: existing client fixtures delete seeded organizations.

Run frontend lint/type-check/test/build and the unchanged Compose build/migrate/health/API/web-to-API smoke route as regression CI gates. Use a dedicated Compose project; fixed container names can conflict with another running Sawakli stack. Do not stop/delete unrelated containers. Finish with documentation governance against actual PR base and head, `git diff --check`, and final diff/status review.

If infrastructure is unavailable, attempt the existing CI PostgreSQL/Compose route. Report NOT RUN with exact reason/commands for local unavailable checks; do not call required database acceptance complete without actual database evidence.

## 11. Evidence package

- Base/head SHA, branch, environment and exact commands; one result per check as PASS, FAIL or NOT RUN with reason.
- Requirement IDs S.5–S.7, AS.1–AS.7, ST.1–ST.7 mapped to current behavior and actual test node IDs. Do not imply outdated architecture was implemented literally.
- Per-file and total coverage statements/misses/percentage; coverage XML/HTML and JUnit uploaded as CI artifacts, not Git files.
- Restricted test role attributes, memberships, effective permissions and RLS own/foreign/no-context results; redact credentials and query bindings.
- Before/after canonical snapshots or reproducible comparison summary, SQL access classification, output-link checks, safe error/cancellation/replay results.
- Two-seed benchmark digests and numerators/denominators, unchanged gates and honest claims. Historical Nour anomaly-quality validation remains unavailable without original independent labels.
- Existing `scripts/ai06_evidence.py` can supply a fresh stored/replay example if needed; its current setup requires DATABASE_URL=TEST_DATABASE_URL on an explicit disposable DB and retains synthetic rows. Label its admin execution as persistence evidence, not restricted-login security proof.
- Exact-head CI link plus independent review outcome. No invented acceptance, runtime rollout or approval.

## 12. Effort and sequencing

Existing task estimate is 8h. Current inspection suggests **12–16 active hours** for the full security/role-fixture/coverage/documentation package, excluding shared runtime rollout and external review waiting. This is a planning estimate, not logged time or an authorized deadline change. Preserve the existing 4 base points and current estimate field until scheduling is reconciled by the owner.

| Work package | Working estimate |
|---|---|
| Refresh baseline and requirement/permission matrix | 1h |
| Static boundary checker and negative cases | 2h |
| SQL audit, tenant/immutability and error tests | 2.5h |
| Restricted-login/RLS fixtures and actual probes | 2h |
| Coverage gap closure and CI/artifacts | 1.5h |
| Full regression/evidence/documentation | 1.5h |
| Review preparation and bounded response allowance | 1.5h |
| Total working estimate | 12h, with up to 4h contingency |

Order: A → B/C → D → E → F → G. Independent source/coverage work continues while permission deltas are resolved. Readiness is not a guarantee of finishing by the existing deadline; shared grant work is an explicit scheduling risk.

## 13. Risks, decisions and exclusions

- **Role drift:** ai_layer_role has no jobs lock privileges; worker_role includes users read. Produce actual failure evidence. Database-owner-reviewed successor migration/profile is the resolution path, not ad hoc privilege repair inside fixtures.
- **Context lifecycle:** pipeline opens several independent transactions. A one-time SET on a caller session does not scope them. Do not claim role-scoped pipeline acceptance until context propagation is tested; production Worker context belongs to WORK-04/runtime rollout owners.
- **Shared-process privileges:** code guardrails cannot enforce module isolation against arbitrary code execution in a process with broader privileges. Report this accepted ADR limitation explicitly.
- **Old specifications:** original separate AI logins, append-only runs, feature_cache and skipped foreign campaigns are superseded/incompatible details. Current schema/contracts and accepted decisions govern; no recreated obsolete tables or APIs.
- **Coverage inflation:** require whole-AI denominator and meaningful assertion review; 70% total never excuses an untested security invariant.
- **Test setup damage:** guarded disposable names, unique roles, isolated servers and cleanup after pool disposal; never use development/production data.
- **Scope:** no new algorithms, model/benchmark tuning, provider actions, queue/services, runtime credential rollout, API/UI integration, distributed lease recovery, dependency-security sweep or DEV-02 cleanup. No schema change is assumed for AI-07 itself.
- **Approval record:** reviewers are proposed roles, not recorded approvals. ADR 0002's review status is preserved; no final security waiver is inferred from existing merged AI code.

## 14. Current verification status and final gates

**PASS — planning research:** task and prerequisite pages read; original AI PDF sections extracted; applicable instructions, current source/tests/contracts/migrations/CI inspected; main fetched and matched to GitHub; exact-main baseline CI observed. Initial sandboxed fetch failed DNS; the permitted network fetch succeeded. No repository implementation files were edited.

**NOT RUN — AI-07 implementation tests, coverage measurement, role probes, new CI:** this request prepares the plan. Existing main CI is explicitly baseline evidence only. No coverage percentage or new security PASS is claimed.

- [ ] Baseline refreshed at implementation start and requirement matrix agreed against current authority.
- [ ] Static checker and its negative cases pass; real AI SQL audit respects the declared boundary.
- [ ] Tenant, identity, tagging, FK, immutable-input and safe-error evidence passes.
- [ ] Actual migrated restricted-role/RLS tests pass with own-tenant positive controls; remaining effective-profile limits are resolved or explicitly accepted through the governing decision process.
- [ ] Entire AI package reaches >=70% statement coverage with an enforced CI gate and inspectable report.
- [ ] Existing model benchmark and backend/frontend/contracts/Compose/migration gates pass on the exact final head with zero backend skips.
- [ ] Complete 17-section task document, execution plan and docs index are reconciled with actual results.
- [ ] Independent review, required merge and Notion evidence update complete before task Done. No automatic merge.
