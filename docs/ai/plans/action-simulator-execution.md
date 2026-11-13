# AI-05 execution plan

Prepared 9 November 2026 against main `9443642a2cdfbf6293eba7ffac645f65a8e3ee45`.

## Goal and acceptance

Implement a pure, deterministic preview of the three approved budget scenarios. The input is
AI-04 recommendations plus explicitly supplied seven-day no-action baseline totals. The output
is the existing ARCH-03 SimulationBatch, correlated by organization/campaign/rule within a run.
AI-04 and DATA-01 are Done in Notion. ARCH-03 is merged; ADR 0002 still says prepared for review.

| Acceptance requirement | Delivery | Validation |
|---|---|---|
| Three bounded scenarios and nonnegative outputs | Decimal-based calculation, existing Scenario enum | Hand-calculated -20%, +15%, pause; fractional and zero cases |
| Explicit assumptions | Source, cutoff/horizon, baseline totals, proportional response and limitations in each batch | Assert traceable assumptions and JSON round-trip |
| Results persist in action_simulations | AI-06-owned adapter and publication, per canonical integration contract | Downstream gate; do not claim a pure fixture is a DB insert |
| No live writes | No network/DB/scheduler dependency in simulator | In-process tests and import-boundary inspection |

## Ordered execution

1. **Reconcile scope.** Read task, prerequisites, current contracts, migrations, AI-04 output,
   instructions and existing tests. Check current main and competing implementation work.
2. **Define the input and formula contract.** Add a strict immutable SimulationBaseline carrying
   organization, campaign, as_of, a seven-day horizon, source description and spend/conversion/
   revenue totals. This is caller-supplied analytical input, not a new forecast algorithm.
   Preserve ARCH-03's output schema and persistence ownership. Record semantics canonically once.
3. **Implement computation.** Scale each baseline total by 0.80, 1.15 or 0. Compute CPA as
   projected spend / projected conversions and ROAS as projected revenue / projected spend.
   Use a pinned Decimal context; preserve fractional expected conversions. For undefined ratios,
   emit numeric-zero sentinels only with matching markers. No model fitting or provider call.
4. **Protect the handoff.** Reject foreign-organization inputs, wrong as_of, missing baselines,
   duplicate campaign baselines and duplicate campaign/rule recommendation keys. Reject missing,
   negative or nonfinite totals at model construction. Sort output by campaign UUID and rule ID.
   Accept extra same-tenant baselines for campaigns with no recommendation; never silently skip
   a recommendation lacking its baseline. Empty recommendations return no simulation batches.
5. **Prove behavior.** Test exact known totals, revenue-based ROAS, ratio-of-totals semantics,
   zeros and unavailable markers, fractional projections, immutable inputs, permuted iterables,
   different ambient Decimal precision, isolation, malformed data and actual AI-04 output.
6. **Verify.** Run focused tests, Ruff/format, strict mypy, backend unit regression and the root
   contract runner. Run DB/Compose checks only if available; record NOT RUN otherwise. Validate
   documentation governance against the actual base and review the final diff.
7. **Document.** Maintain the required 17-section AI-05 task document with walkthrough in section 5.
   Add a separate plain-language guide explaining inputs, formulas, code paths, tests, limits and
   AI-06 adoption. Link them from docs/README.md. Export two readable PDFs and inspect every page.
8. **Handoff.** Commit a focused branch, prepare a reviewable PR when publishing is available,
   and attach links/evidence to the existing Notion task. Never mark full acceptance Done before
   actual persistence evidence and review/merge requirements are met. Do not merge automatically.

## Formula provenance and assumptions

The supplied AI Layer Design Document section 1.7 specifies heuristic linear budget/spend behavior,
constant conversion rate and exactly three scenarios. ARCH-03 defines the seven-day horizon and
its illustrative fixture scales spend, conversions and revenue proportionally. Implementation
makes the required constant cost per conversion and constant value per conversion assumptions
explicit. It does not claim causal lift, elasticity, uncertainty intervals or model accuracy.

Baseline preparation remains explicit caller work: identify source/assumptions and supply valid
weekly totals through the fixed cutoff. Do not multiply a single AI-03 day-7 point as though it
were already a weekly total. No historical window, gap filling or estimator is silently invented.

## Scope limits and risks

- Production persistence, recommendation UUID/FK resolution, human-decision status preservation,
  replay and atomic transactions remain AI-06. Stored example acceptance remains open until then.
- Runtime invocation/cancellation remain Worker/AI-06; API projection of unavailable values remains
  API-05. No endpoint, migration, provider action or existing AI formula changes.
- Baseline provenance is caller-supplied and cannot prove data quality or currency consistency.
- The linear heuristic preserves efficiency ratios for positive denominators. It is useful for
  consistent previews, not evidence that scaling a real campaign maintains efficiency.
- No work on DEV-02 cleanup, dependency upgrades or unrelated README snapshot repairs.

## Deliverables

- SimulationBaseline, simulate_actions, and reuse of existing projection/batch types.
- Focused tests and an AI-01/AI-04-to-AI-05 in-memory flow.
- Canonical scenario semantics; technical task document; separate implementation/learning guide.
- Verification evidence and honest persistence/adoption status; downloadable technical/guide PDFs.
