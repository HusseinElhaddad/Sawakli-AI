"""Unit tests for the Data-owned CSV ingestion service."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from sawakli.connectors.csv.parser import RawResponse
from sawakli.data.ingestion.service import (
    IngestResult,
    ingest_csv_upload,
    record_sync_failure,
)


def test_ingest_csv_upload_persists_raw_response() -> None:
    """Verify the service persists the raw payload as immutable evidence."""
    organization_id = uuid4()
    data_source_id = uuid4()
    upload_id = uuid4()
    synced_at = datetime(2026, 10, 14, 12, 0, 0)
    endpoint = "csv://upload/test.csv"
    raw_payload = {
        "csv": (
            "date,campaign_name,platform,spend,impressions,clicks,conversions,revenue\n"
            "2026-01-01,Test,meta,100,1000,100,10,200"
        )
    }

    raw_response = RawResponse(
        parsed_rows=[
            {
                "date": "2026-01-01",
                "campaign_name": "Test",
                "platform": "meta",
                "spend": 100.0,
                "impressions": 1000,
                "clicks": 100,
                "conversions": 10,
                "revenue": 200.0,
                "sessions": 0,
                "bounces": 0,
            }
        ],
        row_count=1,
        parse_warnings=[],
    )

    db = MagicMock()

    with patch("sawakli.data.ingestion.service.normalize_and_upsert_batch") as mock_normalize:
        result = ingest_csv_upload(
            db=db,
            raw_response=raw_response,
            organization_id=organization_id,
            data_source_id=data_source_id,
            upload_id=upload_id,
            endpoint=endpoint,
            raw_payload=raw_payload,
            synced_at=synced_at,
        )

    assert isinstance(result, IngestResult)
    assert result.row_count == 1
    assert result.parse_warnings == []

    # Verify db.execute was called for raw_api_responses insert, normalization, and
    # data_sources update.
    assert db.execute.call_count >= 2

    # Verify normalization was called with staged rows
    mock_normalize.assert_called_once()
    staged_rows = mock_normalize.call_args[0][1]
    assert len(staged_rows) == 1


def test_ingest_csv_upload_updates_data_sources_freshness() -> None:
    """Verify the service updates data_sources sync status after canonical writes."""
    organization_id = uuid4()
    data_source_id = uuid4()
    upload_id = uuid4()
    synced_at = datetime(2026, 10, 14, 12, 0, 0)

    raw_response = RawResponse(
        parsed_rows=[
            {
                "date": "2026-01-01",
                "campaign_name": "Campaign A",
                "platform": "google",
                "spend": 50.0,
                "impressions": 500,
                "clicks": 50,
                "conversions": 5,
                "revenue": 100.0,
                "sessions": 0,
                "bounces": 0,
            }
        ],
        row_count=1,
        parse_warnings=[],
    )

    db = MagicMock()

    with patch("sawakli.data.ingestion.service.normalize_and_upsert_batch"):
        result = ingest_csv_upload(
            db=db,
            raw_response=raw_response,
            organization_id=organization_id,
            data_source_id=data_source_id,
            upload_id=upload_id,
            endpoint="csv://upload/test.csv",
            raw_payload={"csv": "test data"},
            synced_at=synced_at,
        )

    # Verify db.execute was called at least twice (raw_api_responses + data_sources update)
    assert db.execute.call_count >= 2

    # Verify the result contains expected data
    assert isinstance(result, IngestResult)
    assert result.row_count == 1


def test_ingest_csv_upload_handles_multiple_rows() -> None:
    """Verify the service processes multiple parsed rows correctly."""
    organization_id = uuid4()
    data_source_id = uuid4()
    upload_id = uuid4()

    raw_response = RawResponse(
        parsed_rows=[
            {
                "date": "2026-01-01",
                "campaign_name": "Campaign A",
                "platform": "meta",
                "spend": 100.0,
                "impressions": 1000,
                "clicks": 100,
                "conversions": 10,
                "revenue": 200.0,
                "sessions": 500,
                "bounces": 100,
            },
            {
                "date": "2026-01-02",
                "campaign_name": "Campaign A",
                "platform": "meta",
                "spend": 75.0,
                "impressions": 750,
                "clicks": 75,
                "conversions": 8,
                "revenue": 150.0,
                "sessions": 400,
                "bounces": 80,
            },
        ],
        row_count=2,
        parse_warnings=[],
    )

    db = MagicMock()

    with patch("sawakli.data.ingestion.service.normalize_and_upsert_batch") as mock_normalize:
        result = ingest_csv_upload(
            db=db,
            raw_response=raw_response,
            organization_id=organization_id,
            data_source_id=data_source_id,
            upload_id=upload_id,
            endpoint="csv://upload/multi.csv",
            raw_payload={"csv": "test"},
            synced_at=datetime(2026, 10, 14, 12, 0, 0),
        )

        assert result.row_count == 2
        assert result.parse_warnings == []

        # Verify 2 rows were staged
        staged_rows = mock_normalize.call_args[0][1]
        assert len(staged_rows) == 2


def test_ingest_csv_upload_propagates_parse_warnings() -> None:
    """Verify the service includes parse warnings in the result."""
    organization_id = uuid4()
    data_source_id = uuid4()
    upload_id = uuid4()

    raw_response = RawResponse(
        parsed_rows=[
            {
                "date": "2026-01-01",
                "campaign_name": "Valid Campaign",
                "platform": "meta",
                "spend": 100.0,
                "impressions": 1000,
                "clicks": 100,
                "conversions": 10,
                "revenue": 200.0,
                "sessions": 0,
                "bounces": 0,
            }
        ],
        row_count=1,
        parse_warnings=["Row 3: 'spend' is not a valid number ('invalid')"],
    )

    db = MagicMock()

    with patch("sawakli.data.ingestion.service.normalize_and_upsert_batch"):
        result = ingest_csv_upload(
            db=db,
            raw_response=raw_response,
            organization_id=organization_id,
            data_source_id=data_source_id,
            upload_id=upload_id,
            endpoint="csv://upload/warnings.csv",
            raw_payload={"csv": "test"},
            synced_at=datetime(2026, 10, 14, 12, 0, 0),
        )

    assert result.parse_warnings == ["Row 3: 'spend' is not a valid number ('invalid')"]


def test_ingest_result_is_frozen() -> None:
    """Verify IngestResult is immutable (frozen dataclass)."""
    result = IngestResult(row_count=5, parse_warnings=[])

    with pytest.raises(AttributeError):
        result.row_count = 10  # type: ignore[misc]


def test_record_sync_failure_updates_only_the_org_scoped_source() -> None:
    organization_id = uuid4()
    data_source_id = uuid4()
    db = MagicMock()

    record_sync_failure(
        db=db,
        data_source_id=data_source_id,
        organization_id=organization_id,
        message="The source could not be refreshed.",
    )

    db.execute.assert_called_once()
    statement, parameters = db.execute.call_args.args
    assert "sync_status = 'failed'" in str(statement)
    assert "last_error = :message" in str(statement)
    assert "id = :id AND organization_id = :organization_id" in str(statement)
    assert parameters == {
        "id": data_source_id,
        "organization_id": organization_id,
        "message": "The source could not be refreshed.",
    }
    db.commit.assert_not_called()
