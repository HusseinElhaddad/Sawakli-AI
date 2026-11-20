"""ARCH-03 boundary/fixture checks, not production-orchestrator acceptance."""

import json
from dataclasses import FrozenInstanceError, replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from sawakli.ai.anomaly.detector import AnomalyResult
from sawakli.ai.contracts import (
    ContractError,
    MetricEvidence,
    PipelineOutcome,
    PipelineRequest,
    SimulationBatch,
)
from sawakli.ai.features import MetricRecord, engineer_features
from sawakli.ai.forecasting import ModelUsed, generate_forecasts
from sawakli.ai.integration import (
    job_status_for,
    persistable_forecasts,
    to_anomaly_signal,
    validate_feature_scope,
)
from sawakli.shared.enums import JobStatus
from tests.fixtures.ai02_benchmark import dataset_digest, generate_benchmark

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "docker-compose.yml").exists())
MANIFEST = json.loads((ROOT / "tests/contracts/ai-pipeline-v1.json").read_text())
NORMAL = MANIFEST["cases"][0]


@pytest.mark.parametrize(
    "seed,digest_key", [(20261015, "development_digest"), (20261016, "validation_digest")]
)
def test_evaluation_manifest_matches_real_generator(seed, digest_key):
    benchmark = generate_benchmark(seed)
    manifest = MANIFEST["evaluation"]
    assert dataset_digest(benchmark) == manifest[digest_key]
    assert len(benchmark.records) == manifest["rows_per_seed"]
    assert len(benchmark.events) == manifest["events_per_seed"]
    assert len(benchmark.clean_keys) == manifest["clean_days_per_seed"]
    assert len(benchmark.clean_campaigns) == manifest["clean_campaigns_per_seed"]


def request():
    return PipelineRequest.model_validate_json(json.dumps(NORMAL["request"]))


def features():
    facts = [
        MetricRecord(
            organization_id=UUID(row["organization_id"]),
            campaign_id=UUID(row["campaign_id"]),
            campaign_name=row["campaign_name"],
            platform=row["platform"],
            date=date.fromisoformat(row["date"]),
            spend=Decimal(row["spend"]),
            impressions=row["impressions"],
            clicks=row["clicks"],
            conversions=row["conversions"],
            revenue=Decimal(row["revenue"]),
        )
        for row in NORMAL["raw_metrics"]
    ]
    return engineer_features(facts)


def evidence():
    return MetricEvidence.model_validate_json(json.dumps(NORMAL["metric_evidence"]))


def diagnostic(score="0.86", severity="critical"):
    item = evidence()
    return AnomalyResult(
        organization_id=item.organization_id,
        campaign_id=item.campaign_id,
        campaign_name="Synthetic contract diagnostic - not a model prediction",
        date=item.observed_on,
        score=Decimal(score),
        severity=severity,
        direction="down",
        robust_z_score=Decimal("1"),
        iqr_score=Decimal("1"),
        isolation_score=Decimal("0.65"),
        reasons=("fixture only",),
    )


@pytest.mark.parametrize("case", MANIFEST["cases"], ids=lambda item: item["name"])
def test_published_request_outcome_examples_are_typed_and_scoped(case):
    req = PipelineRequest.model_validate_json(json.dumps(case["request"]))
    outcome = PipelineOutcome.model_validate_json(json.dumps(case["outcome"]))
    assert job_status_for(req, outcome).value == outcome.status.value


@pytest.mark.parametrize("campaigns", [[], [str(UUID(int=101))] * 2])
def test_empty_or_duplicate_campaign_selection_is_rejected(campaigns):
    value = {**NORMAL["request"], "campaign_ids": campaigns}
    with pytest.raises(ValidationError):
        PipelineRequest.model_validate_json(json.dumps(value))


def test_unknown_request_field_and_mutation_are_rejected():
    with pytest.raises(ValidationError):
        PipelineRequest.model_validate_json(json.dumps({**NORMAL["request"], "token": "unused"}))
    with pytest.raises(ValidationError):
        request().as_of = date(2030, 1, 1)


@pytest.mark.parametrize(
    "change",
    [
        {"organization_id": UUID(int=2)},
        {"campaign_id": UUID(int=102)},
        {"date": date(2026, 10, 21)},
    ],
)
def test_feature_guard_rejects_tenant_campaign_and_future_leakage(change):
    with pytest.raises(ContractError):
        validate_feature_scope(request(), [replace(features()[0], **change)])


def test_feature_guard_rejects_duplicates_and_sorts_without_mutation():
    source = features()
    with pytest.raises(ContractError, match="duplicate"):
        validate_feature_scope(request(), [source[0], source[0]])
    assert validate_feature_scope(request(), reversed(source)) == tuple(source)
    with pytest.raises(FrozenInstanceError):
        source[0].spend = Decimal(0)


def test_hand_calculable_metric_evidence_maps_direction_not_business_direction():
    source = features()
    assert source[-1].cpa == Decimal(80)
    assert all(row.cpa == Decimal(20) for row in source[:-1])
    signal = to_anomaly_signal(diagnostic(), evidence(), anomaly_id=UUID(int=401))
    row = NORMAL["persisted_rows"]["anomalies"][0]
    assert signal is not None
    assert signal.direction == "above"  # diagnostic.direction was business-performance "down"
    assert signal.severity == row["severity"] == "high"
    assert signal.metric_name == row["metric_name"] == "cpa"
    assert signal.anomaly_score == Decimal(row["anomaly_score"])


@pytest.mark.parametrize("score,expected", [("0.799999", False), ("0.80", True), ("1", True)])
def test_critical_gate_has_exact_decimal_boundary(score, expected):
    result = to_anomaly_signal(diagnostic(score), evidence(), anomaly_id=UUID(int=401))
    assert (result is not None) == expected


@pytest.mark.parametrize(
    "field,value",
    [
        ("organization_id", str(UUID(int=2))),
        ("campaign_id", str(UUID(int=102))),
        ("observed_on", "2026-10-19"),
    ],
)
def test_anomaly_adapter_rejects_mismatched_metric_identity(field, value):
    item = MetricEvidence.model_validate_json(
        json.dumps({**NORMAL["metric_evidence"], field: value})
    )
    with pytest.raises(ContractError):
        to_anomaly_signal(diagnostic(), item, anomaly_id=UUID(int=401))


@pytest.mark.parametrize(
    "field,value",
    [
        ("historical_count", 4),
        ("current_value", "NaN"),
        ("baseline_median", "-1"),
        ("metric_name", "guessed_from_reason"),
    ],
)
def test_metric_evidence_rejects_insufficient_invalid_or_guessed_values(field, value):
    with pytest.raises(ValidationError):
        MetricEvidence.model_validate_json(json.dumps({**NORMAL["metric_evidence"], field: value}))


def test_metric_evidence_needs_statistical_contribution_and_changed_value():
    value = {**NORMAL["metric_evidence"], "z_contribution": "0", "iqr_contribution": "0"}
    with pytest.raises(ValidationError):
        MetricEvidence.model_validate_json(json.dumps(value))
    item = evidence().model_copy(update={"current_value": Decimal(20)})
    assert to_anomaly_signal(diagnostic(), item, anomaly_id=UUID(int=401)) is None


@pytest.mark.parametrize(
    "score,severity", [("NaN", "critical"), ("1.1", "critical"), ("0.86", "medium")]
)
def test_anomaly_adapter_rejects_invalid_diagnostic(score, severity):
    with pytest.raises(ContractError):
        to_anomaly_signal(diagnostic(score, severity), evidence(), anomaly_id=UUID(int=401))


def test_real_ai03_degraded_outputs_are_omitted_without_zero_fabrication():
    forecasts = generate_forecasts(list(features()))  # six observations: no eligible forecaster
    assert forecasts and all(f.model_used == ModelUsed.INSUFFICIENT_HISTORY for f in forecasts)
    assert persistable_forecasts(forecasts) == ()
    assert all(f.value is None for f in forecasts)


def usable_forecast():
    placeholder = generate_forecasts(list(features()))[0]
    return replace(
        placeholder,
        value=Decimal(100),
        ci_lower=Decimal(90),
        ci_upper=Decimal(110),
        model_used=ModelUsed.MOVING_AVERAGE,
    )


@pytest.mark.parametrize(
    "change", [{"value": None}, {"value": Decimal("Infinity")}, {"ci_lower": Decimal(120)}]
)
def test_invalid_usable_forecasts_are_rejected(change):
    with pytest.raises(ContractError):
        persistable_forecasts([replace(usable_forecast(), **change)])


def test_usable_forecast_is_preserved_and_inconsistent_placeholder_rejected():
    row = usable_forecast()
    assert persistable_forecasts([row]) == (row,)
    with pytest.raises(ContractError):
        persistable_forecasts([replace(row, model_used=ModelUsed.INSUFFICIENT_HISTORY)])


def test_three_scenarios_have_explicit_correlation_and_unavailable_pause_ratios():
    batch = SimulationBatch.model_validate_json(json.dumps(NORMAL["simulation_batch"]))
    assert batch.rule_id == "cpa_spike" and batch.horizon_days == 7
    pause = next(p for p in batch.projections if p.scenario_type == "pause")
    assert set(pause.undefined_ratios) == {"cpa", "roas"}
    assert pause.projected_cpa == pause.projected_roas == 0


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "negative", "pause_marker"])
def test_invalid_simulation_batch_is_rejected(mutation):
    value = json.loads(json.dumps(NORMAL["simulation_batch"]))
    if mutation == "missing":
        value["projections"].pop()
    elif mutation == "duplicate":
        value["projections"][2] = value["projections"][0]
    elif mutation == "negative":
        value["projections"][0]["projected_spend"] = "-1"
    else:
        value["projections"][2]["undefined_ratios"] = []
    with pytest.raises(ValidationError):
        SimulationBatch.model_validate_json(json.dumps(value))


@pytest.mark.parametrize(
    "change",
    [
        {"status": "SUCCESS", "retryable": True},
        {"status": "FAILED", "error_code": None},
        {"status": "CANCELLED", "error_code": None},
        {"status": "FAILED", "error_code": "invalid_input", "retryable": True},
    ],
)
def test_inconsistent_outcomes_are_rejected(change):
    value = {**NORMAL["outcome"], **change}
    with pytest.raises(ValidationError):
        PipelineOutcome.model_validate_json(json.dumps(value))


@pytest.mark.parametrize("field", ["organization_id", "job_id", "model_run_id"])
def test_worker_mapping_rejects_foreign_result(field):
    value = {**NORMAL["outcome"], field: str(UUID(int=999))}
    outcome = PipelineOutcome.model_validate_json(json.dumps(value))
    with pytest.raises(ContractError):
        job_status_for(request(), outcome)


def test_worker_mapping_accepts_only_scoped_terminal_success():
    outcome = PipelineOutcome.model_validate_json(json.dumps(NORMAL["outcome"]))
    assert job_status_for(request(), outcome) == JobStatus.SUCCESS
    foreign = outcome.model_copy(update={"campaigns_analyzed": (UUID(int=999),)})
    with pytest.raises(ContractError):
        job_status_for(request(), foreign)
