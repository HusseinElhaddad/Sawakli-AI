from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from sawakli.connectors.csv.parser import RawResponse
from sawakli.data.normalization.pipeline import normalize_and_upsert_batch
from sawakli.data.staging.adapters import staged_row_from_csv_dict


@dataclass(frozen=True)
class IngestResult:
    row_count: int
    parse_warnings: list[str]


def ingest_csv_upload(
    db: Session,
    raw_response: RawResponse,
    organization_id: UUID,
    data_source_id: UUID,
    upload_id: UUID,
    endpoint: str,
    raw_payload: dict[str, Any],
    synced_at: datetime,
) -> IngestResult:
    """Persist a parsed CSV upload as an org-scoped, atomic ingest transaction.

    Sequence per the ARCH-04 / raw-response-canonical-handoff contract:
      1. Persist raw payload as an immutable raw_api_responses row (idempotent).
      2. Convert parsed_rows to StagedCampaignRow via the staging adapter.
      3. Normalize and upsert canonical campaigns, daily_metrics, ga_events.
      4. Update data_sources sync_status and last_synced_at only after canonical
         writes commit (freshness ownership belongs to Data, not to the API layer).

    All four steps run inside a single transaction; the caller owns the session
    lifecycle and calls db.commit() / db.rollback() after this function returns.
    """
    # Step 1 — immutable raw evidence (idempotent: duplicate upload_id is a no-op)
    db.execute(
        sa.text(
            "INSERT INTO raw_api_responses "
            "(id, data_source_id, provider, endpoint, payload, fetched_at) "
            "VALUES (:id, :data_source_id, 'csv_demo', :endpoint, "
            "CAST(:payload AS jsonb), :fetched_at) "
            "ON CONFLICT (id) DO NOTHING"
        ),
        {
            "id": upload_id,
            "data_source_id": data_source_id,
            "endpoint": endpoint,
            "payload": json.dumps(raw_payload),
            "fetched_at": synced_at,
        },
    )

    # Step 2+3 — stage and normalize into canonical tables
    staged_rows = [
        staged_row_from_csv_dict(organization_id, data_source_id, row)
        for row in raw_response.parsed_rows
    ]
    normalize_and_upsert_batch(db, staged_rows)

    # Step 4 — freshness: Data owns data_sources.sync_status and last_synced_at
    db.execute(
        sa.text(
            "UPDATE data_sources "
            "SET status = 'demo_data', sync_status = 'success', "
            "last_synced_at = :synced_at, last_error = NULL "
            "WHERE id = :id AND organization_id = :organization_id"
        ),
        {
            "id": data_source_id,
            "organization_id": organization_id,
            "synced_at": synced_at,
        },
    )

    return IngestResult(
        row_count=raw_response.row_count,
        parse_warnings=raw_response.parse_warnings,
    )


def record_sync_failure(
    db: Session,
    data_source_id: UUID,
    organization_id: UUID,
    message: str,
) -> None:
    """Record a failed sync without changing the last successful sync time.

    Data owns the source freshness columns. The caller owns the transaction and
    decides when to commit or roll back.
    """
    db.execute(
        sa.text(
            "UPDATE data_sources "
            "SET sync_status = 'failed', last_error = :message "
            "WHERE id = :id AND organization_id = :organization_id"
        ),
        {
            "id": data_source_id,
            "organization_id": organization_id,
            "message": message,
        },
    )
