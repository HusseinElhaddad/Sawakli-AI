"""AI-06 application service: materialize once, compute, atomically publish.

Worker owns claim/reservation/dispatch and job transitions. See the canonical
AI pipeline contract and docs/ai/AI-06-pipeline-orchestrator.md.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from decimal import Decimal, localcontext
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session

from sawakli.ai import persistence as store
from sawakli.ai.anomaly.detector import detect_anomalies
from sawakli.ai.contracts import (
    CancellationCheck,
    ContractError,
    ErrorCode,
    PipelineOutcome,
    PipelineRequest,
    RunStatus,
    WarningCode,
)
from sawakli.ai.features import DatabaseDataLoader, FeatureRecord, engineer_features
from sawakli.ai.features.metrics import FEATURE_DECIMAL_CONTEXT, decimal_sum
from sawakli.ai.features.schemas import FeatureDataError, MetricRecord
from sawakli.ai.forecasting import generate_forecasts
from sawakli.ai.integration import persistable_forecasts, to_anomaly_signal, validate_feature_scope
from sawakli.ai.recommendations import generate_recommendations
from sawakli.ai.recommendations.schemas import AnomalySignal
from sawakli.ai.simulation import SimulationBaseline, simulate_actions
from sawakli.db.session import SessionLocal
from sawakli.db.tables import (
    action_simulations_table,
    anomalies_table,
    campaigns_table,
    forecasts_table,
    recommendations_table,
)


class _Cancelled(Exception):
    pass


def _checkpoint(cancellation: CancellationCheck) -> None:
    if cancellation():
        raise _Cancelled


@dataclass(frozen=True)
class _Publication:
    outcome: PipelineOutcome
    anomalies: tuple[dict[str, Any], ...]
    forecasts: tuple[dict[str, Any], ...]
    recommendations: tuple[dict[str, Any], ...]
    simulations: tuple[dict[str, Any], ...]
    omissions: list[dict[str, object]]


def prepare_baseline(
    request: PipelineRequest,
    records: tuple[FeatureRecord, ...],
) -> SimulationBaseline | None:
    """Approved complete-calendar-week repeat; None means unavailable, never zero."""
    records = validate_feature_scope(request, records)
    if not records:
        return None
    campaign = records[0].campaign_id
    if any(item.campaign_id != campaign for item in records):
        raise ContractError("baseline must contain one campaign")
    start = request.as_of - timedelta(days=6)
    week = tuple(item for item in records if start <= item.date <= request.as_of)
    if {item.date for item in week} != {start + timedelta(days=i) for i in range(7)}:
        return None
    return SimulationBaseline(
        organization_id=request.organization_id,
        campaign_id=campaign,
        as_of=request.as_of,
        spend=decimal_sum(item.spend for item in week),
        conversions=decimal_sum(item.conversions for item in week),
        revenue=decimal_sum(item.revenue for item in week),
        source=f"historical-repeat-v1: authorized canonical daily_metrics totals from {start} "
        f"through {request.as_of} inclusive, all seven distinct calendar dates; repeat "
        "this complete week into the next seven days; MVP heuristic, not validated accuracy.",
    )


def _load(request: PipelineRequest) -> tuple[tuple[MetricRecord, ...], tuple[UUID, ...]]:
    with SessionLocal() as db, db.begin():
        db.execute(sa.text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        query = (
            sa.select(campaigns_table.c.id)
            .where(campaigns_table.c.organization_id == request.organization_id)
            .order_by(campaigns_table.c.id)
        )
        if request.campaign_ids is not None:
            query = query.where(campaigns_table.c.id.in_(request.campaign_ids))
        campaigns: tuple[UUID, ...] = tuple(db.scalars(query))
        records = DatabaseDataLoader(db).load_metrics(
            request.organization_id,
            request.campaign_ids,
            date_to=request.as_of,
        )
        return records, campaigns


def _compute(
    request: PipelineRequest,
    records: tuple[MetricRecord, ...],
    campaigns: tuple[UUID, ...],
    cancellation: CancellationCheck,
) -> _Publication:
    _checkpoint(cancellation)
    features = validate_feature_scope(request, engineer_features(records))
    if not {item.campaign_id for item in features} <= set(campaigns):
        raise ContractError("loader returned a campaign outside owned scope")
    _checkpoint(cancellation)
    groups: dict[UUID, list[FeatureRecord]] = defaultdict(list)
    for feature in features:
        groups[feature.campaign_id].append(feature)
    warnings: set[WarningCode] = set()
    if not features:
        warnings.add("no_data")
    anomaly_rows: list[dict[str, Any]] = []
    forecast_rows: list[dict[str, Any]] = []
    recommendation_rows: list[dict[str, Any]] = []
    simulation_rows: list[dict[str, Any]] = []
    omissions: list[dict[str, object]] = []
    for campaign in campaigns:
        _checkpoint(cancellation)
        history = tuple(groups.get(campaign, ()))
        if not history:
            warnings.add("insufficient_history")
        diagnostics = detect_anomalies(history)
        _checkpoint(cancellation)
        signals: list[AnomalySignal] = []
        for diagnostic in diagnostics:
            if (diagnostic.organization_id, diagnostic.campaign_id) != (
                request.organization_id,
                campaign,
            ):
                raise ContractError("diagnostic identity differs from campaign scope")
            if diagnostic.score >= Decimal("0.80") and not diagnostic.metric_evidence:
                warnings.add("metric_evidence_missing")
            for evidence in diagnostic.metric_evidence:
                anomaly_id = uuid4()
                signal = to_anomaly_signal(diagnostic, evidence, anomaly_id=anomaly_id)
                if signal is None:
                    continue
                anomaly_rows.append(
                    dict(
                        id=anomaly_id,
                        campaign_id=campaign,
                        metric_name=signal.metric_name,
                        detected_at=datetime.combine(evidence.observed_on, time()),
                        anomaly_score=signal.anomaly_score,
                        severity=signal.severity,
                        direction=signal.direction,
                        detectors_triggered={
                            **evidence.model_dump(mode="json"),
                            "score_scope": "campaign_day",
                        },
                    )
                )
                if diagnostic.date == history[-1].date:
                    signals.append(signal)
        forecasts = generate_forecasts(list(history))
        usable = persistable_forecasts(forecasts)
        if len(usable) != len(forecasts):
            warnings.add("insufficient_history")
        for point in usable:
            if (point.organization_id, point.campaign_id) != (request.organization_id, campaign):
                raise ContractError("forecast identity differs from campaign scope")
            forecast_rows.append(
                dict(
                    id=uuid4(),
                    campaign_id=campaign,
                    metric_name=point.metric_name,
                    forecast_date=point.forecast_date,
                    value=point.value,
                    ci_lower=point.ci_lower,
                    ci_upper=point.ci_upper,
                    model_used=point.model_used.value,
                )
            )
        _checkpoint(cancellation)
        baseline = prepare_baseline(request, history)
        recommendations = generate_recommendations(history, signals, usable)
        _checkpoint(cancellation)
        if baseline is None:
            warnings.add("insufficient_history")
            omissions.append(
                {
                    "campaign_id": str(campaign),
                    "reason": "incomplete_baseline_week",
                    "window_start": str(request.as_of - timedelta(days=6)),
                    "window_end": str(request.as_of),
                    "omitted_rule_ids": [item.rule_id for item in recommendations],
                }
            )
            continue
        batches = simulate_actions(
            recommendations,
            (baseline,),
            organization_id=request.organization_id,
            as_of=request.as_of,
        )
        by_key = {(item.organization_id, item.campaign_id, item.rule_id): item for item in batches}
        for recommendation in recommendations:
            if (recommendation.organization_id, recommendation.campaign_id) != (
                request.organization_id,
                campaign,
            ):
                raise ContractError("recommendation identity differs from campaign scope")
            batch = by_key[(recommendation.organization_id, campaign, recommendation.rule_id)]
            recommendation_id = uuid4()
            evidence_strings = [
                *recommendation.evidence,
                f"rule_id:{recommendation.rule_id}",
                *batch.assumptions,
            ]
            for projection in batch.projections:
                evidence_strings.append(
                    f"scenario:{projection.scenario_type.value};undefined_ratios:"
                    + ",".join(projection.undefined_ratios)
                )
                if projection.undefined_ratios:
                    warnings.add("undefined_ratios")
                simulation_rows.append(
                    dict(
                        id=uuid4(),
                        recommendation_id=recommendation_id,
                        **projection.model_dump(exclude={"undefined_ratios"}),
                    )
                )
            recommendation_rows.append(
                dict(
                    id=recommendation_id,
                    campaign_id=campaign,
                    source_anomaly_id=recommendation.source_anomaly_id,
                    problem=recommendation.problem,
                    evidence=evidence_strings,
                    suggested_action=recommendation.suggested_action,
                    confidence_score=recommendation.confidence_score,
                    risk_rating=recommendation.risk_rating,
                    severity=recommendation.severity,
                    status="pending",
                )
            )
        _checkpoint(cancellation)
    tags = {"organization_id": request.organization_id, "model_run_id": request.model_run_id}
    return _Publication(
        PipelineOutcome(
            **store.request_identity(request),
            status=RunStatus.SUCCESS,
            campaigns_analyzed=tuple(sorted(groups, key=lambda item: item.int)),
            warnings=tuple(sorted(warnings)),
        ),
        tuple({**row, **tags} for row in anomaly_rows),
        tuple({**row, **tags} for row in forecast_rows),
        tuple({**row, **tags} for row in recommendation_rows),
        tuple(simulation_rows),
        omissions,
    )


def _insert_outputs(db: Session, publication: _Publication) -> None:
    for table, rows in (
        (anomalies_table, publication.anomalies),
        (forecasts_table, publication.forecasts),
        (recommendations_table, publication.recommendations),
        (action_simulations_table, publication.simulations),
    ):
        if rows:
            db.execute(table.insert(), list(rows))


def _publish(
    request: PipelineRequest,
    publication: _Publication,
    cancellation: CancellationCheck,
) -> PipelineOutcome:
    _checkpoint(cancellation)
    with SessionLocal() as db, db.begin():
        db.execute(sa.text("SET LOCAL TIME ZONE 'UTC'"))
        job = store.lock_job(db, request)
        row = store.read_run(db, request)
        # Re-read under the job lock: two computations may have passed registration.
        completed = store.terminal(row)
        if completed is not None:
            return completed
        if job.status == "CANCELLED":
            raise _Cancelled
        if row is None:
            raise ContractError("registered run disappeared")
        store.same_claim(job, row)
        _checkpoint(cancellation)
        _insert_outputs(db, publication)
        store.save_outcome(db, request, row, publication.outcome, omissions=publication.omissions)
        return publication.outcome


def run_pipeline(request: PipelineRequest, *, cancellation: CancellationCheck) -> PipelineOutcome:
    """Execute a reserved Worker request. Database recovery errors propagate to Worker."""
    registered = False
    error: ErrorCode = "computation_failed"
    try:
        with SessionLocal() as db, db.begin():
            completed = store.register(db, request)
        if completed is not None:
            return completed
        registered = True
        _checkpoint(cancellation)
        records, campaigns = _load(request)
        with localcontext(FEATURE_DECIMAL_CONTEXT):
            publication = _compute(request, records, campaigns, cancellation)
        error = "storage_failed"
        return _publish(request, publication, cancellation)
    except _Cancelled:
        outcome = PipelineOutcome(
            **store.request_identity(request), status=RunStatus.CANCELLED, error_code="cancelled"
        )
    except (ContractError, FeatureDataError):
        outcome = PipelineOutcome(
            **store.request_identity(request), status=RunStatus.FAILED, error_code="invalid_input"
        )
    except sa.exc.SQLAlchemyError:
        # Registration failure may have committed remotely; let Worker reconcile it.
        if not registered:
            raise
        outcome = PipelineOutcome(
            **store.request_identity(request),
            status=RunStatus.FAILED,
            error_code="storage_failed",
            retryable=True,
        )
    except Exception:
        outcome = PipelineOutcome(
            **store.request_identity(request),
            status=RunStatus.FAILED,
            error_code=error,
            retryable=True,
        )
    if not registered:
        return outcome
    # Deliberately outside the try: failure recording errors must reach Worker recovery.
    with SessionLocal() as db, db.begin():
        return store.finalize_failure(db, request, outcome)
