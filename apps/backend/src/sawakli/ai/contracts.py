"""ARCH-03 v1 integration types; these do not execute or persist a pipeline.

See docs/contracts/ai-pipeline-and-persistence.md for ownership and adoption status.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CancellationCheck = Callable[[], bool]
MetricName = Literal["spend", "ctr", "cpc", "cpa", "roas"]
WarningCode = Literal[
    "no_data", "insufficient_history", "undefined_ratios", "metric_evidence_missing"
]
ErrorCode = Literal["invalid_input", "computation_failed", "storage_failed", "cancelled"]


class ContractError(ValueError):
    """An internal handoff is inconsistent or outside the requested tenant scope."""


class ContractModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class PipelineRequest(ContractModel):
    organization_id: UUID
    job_id: UUID
    model_run_id: UUID
    as_of: date
    campaign_ids: tuple[UUID, ...] | None = None
    contract_version: Literal["ai-pipeline-v1"] = "ai-pipeline-v1"

    @field_validator("campaign_ids")
    @classmethod
    def validate_campaign_ids(cls, value: tuple[UUID, ...] | None) -> tuple[UUID, ...] | None:
        if value is not None and (not value or len(set(value)) != len(value)):
            raise ValueError("campaign_ids must be nonempty and unique, or None")
        return tuple(sorted(value, key=lambda item: item.int)) if value is not None else None


class RunStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PipelineOutcome(ContractModel):
    organization_id: UUID
    job_id: UUID
    model_run_id: UUID
    status: RunStatus
    campaigns_analyzed: tuple[UUID, ...] = ()
    warnings: tuple[WarningCode, ...] = ()
    error_code: ErrorCode | None = None
    retryable: bool = False

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        if len(set(self.campaigns_analyzed)) != len(self.campaigns_analyzed):
            raise ValueError("campaigns_analyzed must be unique")
        if self.status == RunStatus.SUCCESS and (self.error_code is not None or self.retryable):
            raise ValueError("SUCCESS cannot contain an error or be retryable")
        if self.status == RunStatus.FAILED and self.error_code not in {
            "invalid_input",
            "computation_failed",
            "storage_failed",
        }:
            raise ValueError("FAILED requires a failure code")
        if self.status == RunStatus.CANCELLED and self.error_code != "cancelled":
            raise ValueError("CANCELLED requires cancelled error_code")
        if self.status != RunStatus.FAILED and self.retryable:
            raise ValueError("only FAILED may be retryable")
        if self.error_code == "invalid_input" and self.retryable:
            raise ValueError("invalid input cannot be retried unchanged")
        if self.status != RunStatus.SUCCESS and self.campaigns_analyzed:
            raise ValueError("failed/cancelled whole-run publication has no analyzed campaigns")
        return self


class MetricEvidence(ContractModel):
    """Caller supplies real statistical evidence; never inferred from reason strings."""

    organization_id: UUID
    campaign_id: UUID
    observed_on: date
    metric_name: MetricName
    current_value: Decimal = Field(ge=0, allow_inf_nan=False)
    baseline_median: Decimal = Field(ge=0, allow_inf_nan=False)
    historical_count: int = Field(ge=5)
    z_contribution: Decimal = Field(ge=0, le=1, allow_inf_nan=False)
    iqr_contribution: Decimal = Field(ge=0, le=1, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        if self.z_contribution == 0 and self.iqr_contribution == 0:
            raise ValueError("a metric requires nonzero statistical evidence")
        return self


class Scenario(StrEnum):
    BUDGET_DECREASE_20 = "budget_decrease_20"
    BUDGET_INCREASE_15 = "budget_increase_15"
    PAUSE = "pause"


class SimulationProjection(ContractModel):
    scenario_type: Scenario
    projected_spend: Decimal = Field(ge=0, allow_inf_nan=False)
    projected_conversions: Decimal = Field(ge=0, allow_inf_nan=False)
    projected_cpa: Decimal = Field(ge=0, allow_inf_nan=False)
    projected_roas: Decimal = Field(ge=0, allow_inf_nan=False)
    undefined_ratios: tuple[Literal["cpa", "roas"], ...] = ()

    @model_validator(mode="after")
    def validate_ratios(self) -> Self:
        if len(set(self.undefined_ratios)) != len(self.undefined_ratios):
            raise ValueError("undefined_ratios must be unique")
        undefined = set(self.undefined_ratios)
        if (self.projected_conversions == 0) != ("cpa" in undefined):
            raise ValueError("zero conversions requires exactly the cpa unavailable marker")
        if (self.projected_spend == 0) != ("roas" in undefined):
            raise ValueError("zero spend requires exactly the roas unavailable marker")
        if ("cpa" in undefined and self.projected_cpa != 0) or (
            "roas" in undefined and self.projected_roas != 0
        ):
            raise ValueError("unavailable ratios use the documented numeric-zero sentinel")
        if self.scenario_type == Scenario.PAUSE and (
            self.projected_spend != 0 or self.projected_conversions != 0
        ):
            raise ValueError("pause must project zero spend and conversions")
        return self


class SimulationBatch(ContractModel):
    organization_id: UUID
    campaign_id: UUID
    rule_id: str = Field(min_length=1)
    horizon_days: Literal[7] = 7
    assumptions: tuple[str, ...] = Field(min_length=1)
    projections: tuple[SimulationProjection, ...]

    @model_validator(mode="after")
    def validate_batch(self) -> Self:
        if not self.rule_id.strip() or any(not item.strip() for item in self.assumptions):
            raise ValueError("rule_id and assumptions must contain text")
        if len(self.projections) != 3 or {item.scenario_type for item in self.projections} != set(
            Scenario
        ):
            raise ValueError("exactly one projection per approved scenario is required")
        return self
