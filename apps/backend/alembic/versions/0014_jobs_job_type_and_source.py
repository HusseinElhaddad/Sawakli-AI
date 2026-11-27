"""Add job type and source ID to jobs."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014_jobs_job_type_and_source"
down_revision: str | Sequence[str] | None = "0013_ai_execution_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    job_type_enum = sa.Enum("ANALYSIS", "SYNC", name="job_type_enum")
    job_type_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "jobs",
        sa.Column(
            "job_type",
            job_type_enum,
            nullable=False,
            server_default="ANALYSIS",
        ),
    )

    op.add_column(
        "jobs",
        sa.Column(
            "source_id",
            sa.UUID(),
            sa.ForeignKey("data_sources.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )

    op.drop_index("uq_jobs_org_inflight", table_name="jobs")
    op.drop_index("uq_jobs_one_inflight_per_org", table_name="jobs")

    op.create_index(
        "uq_jobs_analysis_inflight_per_org",
        "jobs",
        ["organization_id"],
        unique=True,
        postgresql_where=sa.text("job_type = 'ANALYSIS' AND status IN ('PENDING', 'RUNNING')"),
    )

    op.create_index(
        "uq_jobs_sync_inflight_per_source",
        "jobs",
        ["source_id"],
        unique=True,
        postgresql_where=sa.text("job_type = 'SYNC' AND status IN ('PENDING', 'RUNNING')"),
    )


def downgrade() -> None:
    op.drop_index("uq_jobs_sync_inflight_per_source", table_name="jobs")
    op.drop_index("uq_jobs_analysis_inflight_per_org", table_name="jobs")

    op.create_index(
        "uq_jobs_org_inflight",
        "jobs",
        ["organization_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('PENDING', 'RUNNING')"),
    )

    op.drop_column("jobs", "source_id")
    op.drop_column("jobs", "job_type")

    op.execute("DROP TYPE job_type_enum")
