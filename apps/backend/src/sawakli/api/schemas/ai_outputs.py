"""Response schemas for the stored AI output endpoints (API-05).

Field names follow tests/contracts/canonical.json. Fields marked ``ui_excluded`` there
(e.g. ``anomalies.detectors_triggered``) are deliberately absent.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

AiState = Literal["processing", "no_data", "failed", "ready"]
ScenarioType = Literal["budget_decrease_20", "budget_increase_15", "pause"]
Severity = Literal["low", "medium", "high"]
Direction = Literal["above", "below"]
RiskRating = Literal["low", "medium", "high"]
RecommendationStatus = Literal["pending", "approved", "rejected", "marked_done", "needs_review"]
Ratio = Literal["cpa", "roas"]


class RunInfo(BaseModel):
    id: UUID
    status: str
    as_of: date | None = None
    completed_at: datetime | None = None


class Omission(BaseModel):
    """A campaign whose recommendations/simulations were skipped (missing history)."""

    campaign_id: UUID
    reason: str | None = None
    window_start: date | None = None
    window_end: date | None = None
    omitted_rule_ids: list[str] = Field(default_factory=list)


class AiStateInfo(BaseModel):
    """Shared state block returned by every AI output endpoint."""

    state: AiState
    refreshing: bool = False
    run: RunInfo | None = None
    warnings: list[str] = Field(default_factory=list)
    omissions: list[Omission] = Field(default_factory=list)
    error_code: str | None = None
    # Internal only: used to derive "no forecast" campaigns. Never serialized.
    campaigns_analyzed: list[UUID] = Field(default_factory=list, exclude=True)


class AiList[T](AiStateInfo):
    data: list[T] = Field(default_factory=list)


class ForecastOut(BaseModel):
    id: UUID
    campaign_id: UUID
    metric_name: str
    forecast_date: date
    value: Decimal
    ci_lower: Decimal | None = None
    ci_upper: Decimal | None = None
    model_used: str | None = None
    created_at: datetime


class AnomalyOut(BaseModel):
    id: UUID
    campaign_id: UUID
    metric_name: str
    detected_at: datetime
    anomaly_score: Decimal
    severity: Severity
    direction: Direction
    created_at: datetime


class RecommendationOut(BaseModel):
    id: UUID
    campaign_id: UUID
    campaign_name: str | None = None
    source_anomaly_id: UUID | None = None
    problem: str
    evidence: Any = None
    suggested_action: str | None = None
    confidence_score: Decimal | None = None
    risk_rating: RiskRating | None = None
    severity: int | None = None
    status: RecommendationStatus
    created_at: datetime


class SimulationOut(BaseModel):
    """One stored scenario. A 7-day total from as_of+1 through as_of+7.

    ``projected_cpa`` / ``projected_roas`` are ``None`` (and listed in ``unavailable``)
    when their denominator is zero; the stored 0 is only a NOT NULL sentinel.
    """

    id: UUID
    recommendation_id: UUID
    scenario_type: ScenarioType
    projected_spend: Decimal
    projected_conversions: Decimal
    projected_cpa: Decimal | None
    projected_roas: Decimal | None
    unavailable: list[Ratio] = Field(default_factory=list)
    created_at: datetime


class ForecastList(AiList[ForecastOut]):
    # Analyzed campaigns with no stored forecast (insufficient history): not zero.
    campaigns_without_forecast: list[UUID] = Field(default_factory=list)


class SimulationList(AiList[SimulationOut]):
    horizon_start: date | None = None
    horizon_end: date | None = None
