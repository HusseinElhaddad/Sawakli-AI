"""AI-05 arithmetic, explicit missing-data semantics and scope invariants."""

import json
import os
import subprocess
import sys
from dataclasses import replace
from datetime import date, datetime, timedelta
from decimal import Decimal, localcontext
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from sawakli.ai.contracts import ContractError, Scenario, SimulationBatch
from sawakli.ai.features import MetricRecord, engineer_features
from sawakli.ai.recommendations import Recommendation, generate_recommendations
from sawakli.ai.simulation import SimulationBaseline, simulate_actions

ORG, OTHER, CAMPAIGN = UUID(int=1), UUID(int=2), UUID(int=101)
AS_OF = date(2026, 11, 9)


def baseline(**changes):
    return SimulationBaseline(
        **{
            "organization_id": ORG,
            "campaign_id": CAMPAIGN,
            "as_of": AS_OF,
            "spend": Decimal(700),
            "conversions": Decimal(35),
            "revenue": Decimal(2100),
            "source": "Synthetic constant daily baseline: 100 spend, 5 conversions, 300 revenue.",
            **changes,
        }
    )


def recommendation(**changes):
    return Recommendation(
        **{
            "organization_id": ORG,
            "campaign_id": CAMPAIGN,
            "source_anomaly_id": None,
            "problem": "Synthetic cost issue",
            "evidence": ("synthetic evidence",),
            "suggested_action": "Review budget scenarios",
            "confidence_score": Decimal("0.6"),
            "risk_rating": "medium",
            "severity": 3,
            "rule_id": "cpa_spike",
            **changes,
        }
    )


def run(item=None, rec=None):
    return simulate_actions(
        [rec or recommendation()], [item or baseline()], organization_id=ORG, as_of=AS_OF
    )[0]


def test_hand_calculable_three_scenarios_and_revenue_based_ratios():
    result = run()
    decrease, increase, pause = result.projections
    assert [p.scenario_type for p in result.projections] == list(Scenario)
    assert decrease.projected_spend == Decimal(560)
    assert decrease.projected_conversions == Decimal(28)
    assert increase.projected_spend == Decimal(805)
    assert increase.projected_conversions == Decimal("40.25")
    for point, revenue in [(decrease, Decimal(1680)), (increase, Decimal(2415))]:
        assert point.projected_cpa == point.projected_spend / point.projected_conversions == 20
        assert point.projected_roas == revenue / point.projected_spend == 3
        assert point.undefined_ratios == ()
    assert pause.projected_spend == pause.projected_conversions == 0
    assert pause.projected_cpa == pause.projected_roas == 0
    assert pause.undefined_ratios == ("cpa", "roas")
    assert (result.organization_id, result.campaign_id, result.rule_id) == (
        ORG,
        CAMPAIGN,
        "cpa_spike",
    )


def test_ratios_use_aggregate_baseline_totals_not_means_of_daily_ratios():
    # Spend 100/150, conversions 5/15, revenue 300/300:
    # mean daily CPA=(20+10)/2=15, aggregate CPA=250/20=12.5;
    # mean daily ROAS=(3+2)/2=2.5, aggregate ROAS=600/250=2.4.
    result = run(baseline(spend=Decimal(250), conversions=Decimal(20), revenue=Decimal(600)))
    assert result.projections[0].projected_roas == Decimal("2.4")
    assert result.projections[0].projected_cpa == Decimal("12.5")


@pytest.mark.parametrize(
    "spend,conversions,revenue,undefined,cpa,roas",
    [
        ("0", "0", "0", ("cpa", "roas"), "0", "0"),
        ("100", "0", "0", ("cpa",), "0", "0"),
        ("0", "5", "10", ("roas",), "0", "0"),
        ("100", "5", "0", (), "20", "0"),
    ],
)
def test_zero_denominators_differ_from_measured_zero(
    spend, conversions, revenue, undefined, cpa, roas
):
    point = run(
        baseline(spend=Decimal(spend), conversions=Decimal(conversions), revenue=Decimal(revenue))
    ).projections[0]
    assert point.undefined_ratios == undefined
    assert point.projected_cpa == Decimal(cpa)
    assert point.projected_roas == Decimal(roas)


def test_source_cutoff_units_assumptions_and_json_roundtrip_are_traceable():
    result = run()
    text = " ".join(result.assumptions)
    for value in [
        "2026-11-10",
        "2026-11-16",
        "spend=700",
        "revenue=2100",
        "Synthetic constant daily baseline",
        "proportional-v1",
        "Same currency",
        "not validated causal lift",
        "unavailable",
    ]:
        assert value in text
    assert SimulationBatch.model_validate_json(result.model_dump_json()) == result


def test_fractional_expected_conversions_are_preserved():
    result = run(baseline(conversions=Decimal("0.5")))
    assert result.projections[1].projected_conversions == Decimal("0.575")
    assert result.projections[1].projected_cpa == Decimal(1400)


def test_reordering_generators_and_multiple_rules_preserve_scoped_correlation():
    a, b = UUID(int=101), UUID(int=102)
    recs = [recommendation(campaign_id=b), recommendation(rule_id="ctr_drop"), recommendation()]
    bases = [baseline(), baseline(campaign_id=b, spend=Decimal(1400))]
    result = simulate_actions(iter(recs), iter(bases), organization_id=ORG, as_of=AS_OF)
    assert result == simulate_actions(
        reversed(recs), reversed(bases), organization_id=ORG, as_of=AS_OF
    )
    assert [(r.campaign_id, r.rule_id) for r in result] == [
        (a, "cpa_spike"),
        (a, "ctr_drop"),
        (b, "cpa_spike"),
    ]
    assert result[0].projections[0].projected_spend == 560
    assert result[2].projections[0].projected_spend == 1120


@pytest.mark.parametrize("spend", ["100.123456789", "1E+10"])
def test_ambient_decimal_context_does_not_change_results(spend):
    item = baseline(spend=Decimal(spend), conversions=Decimal(3))
    expected = run(item)
    with localcontext() as context:
        context.prec = 4
        context.rounding = "ROUND_DOWN"
        context.capitals = 0
        assert run(item) == expected


def test_decimal_defaults_before_import_do_not_change_results():
    # A separate process exercises import-time context creation without changing
    # the test runner's global Decimal defaults or reloading shared modules.
    script = """
import runpy
import sys
from decimal import DefaultContext, Decimal, Inexact

DefaultContext.Emin = -3
DefaultContext.Emax = 3
DefaultContext.clamp = 1
DefaultContext.traps[Inexact] = True
helpers = runpy.run_path(sys.argv[1])
item = helpers['baseline'](spend=Decimal('100.123456789'), conversions=Decimal(3))
print(helpers['run'](item).model_dump_json())
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(Path(__file__).resolve())],
        env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    expected = run(baseline(spend=Decimal("100.123456789"), conversions=Decimal(3)))
    assert SimulationBatch.model_validate_json(completed.stdout) == expected


@pytest.mark.parametrize("field", ["spend", "conversions", "revenue"])
@pytest.mark.parametrize("value", [Decimal(-1), Decimal("NaN"), Decimal("Infinity"), None, "100"])
def test_baseline_rejects_negative_nonfinite_missing_and_untyped_totals(field, value):
    with pytest.raises(ValidationError):
        baseline(**{field: value})


@pytest.mark.parametrize("changes", [{"horizon_days": 1}, {"source": " "}, {"daily_spend": 100}])
def test_baseline_rejects_wrong_horizon_blank_source_and_unknown_fields(changes):
    with pytest.raises(ValidationError):
        baseline(**changes)


def test_baseline_requires_all_totals_and_is_immutable():
    value = baseline().model_dump()
    del value["revenue"]
    with pytest.raises(ValidationError):
        SimulationBaseline(**value)
    with pytest.raises(ValidationError):
        baseline().spend = Decimal(0)


@pytest.mark.parametrize("changes", [{"organization_id": OTHER}, {"as_of": date(2026, 11, 8)}])
def test_foreign_or_stale_baseline_rejected_even_if_unused(changes):
    with pytest.raises(ContractError):
        simulate_actions([], [baseline(**changes)], organization_id=ORG, as_of=AS_OF)


@pytest.mark.parametrize(
    "changes",
    [
        {"organization_id": OTHER},
        {"campaign_id": UUID(int=999)},
        {"rule_id": " "},
        {"campaign_id": "wrong"},
    ],
)
def test_foreign_missing_or_invalid_recommendation_identity_rejected(changes):
    with pytest.raises(ContractError):
        run(rec=recommendation(**changes))


def test_duplicate_baselines_and_recommendation_keys_rejected():
    with pytest.raises(ContractError, match="duplicate campaign baseline"):
        simulate_actions([], [baseline(), baseline()], organization_id=ORG, as_of=AS_OF)
    with pytest.raises(ContractError, match="duplicate recommendation"):
        simulate_actions([recommendation()] * 2, [baseline()], organization_id=ORG, as_of=AS_OF)


def test_empty_input_and_extra_owned_baseline_do_not_invent_results():
    assert simulate_actions([], [], organization_id=ORG, as_of=AS_OF) == ()
    assert simulate_actions([], [baseline()], organization_id=ORG, as_of=AS_OF) == ()
    with pytest.raises(ContractError, match="no campaign baseline"):
        simulate_actions([recommendation()], [], organization_id=ORG, as_of=AS_OF)


@pytest.mark.parametrize(
    "scope",
    [
        {"organization_id": "not-uuid", "as_of": AS_OF},
        {"organization_id": ORG, "as_of": datetime(2026, 11, 9)},
    ],
)
def test_scope_requires_uuid_and_date(scope):
    with pytest.raises(ContractError):
        simulate_actions([], [], **scope)


def test_invalid_iterable_items_rejected_before_computation():
    with pytest.raises(ContractError):
        simulate_actions([], [object()], organization_id=ORG, as_of=AS_OF)
    with pytest.raises(ContractError):
        simulate_actions([object()], [], organization_id=ORG, as_of=AS_OF)


def test_unrepresentable_horizon_or_arithmetic_fails_explicitly():
    with pytest.raises(ContractError, match="calendar"):
        simulate_actions([], [], organization_id=ORG, as_of=date.max)
    with pytest.raises(ContractError, match="arithmetic range"):
        run(baseline(spend=Decimal("1e1000000")))
    with pytest.raises(ContractError, match="arithmetic range"):
        run(baseline(spend=Decimal("1e-1000100")))


def test_existing_arch03_illustrative_projection_values_match_real_calculation():
    root = next(p for p in Path(__file__).resolve().parents if (p / "docker-compose.yml").exists())
    manifest = json.loads((root / "tests/contracts/ai-pipeline-v1.json").read_text())
    expected = SimulationBatch.model_validate_json(
        json.dumps(manifest["cases"][0]["simulation_batch"])
    )
    assert run().projections == expected.projections


def test_real_feature_and_recommendation_outputs_feed_simulator_without_mutation():
    facts = [
        MetricRecord(
            organization_id=ORG,
            campaign_id=CAMPAIGN,
            campaign_name="Synthetic campaign",
            platform="meta",
            date=AS_OF - timedelta(days=6 - i),
            spend=Decimal(100),
            impressions=1000,
            clicks=50,
            conversions=5,
            revenue=Decimal(50),
        )
        for i in range(7)
    ]
    features = engineer_features(facts)
    recs = generate_recommendations(features)
    assert [r.rule_id for r in recs] == ["spend_waste"]
    # Explicit caller baseline assumption: repeat this fully observed synthetic week.
    item = baseline(
        spend=sum((f.spend for f in facts), Decimal(0)),
        conversions=Decimal(sum(f.conversions for f in facts)),
        revenue=sum((f.revenue for f in facts), Decimal(0)),
        source="Repeat the seven observed synthetic days ending as_of; no missing dates.",
    )
    before = replace(recs[0])
    result = simulate_actions(recs, [item], organization_id=ORG, as_of=AS_OF)
    assert result[0].rule_id == "spend_waste"
    assert result[0].projections[0].projected_spend == 560
    assert result[0].projections[0].projected_roas == Decimal("0.5")
    assert recs[0] == before
    assert facts[0].spend == features[0].spend == 100
