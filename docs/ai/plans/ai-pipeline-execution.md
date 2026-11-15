# AI-06 execution plan

Prepared 14 November 2026 before implementation. Base: current remote main,
`25de23a064d9c315fed6b317221f5da939803380`. Branch: `feat/ai-06-pipeline`.

## Inventory and authority

AI-01 has a tenant-scoped DB loader and immutable facts/features. AI-02 computes
retrospective campaign-day diagnostics; its private statistical branches need a
shared calculation seam to expose direct-metric contributions without parsing reasons.
AI-03 emits point forecasts and explicit unavailable records. AI-04 emits pure
recommendations keyed by campaign/rule. Merged AI-05 exposes SimulationBaseline and
simulate_actions. pipeline.py is empty. Worker still simulates execution and holds
transactions in its scheduler; reservation, dispatch and recovery wiring belong to
WORK-04. Existing Core metadata is query-only, independent of migration metadata.

ADR 0001 is Accepted, with runtime role rollout deferred. ADR 0002 remains prepared
for affected-owner review. The explicit AI-06 instruction authorizes implementation
against the current integration contract; it does not fabricate ADR acceptance.

## Acceptance mapping and proposed files

| Acceptance | Deliverable |
|---|---|
| Real chain and one entry point | ai/pipeline.py; real AI-01..05 calls |
| Statistical evidence unchanged | anomaly/detector.py shared per-feature statistics; regression and benchmark |
| Tenant/run/FK ownership | ai/persistence.py; db/tables.py query handles; adversarial PostgreSQL tests |
| Atomic final status, replay/retry | job-row serialization, run metadata, fault/race/replay tests |
| Actual stored example | scripts/ai06_evidence.py, disposable PostgreSQL queries and replay |
| Durable handoff | 17-section task document, separate guide, two rendered PDFs, draft PR |

## Interfaces and execution order

Keep run_pipeline(request, *, cancellation) -> PipelineOutcome unchanged. Use
SessionLocal for a fresh Session per transaction; tests replace that factory, never
share sessions. Internal helpers isolate registration/loading, pure composition,
publication and failure finalization. No new framework or runtime dependency.

1. Lock scoped job briefly; verify organization existence, claimed state, reserved ID,
   stored selection, UTC job-created cutoff and attempt limit. Inspect run ownership.
2. Register RUNNING or return exact persisted terminal outcome. A FAILED restart needs
   a strictly later eligible Worker claim (increased retry_count and claimed_at).
3. Load owned campaigns/facts in one REPEATABLE READ read-only transaction. Materialize
   facts, close Session; engineer and scope-guard before downstream computation.
4. Between stages and campaigns check injected cancellation. Detect, expose actual
   metric evidence, adapt critical anomalies; only latest-day signals enrich cards.
5. Forecast with AI-03 and persistable_forecasts; preserve allowed negative ROAS.
6. Prepare approved baseline, call AI-04 and AI-05, allocate linked UUIDs by correlation.
7. Check cancellation immediately before publication; lock scoped job, revalidate,
   re-read SUCCESS under lock, insert every output and SUCCESS outcome atomically.
8. Record safe FAILED/CANCELLED in a separate short locked transaction on error. If
   that cannot reach storage, propagate. Never change jobs.status from AI.

## Identity, transactions and output mapping

Never use client identity as authorization. Compare all request fields with stored
job/run context, and selected campaigns against owned campaigns. Preserve explicit
tenant predicates on reads/writes. Canonical facts remain read-only. Compute outside
write transactions and row locks. Publication uses the same jobs row as Worker
cancellation. Job lock precedes run inspection consistently in registration, publish,
and failure finalization, so a losing attempt cannot overwrite committed success.

Anomalies: UTC observation midnight, separate insertion time, direct metric evidence
and campaign_day score_scope JSON. Forecasts: field mapping, no missing-to-zero fill.
Recommendations: original evidence array plus rule, baseline assumptions and per-scenario
undefined-ratio strings; pending status only on insert. Simulations: exactly three
per published card, recommendation FK from organization/campaign/rule key.

One successor migration adds nullable model_runs.execution_metadata JSONB: original
request, Worker claim identity, exact terminal outcome, and campaign-specific omissions.
Existing columns cannot preserve warning/replay semantics or distinguish a later retry
claim. Do not overload error_message or change campaigns_analyzed's array shape.
Historical runs without metadata cannot be safely replayed and are rejected unchanged.

## Baseline preparation: owner-approved MVP policy

Hussein approved in this chat on 14 November 2026: exactly as_of-6 through as_of,
inclusive, all seven distinct dates, same authorized campaign/organization. Repeat
aggregate spend/conversions/revenue into as_of+1..as_of+7; record source window and
historical-repeat assumption. Recorded zero days count; duplicates fail; never use
last seven observed rows or fill gaps. Missing windows omit that campaign's cards and
simulations, preserve independent forecasts/anomalies, warn insufficient_history and
store campaign/date omission details in run metadata. This is not validated prediction.

## Failure, replay and cancellation

Invalid handoffs are nonretryable; computation/storage failures have distinct safe codes.
Expected empty/sparse inputs succeed with warnings. CANCELLED is terminal. Successful
replay is read-only and preserves human decisions, IDs and row counts, including a
crash after publication before Worker completion. A cancellation callback may stop
only at cooperative checkpoints; a sklearn fit cannot be interrupted midway. Stored
job cancellation and publication serialize on one row. No partial success, distributed
exactly-once promise, stale-lease recovery, HTTP cancellation endpoint or Worker rewrite.

## Verification and publication order

Unit: hand-calculable evidence, baseline complete/gap/zero/duplicate/tenant/order cases;
unchanged detector outputs and both declared benchmark seeds. PostgreSQL: real chain,
FKs/tags/three scenarios/markers, no-data/sparse, foreign identities/selection/cutoff,
publication rollback, computation error, cancellation, deterministic separate-session
races using Events/Barriers, replay/human decision, failed retry, crash window and
concurrent publishers after an earlier check. Use existing guarded fresh-db and
roundtrip harnesses on isolated servers/databases only. Never destructive setup on dev.

Then backend regression, Ruff lint/format, strict mypy, root validators/negative cases,
migration roundtrip, whitespace, governance against actual PR base, Compose attempt
and exact-head CI. Record actual commands/results, including unavailable infrastructure.
Write both Markdown documents and index links, generate PDFs outside git, render every
page and inspect. Review diff/secrets/artifacts, commit/push focused branch, create draft
PR, inspect exact-head checks, update existing Notion task and AI-05 stored evidence.
Do not mark Done, ready or merge without required independent review/acceptance.

## Material limits and excluded work

Current Worker cannot yet dispatch the real pipeline; evidence uses a test-only valid
claim/reservation matching the contract, not a claim that WORK-04 is implemented.
Role rollout, GA permissions, API-05 serving, frontend mocks, DEV-02 dependency cleanup,
leases, immutable historical snapshots and arbitrary simulation requests are excluded.
Corrections to old facts can change failed retries; exact success replay is durable.
Affected owners still review the shared contract/schema adoption before merge.

## Execution evidence

The [technical document](../AI-06-pipeline-orchestrator.md#14-verification) records
executed PostgreSQL, rollback/race/replay, benchmark and regression results. The
[separate learning guide](../guides/ai-pipeline-implementation-explained.md) explains
the resulting implementation. Publication/review status is recorded in the task
document and draft PR; no planned check is treated as executed evidence.
