# AI pipeline and persistence contract - v1

**Lifecycle:** concrete contract prepared for affected-owner review under ARCH-03.
Typed contracts, pure boundary adapters and fixture validation are implemented in this
change. Production execution/persistence remains the named downstream tasks. See
[ADR 0002](../adr/0002-ai-pipeline-and-persistence-boundaries.md) for decisions and alternatives.

## 1. Ownership and current endpoints

| Concern | Sole implementation owner |
|---|---|
| Authenticate and enqueue jobs | API-04; API owns initial jobs insert |
| Claim, retry, timeout and update jobs | Worker / WORK-04 |
| Create and finalize model_runs | AI-06 |
| Compute features, anomalies, forecasts, recommendations, simulations | AI-01 through AI-05 |
| Insert forecasts, anomalies, recommendations, action_simulations | AI-06 |
| Update recommendations.status for a human decision | API; never overwritten by an AI retry |
| Canonical input writes | Data; AI is read-only |
| Serve stored outputs | API-05 |

Current trigger: `POST /api/analysis/refresh`; polling: `GET /api/jobs/{job_id}/status`.
`jobs` is the queue; `model_runs` is the AI audit. Neither current response exposes
`model_run_id`. The PDF's `/api/v1/.../analysis-runs` and queued/done statuses are not
new endpoints/enums. Preserve canonical uppercase statuses at API/Worker boundaries;
UI may translate them to labels. No cancellation HTTP endpoint is implemented here.

## 2. Worker-to-AI input

`sawakli.ai.contracts.PipelineRequest` is frozen and rejects unknown fields.

| Field | Type | Rule |
|---|---|---|
| organization_id | UUID | Trusted authenticated organization copied from claimed job |
| job_id | UUID | Existing job in that organization |
| model_run_id | UUID | Worker allocates once, stores on job in short claim transaction; retry reuses it |
| campaign_ids | tuple[UUID, ...] or None | None = all owned campaigns; reject empty/duplicate selection |
| as_of | date | Job.created_at converted to UTC, then date; identical on retry |
| contract_version | literal ai-pipeline-v1 | Reject unknown versions |

Worker verifies all three identities against the database before dispatch. AI-06
rechecks the job organization and run linkage before publishing. A client cannot choose
an organization or run ID through this internal interface.

Use AI-01 `DatabaseDataLoader.load_metrics(organization_id, campaign_ids, date_to=as_of)`.
Read all available prior history; do not use the UI reporting range as training history.
This intentionally avoids inventing a job date-range column. Optional GA values remain
None in database mode. Input loading uses a consistent database read transaction,
then materializes immutable records and releases the read transaction before computation.
`validate_feature_scope` rejects foreign tenants, unrequested campaigns, future dates,
and duplicate campaign/day keys even when a buggy loader supplies them.

An empty workspace is SUCCESS with `no_data` and zero output rows. A campaign with
insufficient history is not relabeled normal business performance. Its unavailable
forecast is skipped and `insufficient_history` is included in the outcome warnings.
AI-02's original insufficient-history diagnostic remains unchanged.

## 3. Computation and public execution signature

Future AI-06 implements:

```python
def run_pipeline(request: PipelineRequest, *, cancellation: CancellationCheck) -> PipelineOutcome:
    ...
```

This callable is specified, not implemented by ARCH-03. Dependencies use the existing
DataLoader and SQLAlchemy Session conventions; do not create another DB/session framework.
Load -> engineer -> detect and forecast -> adapt -> recommend -> simulate -> publish.
All randomness uses existing fixed module seeds. Freeze one input batch for the attempt.
Anomaly fitting remains retrospective within history up to as_of; this is not online inference.

`PipelineOutcome` contains the same organization/job/run IDs, terminal status,
successful campaign IDs, warning codes, safe error code and retryable flag. It excludes
credentials, SQL, provider bodies and exception traces. FAILED requires an error code;
CANCELLED requires `cancelled`; only FAILED may be retryable. SUCCESS may have warnings.
The Worker must validate returned identities before translating its status onto jobs.

## 4. Canonical output mapping

Existing DB fields/enums remain defined by `tests/contracts/canonical.json` and applied
migrations. This contract defines the conversion, not a second set of table definitions.

### Anomalies

AI-02 AnomalyResult is a campaign-day diagnostic with business-performance direction.
It cannot be directly inserted or passed to AI-04. V1 publication threshold is **0.80**
(critical only); lower severities stay diagnostics. This bounded policy reuses the
declared benchmark operating point, not a claim about real-world alert accuracy.

`MetricEvidence` supplies explicit organization/campaign/date, one direct metric
(`spend`, `ctr`, `cpc`, `cpa`, `roas`), current and earlier-history median values,
nonmissing earlier count >=5, and existing feature Z/IQR contributions. Values must
be finite/nonnegative and at least one contribution must be positive. AI-06 must expose
this structured evidence from the existing AI-02 statistical calculation (same floors,
history and formulas); it must not infer it from reason strings or calculate a different
detector. Exposing evidence is an AI-06 integration delta, not a new model-quality claim.

`to_anomaly_signal` checks diagnostic/evidence identity and date, score, evidence and
direction. For each changed evidence metric on a critical diagnostic, it yields an
AI-04 AnomalySignal: same organization/campaign, explicit metric_name, current > median
means above (otherwise below), severity high, same campaign ensemble score and a
preallocated anomaly UUID. Equal values and subcritical diagnostics yield no signal.
The copied score is campaign-level evidence, not an independently scored metric.

AI-06 stores one anomaly per run/campaign/observation-day/metric, with UTC midnight of
the observation date in detected_at. created_at is insertion time. Store observed date,
baseline, current value, contributions and `score_scope: campaign_day` in
detectors_triggered JSON. For AI-04, supply only signals for each campaign's latest
available feature date; historical diagnostics must not enrich a current recommendation.
Do not map performance up/down to metric above/below. IDs may be allocated before the
publication transaction, so source_anomaly_id is valid when recommendations are built.

### Forecasts

`persistable_forecasts` excludes ModelUsed.INSUFFICIENT_HISTORY records and rejects
unexpected missing/nonfinite values in otherwise usable forecasts. It never changes
an unavailable value to zero. Valid records map field-for-field to forecasts; omit
in-memory horizon_days/generated_from_date and add DB identity/run/timestamps.
Skipped rows are visible through PipelineOutcome warnings; API-05 must serve explicit
no-forecast/insufficient-data states rather than imply a zero projection. A negative
ROAS projection allowed by existing AI-03 is not silently clamped by this adapter.

### Recommendations and simulations

AI-04 output stays pure. Correlation key is organization_id + campaign_id + rule_id
within one model_run_id. Never correlate by list position or a name. AI-06 assigns
recommendation IDs, defaults new status to pending and stores rule_id plus simulator
assumptions/undefined-ratio markers in evidence. Preserve existing evidence strings;
additional traceability is appended as explicit strings, retaining the JSON array shape.
No AI retry updates an existing human status.

AI-05 returns a SimulationBatch with exactly these scenarios per key:
budget_decrease_20, budget_increase_15, pause. Every projection is finite/nonnegative;
scenario math is AI-05 work. Horizon and units are explicit: **a seven-calendar-day total
from as_of+1 through as_of+7**, same currency as canonical input. No currency conversion
is implied. Pause projects spend/conversions zero. For undefined CPA/ROAS (zero relevant
denominator), store numeric 0 only as the existing NOT NULL schema's **unavailable-value
sentinel**, declare the metric in undefined_ratios, and preserve that marker in the parent
recommendation evidence. API-05 must expose it as unavailable, not measured zero.
No non-pause zero-denominator prediction may omit the corresponding marker. AI-05's
formula tests must supply projected revenue when checking ROAS semantics; the current
simulation table itself has no projected_revenue column.

AI-05 owns scenario calculation and tests. AI-06 owns all simulation INSERTs and
recommendation FK resolution. AI-05's pure module can be built first; its stored-example
acceptance is demonstrated when AI-06's adapter is available, without making its module
depend on the orchestrator. FUT-05 arbitrary simulation requests remain out of scope.

The AI-05 [action simulation contract](action-simulation.md) defines the explicit seven-day
baseline input, proportional-v1 arithmetic, validation and deterministic public callable.

## 5. Transactions, retry and cancellation

The Worker control boundary is `request_job_cancellation(organization_id, job_id)
-> JobStatus`: an authorized in-process Worker control action locks that tenant's job,
returns its completed status if publication already won, otherwise marks an eligible
PENDING/RUNNING job CANCELLED. It supplies the cancellation signal observed by AI.
There is no new API-to-Worker network call or human-facing cancellation route in v1.
An AI-facing cancellation facade, if used for ARCH-05, delegates to this injected
Worker-owned action; it must not make AI another writer of jobs or import Worker code.
Real control wiring belongs to WORK-04; the boolean CancellationCheck is implemented
here as the typed observation boundary, not as a working cancellation command.

| model_runs transition | Rule |
|---|---|
| Absent -> RUNNING | AI-06 creates the reserved ID after checking the job |
| RUNNING -> SUCCESS / FAILED / CANCELLED | Finalize publication, failure or cancellation |
| FAILED -> RUNNING | Only an eligible Worker retry claim; keep started_at, clear completed_at/error_message and reset campaigns_analyzed |
| SUCCESS -> SUCCESS | Read-only replay; never insert output again |
| CANCELLED | Terminal; no retry |

FAILED retry attempts reuse the logical run row; the existing job retry_count records
attempt count. A separate immutable per-attempt audit table is not introduced by v1.

1. Worker claims job and reserves model_run_id, then commits quickly. Existing column is
   nullable until reservation; its unique constraint prevents sharing one run across jobs.
2. AI-06 creates or inspects model_runs under that ID in a short transaction. Existing
   organization mismatch is fatal. An existing SUCCESS result is replayed without new writes.
3. Compute without holding the job-row lock or a long write transaction. CancellationCheck
   is a no-argument callable returning bool. Check before/after stages, between campaigns,
   and immediately before publication. It reads committed cancellation through a fresh,
   tenant-scoped transaction; it does not share a mutable Session across threads.
4. Publish all output rows and finalize model_runs=SUCCESS in **one transaction**, after
   locking the same jobs row used by cancellation, checking organization/run linkage,
   RUNNING state and cancellation again. Under that lock, re-read model_runs: an already
   committed SUCCESS must return the stored outcome rather than insert again, even if
   both callers passed an earlier pre-computation check. Abort if ownership/state no longer matches.
   No output is visible from a failed or cancelled attempt. This lock is held only for
   publication, not model fitting. AI reads/locks jobs but does not update jobs.status.
5. Worker validates PipelineOutcome IDs and updates jobs. A crash after output commit but
   before that update is recovered by replaying the committed model run. Worker timeout
   recovery must check committed success before declaring failure or starting another fit.
6. Unexpected computation failure rolls back publication, records model_runs=FAILED in
   a separate short transaction when DB is available, and returns FAILED. Retryable
   infrastructure errors enter the existing retry/backoff policy. No-data/insufficient
   history are SUCCESS with warnings; malformed input is not retryable. If the database
   is unavailable even for failure recording, propagate the error to Worker recovery;
   never fabricate a saved failure record.
7. Cancellation that locks first wins; a completed publication that commits first wins.
   A cancellation request after that commit returns the completed outcome. CANCELLED
   is not retried. A scikit-learn fit may finish before the next cooperative checkpoint.

V1 has no PARTIAL_SUCCESS publication and no per-campaign savepoints. Retain existing
Worker enum values for other jobs. Max three attempts remains unchanged. WORK-04 must
serialize attempts per job and prevent re-execution of still-active timed-out computation
before claiming retry-safe behavior. An arbitrary overlapping stale-worker/lease solution
is separately gated FUT-04; no exactly-once claim is made here.

Snapshot limitation: frozen as_of prevents future-date leakage but not corrections to
old canonical facts between failed attempts. Determinism means same records/configuration;
successful replay returns persisted results. Full immutable dataset versioning is deferred.

## 6. Evaluation contract

Reuse `ai02-reference-v1` in tests/fixtures/ai02_benchmark.py; it labels before predicting.
Identity is organization/campaign/date. Seeds 20261015 and 20261016 each have 5,400 rows,
30 events, 152 anomalous days, 5,248 clean days and 30 wholly clean campaigns. No exclusions.
At threshold >=0.80, event/day recall must each be >=0.80, clean-day/campaign FPR each <=0.05.
Missing or duplicate predictions fail; report integer numerators/denominators and digest.
The existing evaluator is reused, not replaced. This benchmark supports campaign diagnostics,
not independent metric attribution, simulation accuracy or end-to-end product quality.
Historical Nour quality remains NOT RUN because original independently dated labels are absent.

## 7. Fixtures and implementation deltas

`tests/contracts/ai-pipeline-v1.json` contains **illustrative contract examples**, not model
predictions or rows claimed to have been inserted. It includes request/outcome examples,
linked output rows, degraded/cancelled/failed examples and evaluation references.
`validate-ai-pipeline.mjs` checks fields, types, canonical enums/required fields,
tenant/run/FK consistency, three-scenario coverage, and injected bad fixtures in CI.
Python tests exercise the actual typed models and pure adapters separately.

| Existing task | Required implementation after this contract is reviewed | Owner / reviewer |
|---|---|---|
| AI-05 | Pure seven-day scenario math, assumptions, undefined ratios; stored example via AI-06 adapter | Hussein / Ahmed |
| AI-06 | run_pipeline, input guards, explicit metric evidence extraction, latest-day signal selection, output repositories, atomic publication, outcome replay | Hussein / affected owners |
| AI-07 | Tenant/output tagging, read-only canonical inputs, secret exclusion, >=70% applicable coverage; real role tests after ADR 0001 rollout | Hussein / Mohamed |
| WORK-04 | Reserve run ID, direct dispatch, cancellation checkpoints, short transactions, serial retries, reconcile committed run after crash | El-Farouk / Hussein |
| API-05 | Stored output APIs, no-data/processing/degraded states, undefined-ratio marker projection | Ahmed / Abdulrahman |
| ARCH-05 / Worker | Reconcile cancellation initiation and terminal state mapping with this contract; do not add AI-to-Worker import cycle | El-Farouk / Hussein |
| Data / runtime-role cleanup | Confirm read permissions and Worker process ai_layer_role bundle; add successor migration only in owning task | Youssef / Mohamed and Ahmed |
| QA / shared contract | Review fixtures, mapping and ADR; expand production checks when adapters land | Mohamed / affected owners |

No tasks, dates or assignments are changed by this matrix. Review roles are requested,
not recorded approvals. The ARCH-01 role rollout remains deferred; helper tests are not
evidence that PostgreSQL currently enforces secret isolation.

## 8. Patterns used

- Functional core / imperative shell: pure helpers here; IO and orchestration in AI-06.
- Typed DTO and boundary validation: frozen Pydantic models; existing frozen analytical records.
- Adapter: explicit evidence to canonical AnomalySignal; filter degraded forecasts.
- Strategy: reuse AI-03 Forecaster and AI-01 DataLoader protocols; no new framework.
- Application service plus unit of work: AI-06 coordinates; existing SQLAlchemy transaction
  publishes one complete run. Worker remains the job state machine.

These patterns do not require service splitting, a message broker or a generic workflow engine.
