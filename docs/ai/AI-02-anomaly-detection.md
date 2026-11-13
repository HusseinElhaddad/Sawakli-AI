# AI-02 — Explainable Campaign Anomaly Detection

## 1. Overview

**23 October integration handoff:** ARCH-03 now supplies a pure, explicit-evidence
adapter and [contract v1](../contracts/ai-pipeline-and-persistence.md), prepared for
affected-owner review. AI-02's algorithm and diagnostic shape are unchanged. AI-06
must expose actual metric contributions and wire the adapter; no production
pipeline or per-metric model-quality result is claimed by this handoff.

AI-02 consumes AI-01 `FeatureRecord` histories and returns one immutable
`AnomalyResult` per organization/campaign/day. It combines robust Z-score, IQR
and Isolation Forest evidence into a score, severity, performance direction and
plain-text statistical reasons.

Original implementation: **Ahmed Ibrahem** (`ahmed-ibrahem1793`). Hussein Elhaddad
owns the subsequent tenant/evaluation fixes and handoff. Contributor history is
preserved in [PR #19](https://github.com/elfaroukomaradmission-a11y/Sawakli-AI/pull/19).

**15 October 2026 revision:** the missing evaluation path is supplied by a new,
versioned 90-day reference benchmark. It exposed excessive clean-campaign flags;
minimum statistical dispersion and two-feature corroboration correct that failure.
This supersedes the earlier max-feature/zero-dispersion scoring description.
The historical 360-row Nour seed remains unchanged and unlabeled; its recall/FPR
is **not** claimed. See the [benchmark definition and executed evidence](../testing/AI-02-seeded-benchmark.md).

## 2. Scope

### In scope

- Pure in-memory, organization/campaign-isolated analysis of AI-01 features.
- Robust Z, IQR and 200-tree Isolation Forest ensemble; deterministic ordering.
- Explicit missing-value and insufficient-history behavior.
- Mathematical, tenant, ordering, missing-data and benchmark regression tests.
- Reproducible source facts, independently defined intervention labels, complete
  clean masks and integer-denominator evaluation at a declared operating point.

### Out of scope

Loading/feature engineering (AI-01), forecasting (AI-03), recommendations (AI-04),
simulation (AI-05), orchestration/persistence (AI-06), REST/UI integration and
broader runtime-role acceptance (AI-07). No schema, dependency, migration,
credential, provider action or canonical source-table change is introduced.

## 3. Prerequisites

| Source | Use |
|---|---|
| [AI-01](AI-01-feature-pipeline.md) | Validated `FeatureRecord` input; raw facts and derived ratios |
| [Reference benchmark v1](../testing/AI-02-seeded-benchmark.md) | New deterministic facts, dated interventions and explicit clean denominators |
| DATA-02 / PROD-01 | Historical Nour story and quality targets; original dated ground truth remains unavailable |
| [ADR 0001](../adr/0001-runtime-boundaries-and-database-roles.md) | Accepted in-process boundaries and deferred runtime-role rollout |
| [Canonical schema](../../tests/contracts/canonical.json) | Downstream persistence boundary; unchanged |

The project lead requested fixing the evaluation issue and then merging on
15 October, with human approval treated as satisfied. This is an explicit
execution assumption, not a fabricated GitHub approval or DATA-02-owner review.
The new benchmark is a reference for this standalone analytical task; it does
not recover the missing historical generator or establish full demo acceptance.

## 4. Architecture

`detect_anomalies` materializes the iterable, groups by
`(organization_id, campaign_id)`, sorts each group by date and evaluates it
independently. It returns results sorted by organization UUID, campaign UUID and
date. Reordered equivalent inputs produce the same outputs.

Statistical detectors compare each row with strictly earlier dates only.
Isolation Forest fits the entire supplied campaign group retrospectively.
Neither the function nor benchmark reads/writes PostgreSQL or provider APIs.

## 5. Inputs

```python
detect_anomalies(
    records: Iterable[FeatureRecord],
    *,
    contamination: float = 0.05,
    random_state: int = 42,
) -> tuple[AnomalyResult, ...]
```

Features: `spend`, `ctr`, `cpc`, `cpa`, `roas`, `spend_trend`,
`conversion_trend`, `roas_trend`, `rolling_ctr_7d`, `rolling_ctr_14d`,
`rolling_cpc_7d`, `rolling_cpc_14d`. UUIDs/dates are identities, not model columns.

The caller authorizes access. Computational grouping prevents baseline/model
leakage but does not replace authentication. AI-01 owns raw validation, duplicate
rejection, stable campaign metadata, Decimal facts and ratio calculation.

## 6. Outputs

`AnomalyResult` is a frozen dataclass containing organization/campaign UUIDs,
campaign name, date, `score`, `severity`, `direction`, `robust_z_score`,
`iqr_score`, `isolation_score`, and a tuple of `reasons`.

Each statistical component is now the average of its two strongest feature
contributions, padded with zero if only one feature supplies evidence. Reasons
identify the strongest feature in each statistical branch; they are not full
forest attribution or an exhaustive decomposition of the score.

This diagnostic is **not** a canonical per-metric `anomalies` row or AI-04
`AnomalySignal`. It has no `metric_name`; `up/down` denotes heuristic performance
movement rather than metric `above/below`, and its severity set includes
`normal/critical`. ARCH-03 must settle that mapping before AI-06 persists or
adapts it. No mapping is silently added here.

## 7. Rules and Semantics

### Robust Z contribution

For a feature with historical median `m`, historical MAD and current value `x`:

```text
floor = max(abs(m) * 0.05, 1e-12)     for level/rolling features
floor = 0.05                        for relative-change trend features
scale = max(1.4826 * MAD, floor)
z_feature = min(abs(x - m) / (6 * scale), 1)
```

The trend floor is five percentage points, not five percent of a zero-centered
trend. Floors prevent tiny quantization/rolling variation from becoming unlimited
evidence when MAD is zero or very small. They are minimum spread assumptions,
not guarantees of calibrated probabilities or universal business thresholds.

### IQR contribution

Compute historical Q1 and Q3, and use:

```text
width = max(Q3 - Q1, floor)
lower = Q1 - 1.5 * width
upper = Q3 + 1.5 * width
iqr_feature = 0                      inside [lower, upper]
iqr_feature = min(distance / (3 * width), 1)   outside the interval
```

`distance` is the nonnegative distance to the violated fence. The same
feature-specific floor applies. A zero-width history is no longer an automatic
maximum for any unequal value.

### Statistical aggregation and precision

Per-feature contributions are rounded to six decimal places. Each branch returns
`(largest + second_largest) / 2`, padding missing evidence with zero and rounding
the aggregate to six places with Decimal half-even rounding. A single saturated
feature contributes at most `0.5` to a statistical branch. Two features need not
be statistically independent; no independence claim is made.

Hand-calculable assertions:

- Spend history `[1,2,3,4,5]`, current `8`: median `3`, MAD `1`, Q1 `2`, Q3 `4`.
  Per-feature Z `0.562076`, IQR `0.166667`; with no other abnormal feature the
  reported components are `0.281038` and `0.083334`.
- Constant spend `100`, current `110`: effective scale/width `5`, upper fence
  `107.5`. Per-feature Z `0.333333`, IQR `0.166667`; reported components
  `0.166666` and `0.083334`.
- A zero-centered trend moving to `0.10` uses width `0.05`; the same reported
  values result. Future/current rows cannot enter historical baselines.

### Isolation Forest

Partially missing columns use the observed group median **only in the forest
matrix**. Fully unavailable columns are omitted. Original `None` values remain
unchanged. The model uses `n_estimators=200`, seed `42` by default and the supplied
`contamination`. Negative decision values are min/max-normalized within the group;
equal raw values produce zeros. This existing normalization is unchanged.

The forest fits all supplied dates, including dates later than a scored row.
Scores can change when new rows are supplied; they are retrospective relative
signals, not causal online predictions or anomaly probabilities. In particular,
`contamination=0.05` does not guarantee a 5% ensemble false-positive rate.

### Ensemble, severity and direction

```text
score = clip(0.40 * robust_z_score + 0.20 * iqr_score + 0.40 * isolation_score, 0, 1)
```

| Score | Severity |
|---|---|
| below 0.20 | normal |
| 0.20 to below 0.40 | low |
| 0.40 to below 0.60 | medium |
| 0.60 to below 0.80 | high |
| at least 0.80 | critical |

Weights and severity boundaries are unchanged. The reference benchmark flags
**critical** scores (`>=0.80`). That operating point does not claim the same
quality for the toy regression's `>=0.40`, nor establish a production alert/API
policy; ARCH-03 must make that policy explicit.

`direction` remains the original `normal/up/down/mixed` business-performance
heuristic. It combines movements in different units and is not a causal finding
or per-metric direction. Reasons are deduplicated statistical explanations.

### History gates

Empty input returns `()`. A group with fewer than five total records receives
score-zero results with `insufficient campaign history`. Each statistical feature
separately needs five strictly earlier nonmissing observations. Current/future
values cannot satisfy this requirement. Missing statistical values are skipped.

## 8. Public Interfaces

- `detect_anomalies`: typed pure analytical function shown above; no I/O side effects.
- `AnomalyResult`: immutable campaign-day diagnostic described above.
- `scripts/ai02_benchmark.py`: test/evidence replay, not a production entry point.
  It can export source CSV, explicit labels/clean masks and results, and exits
  nonzero if any declared quality gate fails.
- `scripts/ai02_evidence.py`: read-only diagnostic trace of all historical Nour rows;
  it deliberately does not calculate quality without dated ground truth.

## 9. Data Ownership

### Reads

Caller-supplied authorized AI-01 features. Benchmark tooling additionally reads its
own synthetic generator or the committed migration's literal fact block.

### Writes

No runtime persistent writes. Optional benchmark export writes only to the
explicit local audit directory chosen by its operator.

### Must Never Read

Credentials, OAuth tokens, user/password data, raw provider payloads or unauthorized
tenant facts. The historical trace parses literals; it executes no SQL/migration.

### Must Never Write

Canonical facts, provider actions, credentials, migrations or another layer's
owned tables. No DB/API/persistence interface is introduced by this task.

## 10. Security

Grouping, imputation, baselines and forest fitting retain organization and
campaign scope. Regression tests compare a combined two-tenant call sharing a
campaign UUID with separate calls. Existing tenant tests remain intact.
Runtime RLS/role enforcement and credential isolation remain AI-07/ADR follow-ups.

## 11. Error and Edge-Case Behavior

| Case | Behavior |
|---|---|
| Empty iterable | Empty tuple |
| Fewer than five group records | Score zero, insufficient-history reason |
| Fewer than five historical feature observations | No statistical evidence for that feature |
| Missing optional feature | Skip statistics; median imputation/drop-column for the forest |
| Zero/near-zero historical spread | Finite documented dispersion floor |
| One anomalous feature | At most 0.5 in each statistical branch; corroboration needed for saturation |
| Equivalent reordered records | Same sorted results |
| Duplicate raw campaign-day | Rejected by upstream AI-01 |
| Missing/duplicate benchmark predictions | Evaluator raises instead of shrinking the denominator |
| DB/provider failure, timeout or cancellation | N/A — no such I/O/async path exists here |

## 12. Testing

`test_detector.py` covers empty/short histories, mathematical formulas and floors,
trend percentage points, near-constant rolling features, top-two corroboration,
feature-specific sparse history, constant normal data, positive/negative changes,
missing columns, tenant collision, input ordering and repeatability.

`test_detector_evaluation.py` retains the earlier 30-event/30-clean homogeneous
21-day regression at threshold `0.40`. It remains supplemental evidence.

`test_detector_benchmark.py` verifies reproducibility, pinned data digests,
complete clean/anomaly labels, variable clean histories, result coverage,
separate event/day/campaign denominators, and the quality gates on **both**
90-day seeds. All facts pass real AI-01 engineering before detection.

Integration/E2E: N/A for standalone detector I/O. Configured repository CI still
checks the backend, migrations, frontend and Compose smoke paths.

## 13. Verification

Prepublication verification on 15 October 2026:

Fresh environment:

```bash
uv venv /tmp/ai02-acceptance-venv --python python3.12
uv pip install --python /tmp/ai02-acceptance-venv/bin/python -e 'apps/backend[dev]'
```

Observed environment: CPython 3.12.14; NumPy 2.5.4, scikit-learn 1.9.1, SciPy 1.18.1.
Commands below use that environment; backend commands run from `apps/backend`.

| Check | Result |
|---|---|
| `ruff check . ../../scripts/ai02_evidence.py ../../scripts/ai02_benchmark.py` | PASS |
| `ruff format --check . ../../scripts/ai02_evidence.py ../../scripts/ai02_benchmark.py` | PASS |
| `mypy src` | PASS — 90 source files |
| `pytest tests/unit -q -k 'not ninety_day'` | PASS — 161 tests, 2 dependency warnings; benchmark replay checked separately |
| `pytest tests/unit/ai/test_detector_benchmark.py -q -s` | PASS — 5 tests, including both 90-day replays |
| Root benchmark replay, seeds 20261015 and 20261016 | PASS — exact counts below |
| Root `scripts/ai02_evidence.py` historical trace | PASS — all 360 rows traced; historical quality remains unmeasured |
| Documentation governance and whitespace check | PASS — task headings and whitespace checked |
| Local full PostgreSQL/migration/Compose checks | NOT RUN — PostgreSQL and Docker executables unavailable; final-head CI is required |
| Final-head remote CI | NOT RUN — awaiting publication at this prepublication checkpoint; final-head results are recorded in PR #19 before merge |

| Reference measure | Development | Reserved validation |
|---|---|---|
| Event recall | 30/30 = 100% | 30/30 = 100% |
| Anomalous-day recall | 149/152 = 98.03% | 144/152 = 94.74% |
| Clean-day FPR | 62/5,248 = 1.18% | 59/5,248 = 1.12% |
| Clean-campaign FPR | 0/30 = 0% | 1/30 = 3.33% |

All four declared reference gates pass. The dataset digests, generation rules,
exact interval matching and export commands are in the [benchmark record](../testing/AI-02-seeded-benchmark.md).
The validation seed was scored after the implementation was fixed, with no
subsequent score-policy adjustment. This is an independently seeded replay, not
a claim that the retrospective detector held out future dates from fitting.

## 14. Known Limitations

- Historical DATA-02/Nour recall/FPR: **NOT RUN — original approved dated labels,
  clean masks and generator remain unavailable**. The new benchmark is explicitly
  distinct; no historical labels are inferred from detector output.
- The reference events are controlled strong changes. Their quality figures do
  not establish real-campaign accuracy, subtle-event recall or generalization.
- Thirty clean campaigns give a coarse FPR estimate; 1/30 is already 3.33%.
- The 5%/five-percentage-point floors and top-two corroboration trade sensitivity
  to small isolated changes for fewer severe false alerts. Related features are
  correlated; scores are not calibrated probabilities. Only critical-alert quality
  is established on the reference benchmark.
- The forest remains retrospective and group-relative. The statistical history
  is expanding rather than seasonal; online/seasonal acceptance is future work.
- Constant chronic underperformance, the full product demo, a canonical anomaly
  adapter, persistent outputs and a production caller are not implemented here.
- INT-01's historical `feature_daily` input differs from merged AI-01's in-memory
  features from `daily_metrics`; ARCH-03 must resolve this inherited boundary.
- Human approval is treated as satisfied only under the project lead's explicit
  instruction; no independent approval event is invented in GitHub.

## 15. Follow-Up Tasks

- **ARCH-03:** settle feature-source ownership, retrospective/online semantics,
  critical versus other alert policies, campaign-day/per-metric mapping, and the
  AI-04/persistence adapter. Record the changed scoring semantics in that handoff.
- **DATA-02/product owner:** recover the original generator/validation artifacts
  and supply independent historical Nour labels; evaluate without retrospective
  relabeling or post-hoc clean exclusions.
- **AI-06:** implement only the agreed adapter, orchestration and idempotent writes.
- **AI-07:** complete broader role/security/organization-isolation acceptance.
- Future model-quality work: larger independent datasets, subtle/seasonal change
  tests, chronic-performance rules and production alert calibration.

## 16. References and Evidence

- [AI-02 task](https://app.notion.com/p/3bc7de83a91b812f90a3d45525c40682)
- [PR #19](https://github.com/elfaroukomaradmission-a11y/Sawakli-AI/pull/19)
- [Reference benchmark](../testing/AI-02-seeded-benchmark.md)
- [AI-01 input](AI-01-feature-pipeline.md); [AI-04 boundary](AI-04-recommendation-engine.md)
- [Canonical schema](../../tests/contracts/canonical.json)
- DATA-02 `README_DATA02.md`, PROD-01 scope freeze and original AI-02 attachment
  re-read on 15 October; none supplies original dated ground truth.

No new architectural decision, shared output shape, persistence or migration is
established by this change. ARCH-03 remains the shared-interface decision point.
