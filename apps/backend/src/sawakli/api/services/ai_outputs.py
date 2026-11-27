"""Read-only service for stored AI outputs (API-05).

Every query filters on ``organization_id`` (taken from the API-01 dependency, never from
the request). Simulations have no org column, so they are always reached by joining
through ``recommendations``.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from pydantic import ValidationError
from sqlalchemy.orm import Session

from sawakli.api.schemas.ai_outputs import (
    AiState,
    AiStateInfo,
    AnomalyOut,
    ForecastOut,
    Omission,
    Ratio,
    RecommendationOut,
    RunInfo,
    SimulationOut,
)
from sawakli.api.services import ai_tables as t

HORIZON_DAYS = 7
_SCENARIO_ORDER = {"budget_decrease_20": 0, "budget_increase_15": 1, "pause": 2}
_RUN_COLS = (
    t.model_runs.c.id,
    t.model_runs.c.status,
    t.model_runs.c.campaigns_analyzed,
    t.model_runs.c.error_message,
    t.model_runs.c.completed_at,
    t.model_runs.c.execution_metadata,
)


# --------------------------------------------------------------------------- pure helpers


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _as_uuids(value: object) -> list[UUID]:
    out: list[UUID] = []
    if isinstance(value, list):
        for item in value:
            try:
                out.append(UUID(str(item)))
            except ValueError:
                continue
    return out


def parse_metadata(raw: object) -> tuple[date | None, list[str], list[Omission]]:
    """Read ``as_of``, outcome warnings and omissions; tolerate NULL/legacy/odd shapes."""
    meta = _as_dict(raw)
    as_of = _as_date(_as_dict(meta.get("request")).get("as_of"))
    raw_warnings = _as_dict(meta.get("outcome")).get("warnings")
    warnings = [str(w) for w in raw_warnings] if isinstance(raw_warnings, list) else []
    omissions: list[Omission] = []
    raw_omissions = meta.get("omissions")
    if isinstance(raw_omissions, list):
        for item in raw_omissions:
            try:
                omissions.append(Omission.model_validate(item))
            except ValidationError:
                continue
    return as_of, warnings, omissions


def horizon(as_of: date | None) -> tuple[date | None, date | None]:
    """Seven-calendar-day total, as_of+1 through as_of+7."""
    if as_of is None:
        return None, None
    return as_of + timedelta(days=1), as_of + timedelta(days=HORIZON_DAYS)


def project_ratios(
    spend: Decimal, conversions: Decimal, cpa: Decimal, roas: Decimal
) -> tuple[Decimal | None, Decimal | None, list[Ratio]]:
    """Turn the stored 0 sentinels into ``None`` when the ratio's denominator is zero.

    CPA = spend / conversions, ROAS = revenue / spend (AI-06 contract). Zero is only a
    measured value when the denominator is nonzero.
    """
    unavailable: list[Ratio] = []
    cpa_out: Decimal | None = cpa
    roas_out: Decimal | None = roas
    if conversions == 0:
        cpa_out = None
        unavailable.append("cpa")
    if spend == 0:
        roas_out = None
        unavailable.append("roas")
    return cpa_out, roas_out, unavailable


def campaigns_without_forecast(
    ctx: AiStateInfo, rows: list[ForecastOut], campaign_id: UUID | None
) -> list[UUID]:
    analyzed = [c for c in ctx.campaigns_analyzed if campaign_id in (None, c)]
    have = {r.campaign_id for r in rows}
    return [c for c in analyzed if c not in have]


# ------------------------------------------------------------------------ run state


def _latest_run(session: Session, org_id: UUID, *, success_only: bool = False) -> Any | None:
    stmt = sa.select(*_RUN_COLS).where(t.model_runs.c.organization_id == org_id)
    if success_only:
        stmt = stmt.where(t.model_runs.c.status == "SUCCESS")
    stmt = stmt.order_by(t.model_runs.c.started_at.desc()).limit(1)
    return session.execute(stmt).first()


def _has_active_job(session: Session, org_id: UUID) -> bool:
    stmt = sa.select(
        sa.exists().where(
            t.jobs.c.organization_id == org_id,
            t.jobs.c.status.in_(["PENDING", "RUNNING"]),
        )
    )
    return bool(session.scalar(stmt))


def _info(row: Any, state: AiState, refreshing: bool, error_code: str | None = None) -> AiStateInfo:
    as_of, warnings, omissions = parse_metadata(row.execution_metadata)
    return AiStateInfo(
        state=state,
        refreshing=refreshing,
        run=RunInfo(id=row.id, status=str(row.status), as_of=as_of, completed_at=row.completed_at),
        warnings=warnings,
        omissions=omissions,
        error_code=error_code,
        campaigns_analyzed=_as_uuids(row.campaigns_analyzed),
    )


def get_ai_context(session: Session, org_id: UUID) -> AiStateInfo:
    """Resolve processing / no_data / failed / ready for this organization.

    Data is always served from the latest SUCCESS run. A newer RUNNING run or an active
    job only sets ``refreshing`` when a SUCCESS run exists, otherwise state=processing.
    """
    latest = _latest_run(session, org_id)
    if latest is not None and latest.status == "SUCCESS":
        success: Any | None = latest
    else:
        success = _latest_run(session, org_id, success_only=True)
    running = (latest is not None and latest.status == "RUNNING") or _has_active_job(
        session, org_id
    )

    if success is not None:
        info = _info(success, "ready", running)
        if "no_data" in info.warnings:
            info.state = "no_data"
        return info
    if running:
        if latest is not None and latest.status == "RUNNING":
            return _info(latest, "processing", True)
        return AiStateInfo(state="processing", refreshing=True)
    if latest is not None and latest.status == "FAILED":
        code = (latest.error_message or "unknown")[:64]
        return _info(latest, "failed", False, error_code=code)
    return AiStateInfo(state="no_data")


def get_run_context(session: Session, org_id: UUID, run_id: UUID) -> AiStateInfo | None:
    stmt = sa.select(*_RUN_COLS).where(
        t.model_runs.c.id == run_id, t.model_runs.c.organization_id == org_id
    )
    row = session.execute(stmt).first()
    return None if row is None else _info(row, "ready", False)


# ---------------------------------------------------------------------------- queries


def campaign_exists(session: Session, org_id: UUID, campaign_id: UUID) -> bool:
    stmt = sa.select(
        sa.exists().where(t.campaigns.c.id == campaign_id, t.campaigns.c.organization_id == org_id)
    )
    return bool(session.scalar(stmt))


def list_forecasts(
    session: Session, org_id: UUID, run_id: UUID, campaign_id: UUID | None, metric: str | None
) -> list[ForecastOut]:
    f = t.forecasts.c
    stmt = sa.select(
        f.id,
        f.campaign_id,
        f.metric_name,
        f.forecast_date,
        f.value,
        f.ci_lower,
        f.ci_upper,
        f.model_used,
        f.created_at,
    ).where(f.organization_id == org_id, f.model_run_id == run_id)
    if campaign_id is not None:
        stmt = stmt.where(f.campaign_id == campaign_id)
    if metric is not None:
        stmt = stmt.where(f.metric_name == metric)
    stmt = stmt.order_by(f.campaign_id, f.metric_name, f.forecast_date)
    return [ForecastOut.model_validate(dict(r._mapping)) for r in session.execute(stmt)]


def list_anomalies(
    session: Session,
    org_id: UUID,
    run_id: UUID,
    campaign_id: UUID | None,
    date_from: date | None,
    date_to: date | None,
    limit: int,
    offset: int,
) -> list[AnomalyOut]:
    a = t.anomalies.c
    stmt = sa.select(
        a.id,
        a.campaign_id,
        a.metric_name,
        a.detected_at,
        a.anomaly_score,
        a.severity,
        a.direction,
        a.created_at,
    ).where(a.organization_id == org_id, a.model_run_id == run_id)
    if campaign_id is not None:
        stmt = stmt.where(a.campaign_id == campaign_id)
    if date_from is not None:
        stmt = stmt.where(a.detected_at >= datetime.combine(date_from, time.min))
    if date_to is not None:
        stmt = stmt.where(a.detected_at < datetime.combine(date_to + timedelta(days=1), time.min))
    stmt = stmt.order_by(a.detected_at.desc(), a.metric_name, a.id).limit(limit).offset(offset)
    return [AnomalyOut.model_validate(dict(r._mapping)) for r in session.execute(stmt)]


def list_recommendations(
    session: Session,
    org_id: UUID,
    run_id: UUID,
    campaign_id: UUID | None,
    status: str | None,
    limit: int,
    offset: int,
) -> list[RecommendationOut]:
    r_ = t.recommendations.c
    joined = t.recommendations.join(
        t.campaigns,
        sa.and_(r_.campaign_id == t.campaigns.c.id, t.campaigns.c.organization_id == org_id),
        isouter=True,
    )
    stmt = (
        sa.select(
            r_.id,
            r_.campaign_id,
            t.campaigns.c.name.label("campaign_name"),
            r_.source_anomaly_id,
            r_.problem,
            r_.evidence,
            r_.suggested_action,
            r_.confidence_score,
            r_.risk_rating,
            r_.severity,
            r_.status,
            r_.created_at,
        )
        .select_from(joined)
        .where(r_.organization_id == org_id, r_.model_run_id == run_id)
    )
    if campaign_id is not None:
        stmt = stmt.where(r_.campaign_id == campaign_id)
    if status is not None:
        stmt = stmt.where(r_.status == status)
    stmt = stmt.order_by(r_.severity.desc().nulls_last(), r_.created_at.desc(), r_.id)
    stmt = stmt.limit(limit).offset(offset)
    return [RecommendationOut.model_validate(dict(r._mapping)) for r in session.execute(stmt)]


def get_recommendation_run_id(
    session: Session, org_id: UUID, recommendation_id: UUID
) -> UUID | None:
    stmt = sa.select(t.recommendations.c.model_run_id).where(
        t.recommendations.c.id == recommendation_id,
        t.recommendations.c.organization_id == org_id,
    )
    return session.scalar(stmt)


def list_simulations(
    session: Session, org_id: UUID, recommendation_id: UUID
) -> list[SimulationOut]:
    s = t.action_simulations.c
    stmt = (
        sa.select(
            s.id,
            s.recommendation_id,
            s.scenario_type,
            s.projected_spend,
            s.projected_conversions,
            s.projected_cpa,
            s.projected_roas,
            s.created_at,
        )
        .select_from(
            t.action_simulations.join(
                t.recommendations, s.recommendation_id == t.recommendations.c.id
            )
        )
        .where(
            t.recommendations.c.id == recommendation_id,
            t.recommendations.c.organization_id == org_id,
        )
    )
    out: list[SimulationOut] = []
    for row in session.execute(stmt):
        m = dict(row._mapping)
        cpa, roas, unavailable = project_ratios(
            m["projected_spend"],
            m["projected_conversions"],
            m["projected_cpa"],
            m["projected_roas"],
        )
        m.update(projected_cpa=cpa, projected_roas=roas, unavailable=unavailable)
        out.append(SimulationOut.model_validate(m))
    out.sort(key=lambda x: _SCENARIO_ORDER[x.scenario_type])
    return out
