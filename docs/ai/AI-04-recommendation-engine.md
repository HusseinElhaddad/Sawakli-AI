# AI-04 — Recommendation Engine and Explainability

## 1. Overview

AI-04 turns campaign feature data, AI-03's forecasts, and (once available) AI-02's anomaly
detections into human-readable recommendation cards. It is the diagnosis-and-prescription step of
the AI pipeline: AI-01 measures, AI-02 flags statistical outliers, AI-03 projects forward, and
AI-04 decides whether any of that adds up to a real, explainable business problem worth a card.

AI-03 forecasts are consumed directly via its real, public `ForecastRecord` / `ModelUsed` types
(`sawakli.ai.forecasting`). AI-02 is merged, but its campaign-day diagnostic differs from
`AnomalySignal`. ARCH-03 supplies an explicit-evidence adapter and a
[reviewable integration contract](../contracts/ai-pipeline-and-persistence.md).
AI-06 still needs to extract metric evidence and wire that adapter into production.
References below to pre-AI-02 fixtures describe the original implementation checkpoint.

It implements the merged 1.6 (Recommendation Engine) and 1.8 (Explainability Formatter)
functionality from the original AI Layer design document, as a single task per the current Notion
board and 4-session schedule.

## 2. Scope

### In Scope

- Four rule-based diagnosis rules: CTR drop, CPA spike, spend waste, conversion drop.
- Rule-appropriate `confidence_score`, `severity`, and `risk_rating` scoring.
- Template-based explainability formatting (`evidence`, `problem`, `suggested_action` text).
- A typed, narrow stand-in contract (`AnomalySignal`) matching the exact columns already present
  in the real, applied `anomalies` table (`alembic/versions/0004_ai_layer_tables.py`), so this
  task can be built and tested before AI-02 exists.
- Direct consumption of AI-03's real `ForecastRecord` / `ModelUsed` (`sawakli.ai.forecasting`).
- Full unit test coverage using AI-01's real `engineer_features()` output as input.

### Out of Scope

- **Anomaly detection** (AI-02) and **forecasting** (AI-03) themselves. This task only consumes
  their output; it does not implement Z-score/IQR/Isolation Forest detection or any forecasting
  model (Random Forest / Linear Regression / Moving Average, per AI-03's own documentation).
- **Persistence.** This task does not open a database session, does not write to `recommendations`,
  and does not mint `id` / `model_run_id` / the default `status`. Mirroring AI-01 (which produces
  `FeatureRecord` objects without persisting them) and AI-03 (same, for `ForecastRecord`), AI-04
  produces `Recommendation` objects in memory only. Writing rows — and everything else in
  "Load → Engineer → Detect → Forecast → Recommend → Simulate → Explain" — is Pipeline
  Orchestrator (AI-06) work, which depends on AI-01 through AI-05.
- **Action simulation** (AI-05 / 1.7 in the original design) — the three budget scenarios per
  recommendation are a separate task consuming this one's output.
- **The "opportunity" recommendation type** (e.g. a good-ROAS, underfunded campaign suggesting a
  budget *increase*, referenced in PROD-01's demo story for Campaign B). None of the four rules
  named as this task's Definition of Done cover that case. `source_anomaly_id` is nullable to
  allow for it, but a fifth rule was not part of the approved scope — see Section 15.

## 3. Prerequisites

| Task / Contract | Status |
|---|---|
| AI-01 — Data Access and Feature Engineering | Complete and merged (commit `32d027349330e91217c82d83a275bcdeb643abac`). Sole source of input data (`FeatureRecord`). |
| AI-02 — Anomaly Detection Module | Merged. AI-06 must use ARCH-03's explicit-metric-evidence adapter; direct diagnostic-to-signal conversion is invalid. |
| AI-03 — Forecasting Module | Complete and merged (PR #14, commits `acc0493`–`844f296`). This task imports AI-03's real `ForecastRecord` / `ModelUsed` directly (Section 4). |
| INT-01 — Canonical MVP Contract Pack, Section 1.3 / 4.2 / 4.3 | Defines the exact `anomalies` and `recommendations` table columns, naming, and enum casing used throughout this task. |
| `alembic/versions/0004_ai_layer_tables.py` | The applied migration creating the `anomalies` table — the canonical shape `AnomalySignal` is built against. |
| `apps/backend/src/sawakli/ai/AGENTS.md` | AI package governance: interpretable/testable-only model philosophy, task-boundary rules, "never invent formulas" rule. |
| `docs/ai/AI-03-forecasting.md` | Source of truth for `ForecastRecord`'s fields, `SUPPORTED_METRICS`, and degraded-forecast semantics. |

## 4. Architecture

```text
FeatureRecord[]    (AI-01, real)
AnomalySignal[]    (AI-02 stand-in — empty until AI-02 ships)
ForecastRecord[]   (AI-03, real — sawakli.ai.forecasting.generate_forecasts())
        |
        v
  generate_recommendations()
        |
        +-- group features by campaign, validate org consistency
        +-- index anomalies / forecasts by (campaign_id, metric_name)
        |     (forecasts with model_used=INSUFFICIENT_HISTORY or value=None are dropped here)
        +-- for each campaign, in campaign_id order:
        |     for each rule in RULES (fixed order):
        |         evaluate rule against feature history alone
        |         if triggered: attach matching anomaly/forecast (optional)
        |                       score (confidence, severity)
        |                       build evidence text (explain.py)
        v
  Recommendation[]  (in memory — not persisted by this task)
```

Ownership boundary: everything left of `generate_recommendations()` is either AI-01's real output,
AI-03's real output, or a narrow typed view of the one table AI-02 will eventually populate.
Everything to the right of it is this task's own, pure-function responsibility. Nothing in this
diagram touches a database.

## 5. Inputs

| Field / Input | Type | Required | Source | Description |
|---|---|---|---|---|
| `features` | `Iterable[FeatureRecord]` | Yes | AI-01 (real) | Validated campaign-day features. Only the latest record per campaign is diagnosed; earlier records provide rolling/baseline context. |
| `anomalies` | `Iterable[AnomalySignal]` | No (default `()`) | AI-02 (stand-in) | Narrow typed view of `anomalies` rows: `organization_id`, `campaign_id`, `metric_name`, `direction`, `severity`, `anomaly_score`, optional `id`. |
| `forecasts` | `Iterable[ForecastRecord]` | No (default `()`) | AI-03 (real, `sawakli.ai.forecasting`) | `organization_id`, `campaign_id`, `metric_name`, `forecast_date`, `horizon_days`, `value` / `ci_lower` / `ci_upper` (all `Decimal \| None`, all `None` together for a degraded row), `model_used`, `generated_from_date`. AI-03 only populates `metric_name` with `spend`, `conversions`, or `roas` (its `SUPPORTED_METRICS`) — never `ctr` or `cpa` — so `ctr_drop` and `cpa_spike` never receive real forecast enrichment; only `spend_waste` and `conversion_drop` can. |

## 6. Outputs

| Field / Output | Type | Nullable | Consumer | Description |
|---|---|---|---|---|
| `organization_id` | `UUID` | No | AI-06, Backend, UI | Matches `recommendations.organization_id`. |
| `campaign_id` | `UUID` | No | AI-06, Backend, UI | Matches `recommendations.campaign_id`. |
| `source_anomaly_id` | `UUID \| None` | Yes | AI-06 | Set only when a matching, direction-consistent `AnomalySignal` had an `id`. |
| `problem` | `str` | No | UI (card title) | Matches `recommendations.problem`. |
| `evidence` | `tuple[str, ...]` | No | UI | Matches `recommendations.evidence` (JSONB array of strings). |
| `suggested_action` | `str` | No | UI | Matches `recommendations.suggested_action`. |
| `confidence_score` | `Decimal` (0–1) | No | UI | Matches `recommendations.confidence_score`. |
| `risk_rating` | `"low" \| "medium" \| "high"` | No | UI | Matches `recommendations.risk_rating`. |
| `severity` | `int` (1–5) | No | UI | Matches `recommendations.severity` — distinct field from `anomalies.severity` (INT-01 4.3). |
| `rule_id` | `str` | No | Tests, AI-05, AI-06 | Not a column on the real table. Used as part of the AI-05 correlation key (Section 8.1); whoever persists this object should drop it or fold it into `evidence`. |

## 7. Rules and Semantics

No project document defines numeric trigger thresholds — every reference (Proposal, GP_29_june,
the AI Layer design docs) is a single illustrative sentence, not a locked value. The thresholds
below are this task's own documented decision, per `docs/DOCUMENTATION_STANDARD.md` Section 9
("an urgent temporary decision still requires an explicit owner, written rationale, known
limitation, and follow-up task"). Full rationale and exact constants: `thresholds.py`.

| Rule | Trigger | Requires anomaly/forecast? |
|---|---|---|
| `ctr_drop` | Today's CTR ≥ 25% below its own 7-day rolling CTR (AI-01's `rolling_ctr_7d`). | No |
| `cpa_spike` | Today's CPA ≥ 30% above its own trailing 14-day mean CPA (computed by this task; AI-01 has no `rolling_cpa` field). Needs ≥ 3 prior days of CPA data. | No |
| `spend_waste` | Trailing 7-day mean ROAS < 1.0 (losing money on spend). Absolute threshold, not change-detection — intentionally fires without an anomaly (INT-01 4.2, `source_anomaly_id` nullable). Needs ≥ 3 days of ROAS data. | No |
| `conversion_drop` | AI-01's own `conversion_trend` ≤ −30% (day-over-day). | No |

Anomaly/forecast enrichment (never required, never breaks a rule when absent):

- A matching `AnomalySignal` (same `campaign_id` + `metric_name`, same `direction`) sets
  `source_anomaly_id`, adds a fixed confidence/severity bonus, and appends one evidence line.
  A same-metric anomaly in the opposite direction is treated as not matching.
- A matching `ForecastRecord` (nearest `forecast_date`) appends one evidence line projecting the
  metric forward, including AI-03's own `horizon_days` and `model_used`. Multiple forecasts for
  the same campaign/metric (AI-03 emits one per horizon — 7/14/30 days): the nearest-dated one
  wins. A forecast with `model_used=INSUFFICIENT_HISTORY` or a `None` `value` (AI-03's degraded
  representation) is never matched.
- `conversion_drop` additionally surfaces `bounce_rate` in evidence when AI-01 provided it,
  pointing at a possible landing-page cause (PROD-01's Nour Fashion Co. demo story).

Scoring (`scoring.py`) is one shared, documented heuristic for all four rules rather than a
per-rule formula: a fixed base `confidence_score` (0.55) and `severity` (3), plus a bonus when a
matching anomaly confirms the rule and a bonus when the rule's own `severe` flag is set (roughly
2× past its trigger line). Both outputs are clamped to their INT-01 4.3 contract range
(confidence 0–1, severity 1–5).

Missing-value and edge-case behavior:

| Case | Expected Behavior |
|---|---|
| Feature field needed by a rule is `None` | Rule returns no trigger (never treats `None` as zero). |
| Fewer prior days than a rule's minimum baseline window | Rule returns no trigger — no invented baseline. |
| Single bad day inside an otherwise healthy trailing window | `spend_waste` does not fire — trailing means intentionally resist one-day noise. |
| Anomaly/forecast for a campaign not present in `features` | Silently ignored — a normal "different pipeline scope" situation, not an error. |
| Anomaly/forecast for a campaign that is present, tagged with a different `organization_id` | Raises `RecommendationDataError` immediately. |
| Forecast with `model_used=INSUFFICIENT_HISTORY` or `value=None` | Never matched. |
| Empty `features` | Returns `()`. |

## 8. Public Interfaces

- `generate_recommendations(features, anomalies=(), forecasts=()) -> tuple[Recommendation, ...]`
  — the only interface other tasks should call. Pure function; no side effects, no I/O.
- `AnomalySignal`, `Recommendation`, `RecommendationDataError` (`schemas.py`) — the typed
  contracts this task owns, described in Sections 5–6.
- `ForecastRecord`, `ModelUsed` — AI-03's real types, re-exported from this package's `__init__.py`
  for caller convenience (`sawakli.ai.recommendations.ForecastRecord`), but owned and defined by
  `sawakli.ai.forecasting`.
- `RULES`, `RuleTrigger`, and the four `evaluate_*` functions (`rules.py`) — public for testing
  and for AI-06 to introspect which rule produced a given recommendation, not intended to be
  called directly by other tasks.

### 8.1 Correlation contract for AI-05 (Action Simulator)

`action_simulations.recommendation_id` is a `NOT NULL` foreign key to `recommendations.id`
(`0004_ai_layer_tables.py`). No `Recommendation` returned by this task has an `id` — none is
minted until AI-06 persists it, and AI-05 runs before that point.

The join key across that gap is `(campaign_id, rule_id)`. It is guaranteed unique within a single
`generate_recommendations()` call: each of the four rules evaluates only one campaign's single
latest-dated record, so it fires at most once per campaign per call — no two returned
`Recommendation` objects can share both fields (enforced by
`test_recommendation_campaign_and_rule_id_pairs_are_unique`). A campaign with two recommendations
firing at once (e.g. `cpa_spike` and `conversion_drop` together) is still unambiguous under this
key. List position is not a documented contract and should not be used for correlation.

This key is unique per call, not globally — across separate pipeline runs the same
`(campaign_id, rule_id)` pair can recur. At persistence time, AI-06 additionally scopes everything
by `model_run_id`, the permanent disambiguator once rows exist in the database.

## 9. Data Ownership

### Reads

- `FeatureRecord` objects passed in by the caller (AI-01's output).
- `AnomalySignal` objects passed in by the caller (currently test fixtures — AI-02 does not exist).
- `ForecastRecord` objects passed in by the caller (AI-03's real `generate_forecasts()` output
  once AI-06 wires the pipeline together; currently test fixtures).

### Writes

- Nothing. This task returns plain Python objects; it does not open a database session.

### Must Never Read

- Raw provider payloads, OAuth tokens, or any Connector-owned data.

### Must Never Write

- The `recommendations`, `anomalies`, `forecasts`, `model_runs`, or `action_simulations` tables —
  all AI Layer-owned per INT-01 1.3, but writing them is Pipeline Orchestrator (AI-06) work.

## 10. Security

Organization isolation is enforced at every cross-input boundary: features are grouped per
campaign with a same-organization check (mirroring AI-01's own validation), and any anomaly or
forecast referencing a known campaign under a different `organization_id` raises
`RecommendationDataError` rather than being silently combined. No credentials, tokens, or raw
provider payloads are read or required.

## 11. Error and Edge-Case Behavior

See the table in Section 7. No additional cases apply (no network calls, no external services, no
timeouts, no cancellation — this task is synchronous, in-process, pure computation).

## 12. Testing

### Unit Tests (`tests/unit/ai/test_recommendations.py`, 29 tests)

- Each of the four rules fires in isolation against a realistic multi-day series run through
  AI-01's real `engineer_features()`, and does not cross-trigger the other three.
- A fully healthy campaign produces zero recommendations; empty input produces `()`.
- `spend_waste` does not fire from a single bad day inside an otherwise healthy window.
- `cpa_spike` does not fire with insufficient baseline history, even when the raw numbers would
  otherwise look like a spike. `conversion_drop` does not fire, and does not crash, when a caller
  passes a history so short or gapped that the previous day's record cannot be safely identified,
  even though the latest `FeatureRecord`'s own `conversion_trend` field is already non-`None`.
- Two rules firing on the same campaign are emitted in `RULES`' fixed order; two campaigns are
  emitted in `campaign_id` order regardless of input order.
- Anomaly matching: sets `source_anomaly_id`, increases confidence/severity, appends evidence;
  an opposite-direction anomaly is not matched; an anomaly for an out-of-scope campaign is
  ignored, not an error; an anomaly with a mismatched `organization_id` raises.
- Forecast matching (against real `ForecastRecord` fixtures): appends an evidence line including
  `horizon_days` and `model_used`; the nearest of several forecast dates is used; a mismatched
  `organization_id` raises; a degraded forecast (`model_used=INSUFFICIENT_HISTORY`, `value=None`)
  is never matched and never crashes the `Decimal | None` formatting path.
- Scoring is exact and bounded: base case, severe case, high-severity-anomaly case, and a
  combined worst case all produce specific, asserted values within the INT-01 4.3 range.
- The explainability formatter produces exact, known evidence text for a hand-built trigger.
- `Recommendation`'s field set is asserted to match the real table's writable columns plus the
  one documented extra (`rule_id`). A separate test confirms `(campaign_id, rule_id)` pairs are
  always unique within one call — the correlation contract Section 8.1 documents for AI-05.

### Integration Tests

- None. This task does not touch a database (Section 2), so there is no integration surface to
  test beyond the unit suite above.

### E2E Impact

- Partial. AI-03's real forecasts flow into this task exactly as they would in production
  (Section 4). Full end-to-end recommendation generation on real demo data still depends on AI-02
  and the Pipeline Orchestrator (AI-06).

## 13. Verification

Commands executed (from `apps/backend/`):

```bash
ruff check .
ruff format --check .
mypy src
pytest
```

Results:

- `ruff check .` — PASS (repo-wide).
- `ruff format --check .` — PASS (repo-wide, 147 files).
- `mypy src` — PASS, "Success: no issues found in 87 source files" (repo-wide, strict mode;
  environment includes AI-03's `numpy` 2.5.2, `pandas` 3.0.5, `scikit-learn` 1.9.0 dependencies).
- `pytest -k recommendation` — PASS, 29 passed, 0 failed, fully isolated from unrelated suites.
- `pytest` (full suite) — 173 passed, 9 skipped, 55 errors. All 55 errors are pre-existing
  `sqlalchemy.exc.OperationalError` failures — `tests/test_auth.py`, `tests/test_job_status.py`,
  `tests/test_org_isolation.py`, `tests/worker/*`, `tests/test_analysis_refresh.py`,
  `tests/integration/ai/test_database_loader.py` (AI-01's own DB integration test), and
  `tests/integration/ai/test_forecasting_integration.py` (AI-03's own DB integration test) —
  every one attempting to reach `postgresql://...@localhost:5434/sawakli_test`, unavailable in
  this environment. None of the 55 touch this task's files.
- GitHub Actions CI run: not run — this report is pre-PR. GitHub Actions provides the PostgreSQL
  service the local environment lacks and will independently verify all DB-dependent suites once
  this is pushed.

## 14. Known Limitations

- Rule thresholds (Section 7) are reasoned defaults, not values backtested against real AI-02
  detector output, because AI-02 does not exist.
- `evaluate_spend_waste`'s single-day-noise resistance (Section 7) is a deliberate design choice,
  not a tuned statistical test — it has not been validated against the seeded demo data's actual
  noise profile.
- AI-03 only forecasts `spend`, `conversions`, and `roas` (`SUPPORTED_METRICS` in
  `sawakli.ai.forecasting.engine`) — never `ctr` or `cpa`. `ctr_drop` and `cpa_spike`
  recommendations therefore cannot receive real forecast enrichment; only `spend_waste` and
  `conversion_drop` can.
- The anomaly/forecast matching key is `(campaign_id, metric_name)` only. AI-03 emits up to three
  rows per campaign/metric (one per horizon: 7/14/30 days) by design — only the nearest-dated one
  is used for evidence. Anomalies have no equivalent tie-breaker beyond "last one wins" via dict
  insertion, since only one is expected per model run.
- The "opportunity" recommendation type (Section 2) is not implemented.
- No `model_run_id` exists yet since this task does not persist — AI-06 must supply it when
  writing rows. Correlation before that point (e.g. for AI-05) uses `(campaign_id, rule_id)`
  instead (Section 8.1).
- This task has not been run against AI-03's real `generate_forecasts()` output on the seeded
  Nour Fashion Co. dataset end-to-end — only against hand-built `ForecastRecord` fixtures in
  tests. That integration becomes possible once AI-06 wires the two together.

## 15. Follow-Up Tasks

- `AI-02` — owner TBD — must emit `metric_name` values matching AI-01's field names (`ctr`, `cpa`,
  `roas`) exactly, per INT-01's "one name per concept, everywhere" rule, or the anomaly-matching
  key in this task will silently never match.
- `AI-06` — owner TBD — must map `Recommendation` objects onto real `recommendations` rows
  (minting `id`, `model_run_id`, `status`), and decide whether to persist or drop `rule_id`. It
  will also be the first place this task's `generate_recommendations()` is called with AI-03's
  real `generate_forecasts()` output rather than test fixtures.
- `AI-05` — owner TBD — should read Section 8.1 before starting: correlate simulation output back
  to a recommendation via `(campaign_id, rule_id)`, since no `Recommendation` has an `id` at the
  point AI-05 runs.
- A dedicated threshold-tuning pass — owner TBD — once AI-02 exists and can run against the
  seeded demo data, to replace the reasoned-default thresholds in `thresholds.py` with values
  checked against real detector behavior.
- A PO-level decision on whether the "opportunity" (budget-increase) recommendation type is in
  scope for this project, and if so, as a fifth rule here or a separate task.

## 16. References and Evidence

- Notion task: AI-04 — Implement Recommendation Engine and Explainability (Base Points: 5; Due:
  07 Sep 2026, 12:59 PM).
- Canonical contracts: INT-01 Canonical MVP Contract Pack, Sections 1.3, 4.2, 4.3;
  `alembic/versions/0004_ai_layer_tables.py`.
- Related technical documentation: `docs/ai/AI-01-feature-pipeline.md`, `docs/ai/AI-03-forecasting.md`.
- Prerequisite: AI-01 completion report (commit `32d027349330e91217c82d83a275bcdeb643abac`,
  CI run #39).
- Prerequisite: AI-03 completion report (PR #14, commits `acc0493`–`844f296`, merged to `main`
  as `8d67c28`).
- Test evidence: `apps/backend/tests/unit/ai/test_recommendations.py`, 29/29 passing locally.
