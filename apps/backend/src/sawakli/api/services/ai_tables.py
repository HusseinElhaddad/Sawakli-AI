"""Query-only Core handles for the AI output tables.

Mirrors tests/contracts/canonical.json. Owns no schema: nothing here is in Alembic
metadata, and API-05 never writes these tables. If AI-06 already exports equivalent
Core handles, import those here instead and delete the duplicates.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


def _enum(name: str, *values: str) -> pg.ENUM:
    return pg.ENUM(*values, name=name, create_type=False)


_UUID = sa.Uuid()
_RUN_STATUS = _enum(
    "model_run_status_enum", "RUNNING", "SUCCESS", "FAILED", "CANCELLED", "PARTIAL_SUCCESS"
)
_JOB_STATUS = _enum(
    "job_status_enum", "PENDING", "RUNNING", "SUCCESS", "FAILED", "CANCELLED", "PARTIAL_SUCCESS"
)
_SEVERITY = _enum("anomaly_severity_enum", "low", "medium", "high")
_DIRECTION = _enum("anomaly_direction_enum", "above", "below")
_REC_STATUS = _enum(
    "recommendation_status_enum", "pending", "approved", "rejected", "marked_done", "needs_review"
)
_RISK = _enum("risk_rating_enum", "low", "medium", "high")
_SCENARIO = _enum("simulation_scenario_enum", "budget_decrease_20", "budget_increase_15", "pause")

model_runs = sa.table(
    "model_runs",
    sa.column("id", _UUID),
    sa.column("organization_id", _UUID),
    sa.column("started_at", sa.DateTime),
    sa.column("status", _RUN_STATUS),
    sa.column("campaigns_analyzed", pg.JSONB),
    sa.column("error_message", sa.Text),
    sa.column("completed_at", sa.DateTime),
    sa.column("execution_metadata", pg.JSONB),
)

jobs = sa.table(
    "jobs",
    sa.column("id", _UUID),
    sa.column("organization_id", _UUID),
    sa.column("status", _JOB_STATUS),
)

campaigns = sa.table(
    "campaigns",
    sa.column("id", _UUID),
    sa.column("organization_id", _UUID),
    sa.column("name", sa.Text),
)

forecasts = sa.table(
    "forecasts",
    sa.column("id", _UUID),
    sa.column("model_run_id", _UUID),
    sa.column("organization_id", _UUID),
    sa.column("campaign_id", _UUID),
    sa.column("metric_name", sa.String),
    sa.column("forecast_date", sa.Date),
    sa.column("value", sa.Numeric),
    sa.column("ci_lower", sa.Numeric),
    sa.column("ci_upper", sa.Numeric),
    sa.column("model_used", sa.String),
    sa.column("created_at", sa.DateTime),
)

anomalies = sa.table(
    "anomalies",
    sa.column("id", _UUID),
    sa.column("model_run_id", _UUID),
    sa.column("organization_id", _UUID),
    sa.column("campaign_id", _UUID),
    sa.column("metric_name", sa.String),
    sa.column("detected_at", sa.DateTime),
    sa.column("anomaly_score", sa.Numeric),
    sa.column("severity", _SEVERITY),
    sa.column("direction", _DIRECTION),
    sa.column("created_at", sa.DateTime),
)

recommendations = sa.table(
    "recommendations",
    sa.column("id", _UUID),
    sa.column("model_run_id", _UUID),
    sa.column("organization_id", _UUID),
    sa.column("campaign_id", _UUID),
    sa.column("source_anomaly_id", _UUID),
    sa.column("problem", sa.Text),
    sa.column("evidence", pg.JSONB),
    sa.column("suggested_action", sa.Text),
    sa.column("confidence_score", sa.Numeric),
    sa.column("risk_rating", _RISK),
    sa.column("severity", sa.Integer),
    sa.column("status", _REC_STATUS),
    sa.column("created_at", sa.DateTime),
)

# No organization_id / model_run_id here: ownership always derives via recommendations.
action_simulations = sa.table(
    "action_simulations",
    sa.column("id", _UUID),
    sa.column("recommendation_id", _UUID),
    sa.column("scenario_type", _SCENARIO),
    sa.column("projected_spend", sa.Numeric),
    sa.column("projected_conversions", sa.Numeric),
    sa.column("projected_cpa", sa.Numeric),
    sa.column("projected_roas", sa.Numeric),
    sa.column("created_at", sa.DateTime),
)
