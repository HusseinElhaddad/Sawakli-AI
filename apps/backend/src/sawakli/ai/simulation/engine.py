"""Deterministic, proportional budget previews. No database or provider I/O."""

from collections.abc import Iterable
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Context, Decimal, DecimalException, Underflow, localcontext
from typing import Literal
from uuid import UUID

from sawakli.ai.contracts import ContractError, Scenario, SimulationBatch, SimulationProjection
from sawakli.ai.recommendations.schemas import Recommendation

from .schemas import SimulationBaseline

_DECIMAL_CONTEXT = Context(prec=28, rounding=ROUND_HALF_EVEN)
_DECIMAL_CONTEXT.traps[Underflow] = True
_SCENARIOS = (
    (Scenario.BUDGET_DECREASE_20, Decimal("0.80")),
    (Scenario.BUDGET_INCREASE_15, Decimal("1.15")),
    (Scenario.PAUSE, Decimal("0")),
)


def simulate_actions(
    recommendations: Iterable[Recommendation],
    baselines: Iterable[SimulationBaseline],
    *,
    organization_id: UUID,
    as_of: date,
) -> tuple[SimulationBatch, ...]:
    """Return three seven-day previews for each recommendation's correlation key.

    Validate the complete handoff before calculation; missing baselines, foreign
    tenants, inconsistent cutoffs and duplicate keys raise ContractError. Same-tenant
    baselines without recommendations are allowed but produce no output. Empty
    recommendations return an empty tuple after baseline validation.
    """
    if not isinstance(organization_id, UUID) or type(as_of) is not date:
        raise ContractError("simulation scope requires a UUID and calendar date")
    if as_of > date.max - timedelta(days=7):
        raise ContractError("simulation horizon exceeds supported calendar dates")
    by_campaign: dict[UUID, SimulationBaseline] = {}
    for baseline in baselines:
        if not isinstance(baseline, SimulationBaseline):
            raise ContractError("baselines must contain SimulationBaseline values")
        if baseline.organization_id != organization_id or baseline.as_of != as_of:
            raise ContractError("baseline organization or cutoff differs from scope")
        if baseline.campaign_id in by_campaign:
            raise ContractError("duplicate campaign baseline")
        by_campaign[baseline.campaign_id] = baseline

    source = tuple(recommendations)
    seen: set[tuple[UUID, str]] = set()
    for recommendation in source:
        if not isinstance(recommendation, Recommendation):
            raise ContractError("recommendations must contain Recommendation values")
        if recommendation.organization_id != organization_id:
            raise ContractError("recommendation organization differs from scope")
        if (
            not isinstance(recommendation.campaign_id, UUID)
            or not isinstance(recommendation.rule_id, str)
            or not recommendation.rule_id.strip()
        ):
            raise ContractError("recommendation requires a campaign UUID and nonblank rule_id")
        key = (recommendation.campaign_id, recommendation.rule_id)
        if key in seen:
            raise ContractError("duplicate recommendation correlation key")
        seen.add(key)
        if recommendation.campaign_id not in by_campaign:
            raise ContractError("recommendation has no campaign baseline")

    try:
        return tuple(
            _simulate(by_campaign[item.campaign_id], item.rule_id)
            for item in sorted(source, key=lambda item: (item.campaign_id.int, item.rule_id))
        )
    except DecimalException as exc:
        raise ContractError("baseline exceeds supported Decimal arithmetic range") from exc


def _simulate(baseline: SimulationBaseline, rule_id: str) -> SimulationBatch:
    projections: list[SimulationProjection] = []
    with localcontext(_DECIMAL_CONTEXT):
        for scenario, multiplier in _SCENARIOS:
            spend = baseline.spend * multiplier
            conversions = baseline.conversions * multiplier
            revenue = baseline.revenue * multiplier
            undefined: list[Literal["cpa", "roas"]] = []
            if conversions == 0:
                undefined.append("cpa")
            if spend == 0:
                undefined.append("roas")
            projections.append(
                SimulationProjection(
                    scenario_type=scenario,
                    projected_spend=spend,
                    projected_conversions=conversions,
                    projected_cpa=spend / conversions if conversions else Decimal(0),
                    projected_roas=revenue / spend if spend else Decimal(0),
                    undefined_ratios=tuple(undefined),
                )
            )
    start, end = baseline.as_of + timedelta(days=1), baseline.as_of + timedelta(days=7)
    return SimulationBatch(
        organization_id=baseline.organization_id,
        campaign_id=baseline.campaign_id,
        rule_id=rule_id,
        assumptions=(
            "simulation_model:proportional-v1; heuristic preview, not validated causal lift.",
            f"Seven-calendar-day totals: {start.isoformat()} through {end.isoformat()}; "
            f"as_of={baseline.as_of.isoformat()}.",
            f"Baseline source: {baseline.source}",
            f"No-action baseline totals: spend={baseline.spend}, "
            f"conversions={baseline.conversions}, revenue={baseline.revenue}.",
            "Spend, expected conversions and revenue scale by 0.80, 1.15 or 0; "
            "constant acquisition efficiency and value per conversion; no saturation or lag.",
            "Same currency as canonical input; no currency conversion. "
            "Expected conversions may be fractional; values use Decimal precision 28, half-even.",
            "Undefined CPA/ROAS use numeric-zero sentinels with undefined_ratios markers; "
            "display as unavailable, not measured zero. No external action is executed.",
        ),
        projections=tuple(projections),
    )
