# AI-07 — Security, Organization Isolation and Model Tests

## 1. Overview

AI-07 adds inspectable security evidence and an enforced whole-AI statement-coverage gate.
Implementation is on a feature branch; database and final-head verification are pending.
No production runtime-role rollout is claimed.

## 2. Scope

In scope: source guard, real-path SQL audit, immutable canonical inputs, tenant tests,
restricted PostgreSQL LOGIN tests, safe failures and coverage reporting. Out of scope:
production credentials/grants rollout, Worker dispatch, analytical changes and new services.

## 3. Prerequisites

AI-06 is merged. DATA-01 supplied migrated NOLOGIN bundles. Accepted
[ADR 0001](../adr/0001-runtime-boundaries-and-database-roles.md) permits FU-09 test logins.
[ADR 0002](../adr/0002-ai-pipeline-and-persistence-boundaries.md) remains prepared for review.
The [execution plan](plans/ai-security-execution.md) reconciles original report requirements.

## 4. Architecture

The modular monolith is unchanged. Tests seed through Data as an administrator, then
observe real AI execution separately. Permission tests open a new connection as a generated
non-superuser login inheriting the actual migrated ai_layer_role. Fixtures never repair grants.

## 5. Step-by-Step Implementation Walkthrough

1. **Source boundary:** `scripts/check_ai_security.py` parses AI Python ASTs for explicit
   network/provider imports, sensitive symbols and simple SQL literals. Negative tests
   demonstrate violations; comments and legitimate shared metadata remain allowed.
2. **Application proof:** `test_security_isolation.py` runs real pipelines for A/B/A,
   compares canonical/job rows before and after, and classifies actual SQL without values.
   Existing AI-06 tests retain tags/FKs, three scenarios, races, retry and human decisions.
3. **Failure safety:** a synthetic exception canary must not enter outcomes, stored metadata
   or captured logs. The original error is replaced by the existing safe code.
4. **Database proof:** separate restricted connections test denied sensitive reads/canonical
   writes, positive canonical reads/output INSERTs, foreign-row rejection and context reset.
   The jobs-lock privilege gap is explicitly tested, not repaired inside fixtures.
5. **Coverage:** coverage.py is development-only. Existing full pytest runs under coverage,
   measuring every executable statement under `src/sawakli/ai`; CI fails below 70%.

| Acceptance | Evidence |
|---|---|
| Secret exclusion | Checker negative cases, actual SQL classification, permission probes |
| Canonical immutability | Frozen DTOs, database snapshot equality, denied DML |
| Tenant/tagging isolation | A/B/A plus existing real-chain AI-06 tags/FK suite |
| Safe errors | Synthetic failure-canary check |
| Database enforcement | Restricted login positive/negative RLS controls |
| >=70% AI statement coverage | Complete-package coverage configuration, CI report/artifact |

Expected behavior above is distinct from executed results in section 14.

## 6. Inputs

Existing `PipelineRequest` organization/job/run/campaign/cutoff identity is unchanged.
Strict models reject missing/null/malformed scope and unknown credential fields.
Restricted test connections require guarded TEST_DATABASE_URL naming a disposable `_test` DB.
Role-creation capability must be available only to the fixture's setup administrator.

## 7. Outputs

No application output schema changes. Test outputs are SQL operation classifications,
assertions, JUnit and coverage XML/HTML. SQL bindings and connection secrets are excluded.
Simulation organization/run scope remains transitive through recommendation_id, not invented columns.

## 8. Rules and Semantics

Original report >=70% means AI code coverage, not predictive accuracy. The measured source
includes pipeline/persistence/integration and unexecuted modules. No omit list or no-cover
pragma is introduced. Existing benchmark seeds, thresholds and formulas remain unchanged.
The current [pipeline contract](../contracts/ai-pipeline-and-persistence.md) governs model-run
UPDATEs and rejection of foreign campaigns; old append-only/skip examples are not reinstated.

## 9. Public Interfaces

`python scripts/check_ai_security.py` exits nonzero on explicit violations.
`inspect_source(source)` returns line/rule pairs for focused checker tests.
`run_pipeline(request, *, cancellation)` and all analytical public interfaces are unchanged.

## 10. Data Ownership

AI reads canonical facts and owns model_runs/output persistence. Data retains canonical
writes; Worker retains jobs transitions. The SQL audit permits AI INSERTs and model-run
lifecycle updates, but no jobs/canonical writes. Fixtures seed/clean using a separate admin.

## 11. Security

The AST checker and runtime observations are bounded guardrails, not a Python sandbox or
complete SQL parser. Dynamic/reflective access and arbitrary compromised shared-process code
are not prevented by these tests. Production API/Worker superuser configuration remains a
known ADR limitation. A migrated AI-only bundle is not a complete Worker execution profile:
worker_role grants users read; ai_layer_role lacks jobs access. No production denial claim
is inferred from passing test-login probes. Test roles are unique and dropped after pool disposal.

## 12. Error and Edge-Case Behavior

Denied SQL statements assert PostgreSQL SQLSTATE 42501. Missing/invalid org context must
fail closed, with positive own-tenant visibility proving tests are not vacuous. Connection
reuse after commit/rollback must not retain org context. Required infrastructure failures
fail visibly rather than skipping. Safe computation failures preserve canonical input rows.

## 13. Testing

New source-guard cases cover aliases, provider/network imports, user models, table symbols,
SQL literals and legitimate imports. New strict-request/frozen-record checks complement
existing tests. Integration tests exercise real algorithms and migrated PostgreSQL privileges;
only computation failure is fault-injected. Full existing suites retain deterministic races.

## 14. Verification

Base: `8590e23846801d16fe559809f6698a80a6af4b2f`. Python 3.12 isolated environment.

- PASS: 23 new focused unit checks; source checker reports zero violations.
- PASS: strict mypy, 100 source files.
- Pending: full backend tests/coverage, Ruff final checks, contracts and final-head CI.
- NOT RUN locally: PostgreSQL and Compose. Docker socket inaccessible in sandbox; outside
  sandbox Docker reports no daemon/socket. sudo is unavailable under no-new-privileges.
  Existing CI PostgreSQL18/Compose route is the integration verification path.

Commands (backend): `ruff check .`, `ruff format --check .`, `mypy src`,
`python -m coverage run -m pytest -rs --junitxml=pytest-results.xml`,
`python -m coverage report`, `python -m coverage xml -o coverage/ai.xml`,
`python -m coverage html -d coverage/html`. Root: `node scripts/run-contracts.mjs`,
`python scripts/check_ai_security.py`, documentation governance against actual base/head,
`git diff --check`. Actual final results belong in the PR/Notion evidence handoff.

## 15. Known Limitations

Owner decision, 16 November 2026: keep AI-07 scope and retain the explicit acceptance gap;
shared grants/production context are not added to this PR.
Full pipeline execution under a restricted process profile is not established. The
permission-gap test documents current migrated behavior; its success is not full task acceptance.
A one-time SET on a caller session cannot scope pipeline transactions. Production context/grant
changes need the database/Worker owners. No independent historical Nour quality labels exist.

## 16. Follow-Up Tasks

Database owner: reconcile jobs-lock grants and Worker users over-grant through reviewed successor
changes. WORK-04: per-job/per-transaction context and production dispatch. QA-05: independent
integrated security acceptance. Keep AI-07 open until required permission evidence and review
are satisfied or a scope decision is explicitly recorded under the governing authority.

## 17. References and Evidence

[Detailed plan](plans/ai-security-execution.md),
[Notion AI-07](https://app.notion.com/p/3bc7de83a91b819abef2d495bd4c051a),
[AI-06 technical evidence](AI-06-pipeline-orchestrator.md),
[coverage.py reporting](https://coverage.readthedocs.io/en/latest/commands/cmd_report.html).
