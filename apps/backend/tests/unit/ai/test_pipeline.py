from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from sawakli.ai.anomaly.detector import detect_anomalies
from sawakli.ai.contracts import ContractError, PipelineRequest
from sawakli.ai.features import engineer_features
from sawakli.ai.features.schemas import MetricRecord
from sawakli.ai.pipeline import prepare_baseline


def sample():
    request = PipelineRequest(
        organization_id=UUID(int=1),
        job_id=UUID(int=2),
        model_run_id=UUID(int=3),
        campaign_ids=(UUID(int=4),),
        as_of=date(2026, 1, 7),
    )
    metrics = tuple(
        MetricRecord(
            organization_id=request.organization_id,
            campaign_id=UUID(int=4),
            campaign_name="test",
            platform="meta",
            date=request.as_of - timedelta(days=6 - i),
            spend=Decimal(100),
            conversions=5,
            revenue=Decimal(300),
            clicks=50,
            impressions=1000,
        )
        for i in range(7)
    )
    return request, engineer_features(metrics)


def test_complete_week_and_reordered_baseline_are_hand_calculable():
    request, features = sample()
    baseline = prepare_baseline(request, features)
    assert baseline == prepare_baseline(request, tuple(reversed(features)))
    assert (baseline.spend, baseline.conversions, baseline.revenue) == (700, 35, 2100)
    assert "2026-01-01 through 2026-01-07" in baseline.source


def test_missing_calendar_day_is_not_last_seven_observations():
    request, features = sample()
    shifted = (replace(features[0], date=date(2025, 12, 31)), *features[1:])
    assert prepare_baseline(request, shifted) is None


def test_recorded_zero_day_is_present_and_not_imputed():
    request, features = sample()
    features = (
        replace(features[0], spend=Decimal(0), conversions=0, revenue=Decimal(0)),
        *features[1:],
    )
    baseline = prepare_baseline(request, features)
    assert (baseline.spend, baseline.conversions, baseline.revenue) == (600, 30, 1800)


@pytest.mark.parametrize("kind", ["duplicate", "tenant", "campaign", "future"])
def test_baseline_rejects_invalid_scope(kind):
    request, features = sample()
    bad = {
        "duplicate": features[0],
        "tenant": replace(features[0], organization_id=UUID(int=99)),
        "campaign": replace(features[0], campaign_id=UUID(int=99)),
        "future": replace(features[0], date=date(2026, 1, 8)),
    }[kind]
    with pytest.raises(ContractError):
        prepare_baseline(request, (*features, bad))


def test_metric_evidence_uses_existing_statistical_calculation():
    request, features = sample()
    # Spend-only departure: scale=5; robust z contribution=1, IQR=1.
    features = (*features[:-1], replace(features[-1], spend=Decimal(200)))
    diagnostic = detect_anomalies(features)[-1]
    evidence = next(item for item in diagnostic.metric_evidence if item.metric_name == "spend")
    assert evidence.baseline_median == 100
    assert evidence.historical_count == 6
    assert evidence.current_value == 200
    assert evidence.z_contribution == evidence.iqr_contribution == 1
    assert diagnostic.robust_z_score == diagnostic.iqr_score == Decimal("0.500000")
    assert diagnostic.score == Decimal("0.7000000")
