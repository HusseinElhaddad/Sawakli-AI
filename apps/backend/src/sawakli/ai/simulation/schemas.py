"""Explicit baseline input for the bounded, seven-day AI-05 simulator."""

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from sawakli.ai.contracts import ContractModel


class SimulationBaseline(ContractModel):
    """Caller-supplied no-action totals for as_of+1 through as_of+7.

    The caller owns baseline estimation and same-currency/source validation.
    Values are totals, never daily values or an AI-03 horizon point.
    """

    organization_id: UUID
    campaign_id: UUID
    as_of: date
    spend: Decimal = Field(ge=0, allow_inf_nan=False)
    conversions: Decimal = Field(ge=0, allow_inf_nan=False)
    revenue: Decimal = Field(ge=0, allow_inf_nan=False)
    source: str = Field(min_length=1)
    horizon_days: Literal[7] = 7

    @field_validator("source")
    @classmethod
    def source_contains_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("baseline source must contain text")
        return value
