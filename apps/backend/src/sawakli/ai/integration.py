"""Pure ARCH-03 boundary checks and adapters; no scheduling, DB or provider IO."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from uuid import UUID

from sawakli.ai.anomaly.detector import AnomalyResult
from sawakli.ai.contracts import ContractError, MetricEvidence, PipelineOutcome, PipelineRequest
from sawakli.ai.features import FeatureRecord
from sawakli.ai.forecasting import ForecastRecord, ModelUsed
from sawakli.ai.recommendations.schemas import AnomalySignal
from sawakli.shared.enums import JobStatus


def validate_feature_scope(
    request: PipelineRequest, records: Iterable[FeatureRecord]
) -> tuple[FeatureRecord, ...]:
    """Reject tenant leakage, future observations and duplicate campaign-days."""
    source = tuple(records)
    seen: set[tuple[UUID, object]] = set()
    for record in source:
        if record.organization_id != request.organization_id:
            raise ContractError("feature organization differs from request")
        if request.campaign_ids is not None and record.campaign_id not in request.campaign_ids:
            raise ContractError("feature campaign is outside request")
        if record.date > request.as_of:
            raise ContractError("feature date exceeds as_of")
        key = (record.campaign_id, record.date)
        if key in seen:
            raise ContractError("duplicate campaign-day")
        seen.add(key)
    return tuple(sorted(source, key=lambda item: (item.campaign_id.int, item.date)))


def to_anomaly_signal(
    diagnostic: AnomalyResult, evidence: MetricEvidence, *, anomaly_id: UUID
) -> AnomalySignal | None:
    """Map explicit metric evidence, retaining the campaign-level score's meaning."""
    if (
        diagnostic.organization_id != evidence.organization_id
        or diagnostic.campaign_id != evidence.campaign_id
        or diagnostic.date != evidence.observed_on
    ):
        raise ContractError("diagnostic/evidence identity or date differs")
    score = diagnostic.score
    if not score.is_finite() or not 0 <= score <= 1:
        raise ContractError("diagnostic score must be finite and in [0, 1]")
    if score < Decimal("0.80") or evidence.current_value == evidence.baseline_median:
        return None
    if diagnostic.severity != "critical":
        raise ContractError("critical score has inconsistent diagnostic severity")
    return AnomalySignal(
        organization_id=evidence.organization_id,
        campaign_id=evidence.campaign_id,
        metric_name=evidence.metric_name,
        direction="above" if evidence.current_value > evidence.baseline_median else "below",
        severity="high",
        anomaly_score=score,
        id=anomaly_id,
    )


def persistable_forecasts(records: Iterable[ForecastRecord]) -> tuple[ForecastRecord, ...]:
    """Separate legitimate unavailable forecasts from invalid numeric output."""
    result: list[ForecastRecord] = []
    for record in records:
        values = (record.value, record.ci_lower, record.ci_upper)
        if record.model_used == ModelUsed.INSUFFICIENT_HISTORY:
            if any(value is not None for value in values):
                raise ContractError("insufficient-history forecast must contain no numeric values")
            continue
        if record.value is None or any(
            value is not None and not value.is_finite() for value in values
        ):
            raise ContractError("usable forecast requires a finite value and finite bounds")
        if (record.ci_lower is not None and record.ci_lower > record.value) or (
            record.ci_upper is not None and record.ci_upper < record.value
        ):
            raise ContractError("forecast interval does not contain its value")
        result.append(record)
    return tuple(result)


def job_status_for(request: PipelineRequest, outcome: PipelineOutcome) -> JobStatus:
    """Translate a terminal outcome only after verifying its request identities."""
    if (
        request.organization_id != outcome.organization_id
        or request.job_id != outcome.job_id
        or request.model_run_id != outcome.model_run_id
    ):
        raise ContractError("outcome does not belong to request")
    if request.campaign_ids is not None and not set(outcome.campaigns_analyzed) <= set(
        request.campaign_ids
    ):
        raise ContractError("outcome contains unrequested campaigns")
    return JobStatus(outcome.status.value)
