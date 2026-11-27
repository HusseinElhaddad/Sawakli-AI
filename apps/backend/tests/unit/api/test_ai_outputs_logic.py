"""Pure-logic tests for API-05 (no database)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from sawakli.api.schemas.ai_outputs import AiStateInfo, ForecastOut
from sawakli.api.services.ai_outputs import (
    campaigns_without_forecast,
    horizon,
    parse_metadata,
    project_ratios,
)

D = Decimal


def test_pause_scenario_ratios_are_unavailable() -> None:
    cpa, roas, unavailable = project_ratios(D(0), D(0), D(0), D(0))
    assert (cpa, roas) == (None, None)
    assert unavailable == ["cpa", "roas"]


def test_zero_conversions_only_hides_cpa() -> None:
    cpa, roas, unavailable = project_ratios(D(100), D(0), D(0), D("1.5"))
    assert cpa is None and roas == D("1.5")
    assert unavailable == ["cpa"]


def test_measured_zero_roas_is_kept() -> None:
    cpa, roas, unavailable = project_ratios(D(100), D(5), D(20), D(0))
    assert (cpa, roas, unavailable) == (D(20), D(0), [])


def test_parse_metadata_null_and_junk_are_empty() -> None:
    for raw in (None, "x", [], {"request": 1, "outcome": [], "omissions": "no"}):
        assert parse_metadata(raw) == (None, [], [])


def test_parse_metadata_reads_contract_shape() -> None:
    cid = uuid4()
    raw = {
        "request": {"as_of": "2026-11-20"},
        "outcome": {"warnings": ["insufficient_history"]},
        "omissions": [{"campaign_id": str(cid), "reason": "missing_history"}, {"bad": 1}],
    }
    as_of, warnings, omissions = parse_metadata(raw)
    assert as_of == date(2026, 11, 20)
    assert warnings == ["insufficient_history"]
    assert [o.campaign_id for o in omissions] == [cid]


def test_horizon_is_seven_days_after_as_of() -> None:
    assert horizon(date(2026, 11, 20)) == (date(2026, 11, 21), date(2026, 11, 27))
    assert horizon(None) == (None, None)


def test_campaigns_without_forecast() -> None:
    a, b = uuid4(), uuid4()
    ctx = AiStateInfo(state="ready", campaigns_analyzed=[a, b])
    row = ForecastOut(
        id=uuid4(),
        campaign_id=a,
        metric_name="spend",
        forecast_date=date(2026, 11, 21),
        value=D(1),
        created_at=datetime(2026, 11, 20),
    )
    assert campaigns_without_forecast(ctx, [row], None) == [b]
    assert campaigns_without_forecast(ctx, [row], a) == []
