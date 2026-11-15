"""SQLAlchemy Core table definitions for querying the real database.

Deliberately NOT registered on the same metadata Alembic uses
(`sawakli.db.session.Base.metadata`, wired up in alembic/env.py as
target_metadata) — this project's schema is built from hand-written raw-SQL
migrations (see alembic/versions/, ported from DATA-01), not from
SQLAlchemy models. If these tables were added to Base.metadata,
`alembic revision --autogenerate` would compare it against the live
database and see every other table as "unknown to metadata," which is
exactly the kind of surprise that leads to someone accidentally generating
a migration that drops half the schema. Keeping a separate MetaData here
means these are just typed handles for building SELECT/INSERT statements —
they're never a source of truth for what alembic upgrade actually builds.

As more layers add their own repositories, their tables belong here too,
following the same pattern — one shared, query-only metadata, decoupled
from Alembic's migration metadata.

Column shapes are copied exactly from Ahmed Ibrahim's DATA-01 deliverable
(002_backend_tables.sql, 003_data_layer_tables.sql, 005_connector_tables.sql) —
kept in sync with the corresponding migrations under alembic/versions/.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import BYTEA, ENUM, JSONB, TIMESTAMP, UUID

metadata = sa.MetaData()

provider_enum = sa.Enum(
    "googleads",
    "metaads",
    "googleanalytics",
    "csv_demo",
    name="provider_enum",
    # the real type is created by alembic/versions/0001_...; never re-create it here
    create_type=False,
)

data_source_status_enum = sa.Enum(
    "connected",
    "disconnected",
    "syncing",
    "failed",
    "stale",
    "demo_data",
    name="data_source_status_enum",
    create_type=False,
)

sync_status_enum = sa.Enum(
    "pending",
    "running",
    "success",
    "failed",
    name="sync_status_enum",
    create_type=False,
)

# ------------------------------------------------------------------------------
# data_sources — Backend-owned (creates the row); Data Layer updates status
# fields only. Connector Layer has read-only access (INT-01 Ownership &
# Access Matrix). Not queried by the connectors package today (check_connection_status()
# receives last_synced_at from its caller); never written to by this package.
# ------------------------------------------------------------------------------
data_sources_table = sa.Table(
    "data_sources",
    metadata,
    sa.Column(
        "id",
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    ),
    sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
    sa.Column("provider", provider_enum, nullable=False),
    sa.Column("external_account_id", sa.Text, nullable=True),
    sa.Column("status", data_source_status_enum, nullable=False),
    sa.Column("last_synced_at", TIMESTAMP(timezone=False), nullable=True),
    sa.Column("sync_status", sync_status_enum, nullable=True),
    sa.Column("last_error", sa.Text, nullable=True),
    sa.Column("created_at", TIMESTAMP(timezone=False), nullable=False),
)

# ------------------------------------------------------------------------------
# connector_tokens — Connector Layer-owned EXCLUSIVELY (INT-01 §1.4). Keyed by
# data_source_id (UNIQUE), not org_id+provider — see Conflict #13.
# refresh_token_encrypted / expires_at / last_refreshed_at are all nullable:
# not every provider grant issues a refresh token or a fixed expiry.
# ------------------------------------------------------------------------------
connector_tokens_table = sa.Table(
    "connector_tokens",
    metadata,
    sa.Column(
        "id",
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    ),
    sa.Column("data_source_id", UUID(as_uuid=True), nullable=False, unique=True),
    sa.Column("provider", provider_enum, nullable=False),
    sa.Column("access_token_encrypted", BYTEA, nullable=False),
    sa.Column("refresh_token_encrypted", BYTEA, nullable=True),
    sa.Column("expires_at", TIMESTAMP(timezone=True), nullable=True),
    sa.Column("last_refreshed_at", TIMESTAMP(timezone=True), nullable=True),
)


platform_enum = sa.Enum(
    "meta",
    "google",
    name="platform_enum",
    create_type=False,
)

campaign_status_enum = sa.Enum(
    "active",
    "paused",
    "removed",
    "unknown",
    name="campaign_status_enum",
    create_type=False,
)


campaigns_table = sa.Table(
    "campaigns",
    metadata,
    sa.Column(
        "id",
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    ),
    sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
    sa.Column("data_source_id", UUID(as_uuid=True), nullable=False),
    sa.Column("external_id", sa.Text),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("platform", platform_enum, nullable=False),
    sa.Column("objective", sa.Text),
    sa.Column("status", campaign_status_enum),
    sa.Column("budget", sa.Numeric),
    sa.Column("start_date", sa.Date),
    sa.Column("end_date", sa.Date),
    sa.Column(
        "updated_at",
        TIMESTAMP(timezone=False),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    ),
)


ad_groups_table = sa.Table(
    "ad_groups",
    metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("campaign_id", UUID(as_uuid=True), nullable=False),
    sa.Column("external_id", sa.Text),
    sa.Column("name", sa.Text),
    sa.Column("status", campaign_status_enum),
)


ads_table = sa.Table(
    "ads",
    metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("ad_group_id", UUID(as_uuid=True), nullable=False),
    sa.Column("external_id", sa.Text),
    sa.Column("name", sa.Text),
    sa.Column("status", campaign_status_enum),
)


creatives_table = sa.Table(
    "creatives",
    metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("ad_id", UUID(as_uuid=True), nullable=False),
    sa.Column("external_id", sa.Text),
    sa.Column("creative_type", sa.String),
    sa.Column("headline", sa.Text),
    sa.Column("asset_url", sa.Text),
)


daily_metrics_table = sa.Table(
    "daily_metrics",
    metadata,
    sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
    sa.Column("campaign_id", UUID(as_uuid=True), primary_key=True),
    sa.Column("date", sa.Date, primary_key=True),
    sa.Column("spend", sa.Numeric, nullable=False),
    sa.Column("clicks", sa.Integer, nullable=False),
    sa.Column("impressions", sa.Integer, nullable=False),
    sa.Column("conversions", sa.Integer, nullable=False),
    sa.Column("revenue", sa.Numeric, nullable=False),
)

ga_events_table = sa.Table(
    "ga_events",
    metadata,
    sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
    sa.Column("campaign_id", UUID(as_uuid=True), primary_key=True),
    sa.Column("date", sa.Date, primary_key=True),
    sa.Column("sessions", sa.Integer, nullable=False),
    sa.Column("bounces", sa.Integer, nullable=False),
    sa.Column("session_duration", sa.Numeric, nullable=True),
)


# AI-owned query handles. Migrations remain the schema authority.

model_runs_table = sa.Table(
    "model_runs",
    metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
    sa.Column("triggered_by_user_id", UUID(as_uuid=True)),
    sa.Column("started_at", TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP")),
    sa.Column(
        "status",
        ENUM(
            "RUNNING",
            "SUCCESS",
            "FAILED",
            "CANCELLED",
            "PARTIAL_SUCCESS",
            name="model_run_status_enum",
            create_type=False,
        ),
        nullable=False,
    ),
    sa.Column("campaigns_analyzed", JSONB),
    sa.Column("error_message", sa.Text),
    sa.Column("completed_at", TIMESTAMP()),
    sa.Column("execution_metadata", JSONB),
)

forecasts_table = sa.Table(
    "forecasts",
    metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("model_run_id", UUID(as_uuid=True), nullable=False),
    sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
    sa.Column("campaign_id", UUID(as_uuid=True), nullable=False),
    sa.Column("metric_name", sa.String, nullable=False),
    sa.Column("forecast_date", sa.Date, nullable=False),
    sa.Column("value", sa.Numeric, nullable=False),
    sa.Column("ci_lower", sa.Numeric),
    sa.Column("ci_upper", sa.Numeric),
    sa.Column("model_used", sa.String),
    sa.Column(
        "created_at", TIMESTAMP(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
    ),
)

anomalies_table = sa.Table(
    "anomalies",
    metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("model_run_id", UUID(as_uuid=True), nullable=False),
    sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
    sa.Column("campaign_id", UUID(as_uuid=True), nullable=False),
    sa.Column("metric_name", sa.String, nullable=False),
    sa.Column("detected_at", TIMESTAMP(), nullable=False),
    sa.Column("anomaly_score", sa.Numeric, nullable=False),
    sa.Column(
        "severity",
        ENUM("low", "medium", "high", name="anomaly_severity_enum", create_type=False),
        nullable=False,
    ),
    sa.Column(
        "direction",
        ENUM("above", "below", name="anomaly_direction_enum", create_type=False),
        nullable=False,
    ),
    sa.Column("detectors_triggered", JSONB),
    sa.Column(
        "created_at", TIMESTAMP(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
    ),
)

recommendations_table = sa.Table(
    "recommendations",
    metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("model_run_id", UUID(as_uuid=True), nullable=False),
    sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
    sa.Column("campaign_id", UUID(as_uuid=True), nullable=False),
    sa.Column("source_anomaly_id", UUID(as_uuid=True)),
    sa.Column("problem", sa.Text, nullable=False),
    sa.Column("evidence", JSONB),
    sa.Column("suggested_action", sa.Text),
    sa.Column("confidence_score", sa.Numeric),
    sa.Column(
        "risk_rating", ENUM("low", "medium", "high", name="risk_rating_enum", create_type=False)
    ),
    sa.Column("severity", sa.Integer),
    sa.Column(
        "created_at", TIMESTAMP(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
    ),
    sa.Column(
        "status",
        ENUM(
            "pending",
            "approved",
            "rejected",
            "marked_done",
            "needs_review",
            name="recommendation_status_enum",
            create_type=False,
        ),
        nullable=False,
    ),
)

action_simulations_table = sa.Table(
    "action_simulations",
    metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("recommendation_id", UUID(as_uuid=True), nullable=False),
    sa.Column(
        "scenario_type",
        ENUM(
            "budget_decrease_20",
            "budget_increase_15",
            "pause",
            name="simulation_scenario_enum",
            create_type=False,
        ),
        nullable=False,
    ),
    sa.Column("projected_spend", sa.Numeric, nullable=False),
    sa.Column("projected_conversions", sa.Numeric, nullable=False),
    sa.Column("projected_cpa", sa.Numeric, nullable=False),
    sa.Column("projected_roas", sa.Numeric, nullable=False),
    sa.Column(
        "created_at", TIMESTAMP(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
    ),
)
