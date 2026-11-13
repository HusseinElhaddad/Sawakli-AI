# ADR 0002 - AI pipeline and persistence boundaries

## Status

Prepared for affected-owner review, 23 October 2026. This is the concrete ARCH-03
decision package requested by Hussein Elhaddad. It is not a claim that another
person approved it, that the branch was published, or that the production pipeline exists.
The contract helpers and fixture checks are implemented; runtime adoption is AI-05/06/07
and WORK-04 work after review. No existing accepted ADR is superseded.

## Context

ARCH-03 requires tenant-scoped input and evaluation contracts, a run/output fixture,
cancellation, simulator/persistence ownership without a cycle, and named implementation deltas.
At baseline `4f71cf8`, AI-01 through AI-04 exist, but `ai/pipeline.py` is empty and the
Worker executor simulates an outcome. Historical API and Worker PDFs are explanatory
references; they do not prove implemented endpoints or execution.

## Decisions

1. Retain the modular monolith and direct in-process Worker-to-AI call. API inserts
   `jobs`; Worker owns job transitions. AI is not an HTTP service.
2. Worker allocates and stores one `model_run_id` on a claimed job before dispatch,
   reusing it for retries. AI-06 alone creates/finalizes the matching `model_runs`
   row and writes AI outputs. This resolves the old migration comment assigning
   Worker insertion in favor of the current AI-06 task's explicit ownership.
   Historical migrations are unchanged. Worker must not independently insert that row.
3. One request contains one organization, an optional nonempty campaign tuple and
   a fixed `as_of` date derived from the job's UTC creation date. Read all available
   authorized history through that date from `daily_metrics` joined to `campaigns`;
   engineer features in memory. No `feature_daily` cache or new job date column.
4. Pure AI-01 through AI-05 computation does not own persistence. AI-05 implements
   the three bounded scenarios and supplies a simulation batch correlated by
   organization/campaign/rule. AI-06 creates recommendation IDs and stores the batch.
   AI-05's stored-example gate is verified through that adapter; its computation
   can merge first, but its full persistence acceptance must not be falsely claimed.
5. Use whole-run atomic output publication for this bounded MVP. Expected missing
   history is a warning, not failure. An unexpected campaign/stage failure aborts
   publication. V1 returns SUCCESS, FAILED or CANCELLED, not PARTIAL_SUCCESS.
6. Preserve AI-02's campaign diagnostic and algorithm. Its result is not a database
   anomaly. Persist only critical diagnostics with explicitly supplied metric evidence;
   map to canonical high severity and metric above/below. Never parse reasons to
   guess a metric. Forecast placeholders with no value are omitted, never zero-filled.
7. Cancellation is cooperative. Claim transactions are short; compute without a
   job-row lock. Serialize cancellation and output publication on the same job row
   immediately before commit. A cancellation that wins that lock prevents publication;
   after successful publication commits, success wins and cancellation is too late.
8. Keep the current retry limit of three attempts. Serialize attempts per job; retries
   first inspect the existing model run. A committed successful run is returned without
   inserting outputs again. Arbitrary multi-worker stale-lease recovery is FUT-04,
   not a guarantee supplied by this contract.

## Consequences and authority

The companion [contract](../contracts/ai-pipeline-and-persistence.md) is the single
definition of the proposed integration boundary; the task document explains delivery.
No runtime roles, migrations, endpoints, thresholds or analytical formulas change here.
Affected-owner review is required before adoption. Reviewers: El-Farouk Omar (Worker),
Ahmed Ibrahem (API), Youssef Halawa (Data/database), Mohamed Hassan (shared contracts/QA),
and Abdulrahman Ehab (frontend/forecast consumer). Names identify requested review roles,
not recorded approvals or newly assigned tasks.
