"""Run one SYNC job through the Connector parser and Data ingestion path."""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from sawakli.connectors.csv.parser import RawResponse, parse_csv_upload
from sawakli.connectors.errors import ConnectorError
from sawakli.data.ingestion import ingest_csv_upload, record_sync_failure
from sawakli.db.models.jobs import Job
from sawakli.db.tables import data_sources_table
from sawakli.shared.enums import JobStatus

logger = logging.getLogger(__name__)

NO_SOURCE_DATA = "no_source_data"
NO_VALID_ROWS = "no_valid_rows"


@dataclass(frozen=True)
class StoredUpload:
    id: UUID
    endpoint: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class SyncSource:
    id: UUID
    organization_id: UUID
    provider: str
    stored_upload: StoredUpload | None = None


def _no_source_data_error() -> ConnectorError:
    return ConnectorError(
        kind=NO_SOURCE_DATA,
        message="No stored upload exists for this data source.",
        user_message="This source has no stored data to refresh.",
        retryable=False,
    )


def _no_valid_rows_error() -> ConnectorError:
    return ConnectorError(
        kind=NO_VALID_ROWS,
        message="The stored upload contained no valid rows.",
        user_message="No valid rows were found in this file.",
        retryable=False,
    )


def _fail(
    db: Session,
    job: Job,
    source_id: UUID | None,
    error: ConnectorError,
) -> JobStatus:
    logger.warning(
        "sync failed job_id=%s source_id=%s kind=%s",
        job.id,
        source_id,
        error.kind,
    )
    if source_id is not None:
        record_sync_failure(
            db=db,
            data_source_id=source_id,
            organization_id=job.organization_id,
            message=error.user_message,
        )
    if error.retryable:
        return JobStatus.ERROR
    return JobStatus.FAILED


def _load_owned_source(db: Session, job: Job) -> SyncSource | None:
    if job.source_id is None:
        return None

    statement = select(
        data_sources_table.c.id,
        data_sources_table.c.organization_id,
        data_sources_table.c.provider,
    ).where(
        data_sources_table.c.id == job.source_id,
        data_sources_table.c.organization_id == job.organization_id,
    )
    row = db.execute(statement).one_or_none()
    if row is None:
        return None

    return SyncSource(
        id=row.id,
        organization_id=row.organization_id,
        provider=row.provider,
    )


def _latest_stored_upload(
    db: Session,
    data_source_id: UUID,
) -> StoredUpload | None:
    row = (
        db.execute(
            text(
                "SELECT id, endpoint, payload "
                "FROM raw_api_responses "
                "WHERE data_source_id = :data_source_id "
                "ORDER BY fetched_at DESC "
                "LIMIT 1"
            ),
            {"data_source_id": data_source_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        return None

    payload = row["payload"]
    if not isinstance(payload, dict):
        payload = {}

    return StoredUpload(
        id=row["id"],
        endpoint=row["endpoint"],
        payload=payload,
    )


def fetch_raw(
    db: Session,
    source: SyncSource,
) -> RawResponse | ConnectorError:
    """Load the source's latest stored CSV and parse it.

    Isolated so a real connector (or a test double) can replace this later.
    """
    stored = source.stored_upload or _latest_stored_upload(db, source.id)
    if stored is None:
        return _no_source_data_error()

    csv_text = stored.payload.get("csv")
    if not isinstance(csv_text, str):
        return _no_source_data_error()

    return parse_csv_upload(
        io.BytesIO(csv_text.encode("utf-8")),
        source.organization_id,
        stored.id,
    )


def run_sync_job(db: Session, job: Job) -> JobStatus:
    """Fetch, persist, and return the status the loop should apply.

    This function never writes job status and never commits. Data-layer
    ingestion owns success freshness; record_sync_failure owns failure freshness.
    """
    failure: ConnectorError | None = None
    try:
        source = _load_owned_source(db, job)
        if source is None:
            failure = _no_source_data_error()
        else:
            # Pin one upload so parsed rows and ingested metadata cannot diverge
            # if a newer upload arrives while parsing is in progress.
            stored = _latest_stored_upload(db, source.id)
            if stored is None:
                failure = _no_source_data_error()
            else:
                source_with_pinned_upload = SyncSource(
                    id=source.id,
                    organization_id=source.organization_id,
                    provider=source.provider,
                    stored_upload=stored,
                )
                result = fetch_raw(db, source_with_pinned_upload)
                if isinstance(result, ConnectorError):
                    failure = result
                elif result.row_count == 0:
                    failure = _no_valid_rows_error()
                else:
                    db.refresh(job, attribute_names=["status"])
                    if JobStatus(job.status) == JobStatus.CANCELLED:
                        return JobStatus.CANCELLED

                    synced_at = datetime.now(UTC).replace(tzinfo=None)
                    with db.begin_nested():
                        ingest_csv_upload(
                            db=db,
                            raw_response=result,
                            organization_id=source.organization_id,
                            data_source_id=source.id,
                            upload_id=stored.id,
                            endpoint=stored.endpoint,
                            raw_payload=stored.payload,
                            synced_at=synced_at,
                        )
    except Exception:
        failure = ConnectorError(
            kind="unexpected",
            message="Unexpected sync error.",
            user_message="Unexpected sync error.",
            retryable=False,
        )

    if failure is not None:
        return _fail(db, job, job.source_id, failure)

    return JobStatus.SUCCESS
