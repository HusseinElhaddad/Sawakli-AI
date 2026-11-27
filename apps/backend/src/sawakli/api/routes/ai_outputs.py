"""GET endpoints serving stored AI outputs (API-05). Read-only, organization-scoped."""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from sawakli.api.deps import AuthContext, DbSession, get_auth_context
from sawakli.api.schemas.ai_outputs import (
    AiList,
    AiStateInfo,
    AnomalyOut,
    ForecastList,
    RecommendationOut,
    RecommendationStatus,
    SimulationList,
)
from sawakli.api.services import ai_outputs as svc

router = APIRouter(prefix="/api", tags=["ai-outputs"])

Db = DbSession


def get_org_id(auth: Annotated[AuthContext, Depends(get_auth_context)]) -> UUID:
    """Organization comes only from the validated token (API-01), never from the request."""
    return auth.organization.id


OrgId = Annotated[UUID, Depends(get_org_id)]
Limit = Annotated[int, Query(ge=1, le=1000)]
Offset = Annotated[int, Query(ge=0)]


def _require_campaign(db: Session, org_id: UUID, campaign_id: UUID | None) -> None:
    """A campaign from another organization is indistinguishable from a missing one."""
    if campaign_id is not None and not svc.campaign_exists(db, org_id, campaign_id):
        raise HTTPException(status_code=404, detail="campaign_not_found")


def _run_id(ctx: AiStateInfo) -> UUID | None:
    return ctx.run.id if ctx.state == "ready" and ctx.run is not None else None


@router.get("/ai/status", response_model=AiStateInfo)
def ai_status(org_id: OrgId, db: Db) -> AiStateInfo:
    return svc.get_ai_context(db, org_id)


@router.get("/forecasts", response_model=ForecastList)
def get_forecasts(
    org_id: OrgId,
    db: Db,
    campaign_id: UUID | None = None,
    metric: str | None = None,
) -> ForecastList:
    _require_campaign(db, org_id, campaign_id)
    ctx = svc.get_ai_context(db, org_id)
    run_id = _run_id(ctx)
    rows = svc.list_forecasts(db, org_id, run_id, campaign_id, metric) if run_id else []
    missing = svc.campaigns_without_forecast(ctx, rows, campaign_id) if run_id else []
    return ForecastList(**ctx.model_dump(), data=rows, campaigns_without_forecast=missing)


@router.get("/anomalies", response_model=AiList[AnomalyOut])
def get_anomalies(
    org_id: OrgId,
    db: Db,
    campaign_id: UUID | None = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    limit: Limit = 200,
    offset: Offset = 0,
) -> AiList[AnomalyOut]:
    _require_campaign(db, org_id, campaign_id)
    ctx = svc.get_ai_context(db, org_id)
    run_id = _run_id(ctx)
    rows = (
        svc.list_anomalies(db, org_id, run_id, campaign_id, date_from, date_to, limit, offset)
        if run_id
        else []
    )
    return AiList[AnomalyOut](**ctx.model_dump(), data=rows)


@router.get("/recommendations", response_model=AiList[RecommendationOut])
def get_recommendations(
    org_id: OrgId,
    db: Db,
    campaign_id: UUID | None = None,
    status: RecommendationStatus | None = None,
    limit: Limit = 200,
    offset: Offset = 0,
) -> AiList[RecommendationOut]:
    _require_campaign(db, org_id, campaign_id)
    ctx = svc.get_ai_context(db, org_id)
    run_id = _run_id(ctx)
    rows = (
        svc.list_recommendations(db, org_id, run_id, campaign_id, status, limit, offset)
        if run_id
        else []
    )
    return AiList[RecommendationOut](**ctx.model_dump(), data=rows)


@router.get("/recommendations/{recommendation_id}/simulations", response_model=SimulationList)
def get_simulations(recommendation_id: UUID, org_id: OrgId, db: Db) -> SimulationList:
    """Stored scenarios for one recommendation, addressed by id (any run, same org)."""
    run_id = svc.get_recommendation_run_id(db, org_id, recommendation_id)
    ctx = svc.get_run_context(db, org_id, run_id) if run_id is not None else None
    if ctx is None:
        raise HTTPException(status_code=404, detail="recommendation_not_found")
    rows = svc.list_simulations(db, org_id, recommendation_id)
    start, end = svc.horizon(ctx.run.as_of if ctx.run else None)
    return SimulationList(**ctx.model_dump(), data=rows, horizon_start=start, horizon_end=end)
