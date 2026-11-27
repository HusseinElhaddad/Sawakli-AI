"""Identify data sources that are due for synchronization."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import (
    and_,
    column,
    exists,
    not_,
    or_,
    select,
    table,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Session

from sawakli.core.config import settings
from sawakli.db.models.jobs import Job
from sawakli.db.tables import data_sources_table
from sawakli.shared.enums import JobType


@dataclass(frozen=True)
class DueSource:
    data_source_id: UUID
    organization_id: UUID


raw_api_responses = table(
    "raw_api_responses",
    column("data_source_id", PGUUID(as_uuid=True)),
)


def find_due_sources(
    db: Session,
    now: datetime,
) -> list[DueSource]:
    """Return sources eligible for synchronization without modifying data."""

    refresh_interval = timedelta(seconds=settings.sync_refresh_every_seconds)
    cutoff = now - refresh_interval

    has_stored_upload = exists(
        select(1)
        .select_from(raw_api_responses)
        .where(raw_api_responses.c.data_source_id == data_sources_table.c.id)
    )

    has_open_or_recent_sync = exists(
        select(1)
        .select_from(Job)
        .where(
            and_(
                Job.job_type == JobType.SYNC,
                Job.source_id == data_sources_table.c.id,
                or_(
                    Job.status.in_(("PENDING", "RUNNING")),
                    Job.created_at >= cutoff.replace(tzinfo=UTC),
                ),
            )
        )
    )

    statement = select(
        data_sources_table.c.id,
        data_sources_table.c.organization_id,
    ).where(
        data_sources_table.c.provider == "csv_demo",
        has_stored_upload,
        or_(
            data_sources_table.c.last_synced_at.is_(None),
            data_sources_table.c.last_synced_at < cutoff,
        ),
        not_(has_open_or_recent_sync),
    )

    rows = db.execute(statement).all()

    return [
        DueSource(
            data_source_id=row.id,
            organization_id=row.organization_id,
        )
        for row in rows
    ]
