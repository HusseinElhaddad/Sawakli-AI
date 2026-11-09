# Action simulation - proportional-v1

**Lifecycle:** AI-05 computation implemented on its feature branch; cross-layer adoption and
stored-output evidence remain AI-06/API-05 work. This refines the calculation delegated to AI-05
by the [AI integration contract](ai-pipeline-and-persistence.md#recommendations-and-simulations).
It does not change its output fields, scenarios, ownership or seven-day horizon.

## Input boundary

`sawakli.ai.simulation.SimulationBaseline` is a strict, immutable Pydantic input:

| Field | Type / meaning |
|---|---|
| organization_id, campaign_id | UUIDs identifying a single owned campaign |
| as_of | Calendar date, equal to the simulator call's cutoff |
| spend, conversions, revenue | Finite, nonnegative Decimal no-action **totals** for as_of+1 through as_of+7 |
| source | Required nonblank explanation of the baseline's source/estimation assumptions |
| horizon_days | Literal 7 |

The caller prepares an explicit no-action baseline using authorized canonical data and records
its estimation method in source. AI-05 does not estimate the baseline, read a database, fill
missing dates, choose a training window or convert AI-03 point forecasts into totals. A repeated
historical week is an example assumption, not a hidden fallback. Currency consistency remains
the caller's responsibility because canonical inputs do not carry a currency field here.

`simulate_actions(recommendations, baselines, *, organization_id, as_of)` returns an immutable
tuple of the existing SimulationBatch. The explicit organization is trusted internal scope;
authentication and selected-campaign authorization remain upstream responsibilities. It validates
all supplied inputs before returning anything, even unused baselines. Reject nonmatching tenant
or cutoff, duplicate campaign baselines, missing baseline for a recommendation, blank/invalid
campaign/rule identity, or duplicate campaign/rule recommendation keys. Extra owned baselines
are allowed and produce no rows without recommendations. Empty input returns an empty tuple.
Input iterables are consumed once. Output is sorted by campaign UUID then rule_id, with scenarios
ordered budget_decrease_20, budget_increase_15, pause. No UUID or timestamp is minted here.

## Formulas and assumptions

The supplied AI Layer Design Document section 1.7 specifies heuristic linear budget/spend behavior
and constant conversion rate; ARCH-03's worked fixture demonstrates proportional spend/conversion/
revenue totals. `proportional-v1` makes fixed acquisition efficiency and fixed value per conversion
explicit. It is a bounded what-if calculator, not an empirically fitted response model.

Let baseline totals be S, C and R. For each multiplier m (0.80, 1.15, 0):

- projected spend = S × m
- projected conversions = C × m
- projected revenue used internally = R × m
- projected CPA = projected spend / projected conversions, when conversions is nonzero
- projected ROAS = projected revenue / projected spend, when spend is nonzero

For positive denominators, proportional scaling preserves CPA and ROAS. Do not claim improvement
or budget elasticity. Revenue is necessary for ROAS arithmetic but is not an output table column.
No saturation, attribution lag, auction change, seasonality or uncertainty model is implied.

Expected conversions may be fractional. Compute in a local Decimal context with precision 28 and
ROUND_HALF_EVEN; no integer rounding, binary float, clamp or two-decimal display rounding is
applied. Arithmetic outside its exponent range raises ContractError, rather than returning an
infinite projection. The seven-day horizon must fit inside Python's date range.

## Missing, zero and undefined values

Missing totals are rejected, never interpreted as zero. A measured zero numerator with positive
denominator gives a valid zero ratio. A zero denominator yields numeric 0 only as the existing
schema sentinel plus the corresponding undefined_ratios marker. Pause always has both markers.
Zero-spend/nonzero-conversion attributed baselines are accepted; ROAS is unavailable, while CPA
can be a valid zero. This is algebraic behavior, not a claim of paid-campaign causal performance.

Every batch includes version, date range, baseline source/totals, scaling assumptions, units,
numeric precision, missing-ratio semantics and no-execution limitations. AI-06 must preserve
assumptions in parent recommendation evidence and encode each scenario's undefined markers per
the integration contract. API-05 must expose marked values as unavailable.

## Example and acceptance boundary

For S=700, C=35, R=2100, -20% gives 560/28/CPA20/ROAS3; +15% gives
805/40.25/CPA20/ROAS3. Pause gives zero spend/conversions and unavailable CPA/ROAS.
These are calculated scenario outputs, not observed outcomes or validated lift.

AI-05 returns one batch per organization/campaign/rule within a caller's model run. AI-06 owns
recommendation UUID assignment, FK resolution and atomic INSERTs into action_simulations. The
simulator neither imports an orchestrator nor updates recommendation status. The task's actual
stored-example acceptance is open until AI-06 supplies its adapter and PostgreSQL evidence.

See [technical documentation](../ai/AI-05-action-simulator.md) for executed verification and
[learning guide](../ai/guides/action-simulator-walkthrough.md) for worked explanations.
