import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from sawakli.connectors.csv.parser import RawResponse
from sawakli.connectors.errors import ConnectorError
from sawakli.db.models.jobs import Job
from sawakli.db.models.organization import Organization
from sawakli.shared.enums import JobStatus, JobType
from sawakli.worker.orchestration import synch as synch_module
from sawakli.worker.scheduler import loop as loop_module
from sawakli.worker.scheduler.loop import run_once

VALID_CSV = (
    "date,campaign_name,platform,spend,impressions,clicks,conversions,revenue\n"
    "2024-01-15,Error Test Campaign,meta,100.50,1000,50,5,250.00\n"
)


def _create_org(db: Session) -> UUID:
    organization_id = uuid4()
    db.add(Organization(id=organization_id, name="SYNC Error Test Org"))
    db.commit()
    return organization_id


def _create_source_and_job(
    db: Session,
    organization_id: UUID,
    *,
    csv_text: str = VALID_CSV,
) -> tuple[UUID, Job, datetime]:
    source_id = uuid4()
    previous_success = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
    db.execute(
        text(
            "INSERT INTO data_sources "
            "(id, organization_id, provider, status, last_synced_at) "
            "VALUES (:id, :organization_id, 'csv_demo', 'demo_data', :last_synced_at)"
        ),
        {
            "id": source_id,
            "organization_id": organization_id,
            "last_synced_at": previous_success,
        },
    )
    db.execute(
        text(
            "INSERT INTO raw_api_responses "
            "(id, data_source_id, provider, endpoint, payload, fetched_at) "
            "VALUES (:id, :data_source_id, 'csv_demo', :endpoint, "
            "CAST(:payload AS jsonb), CURRENT_TIMESTAMP)"
        ),
        {
            "id": uuid4(),
            "data_source_id": source_id,
            "endpoint": "csv://test/errors.csv",
            "payload": json.dumps({"csv": csv_text}),
        },
    )
    job = Job(
        id=uuid4(),
        organization_id=organization_id,
        campaign_ids=None,
        triggered_by_user_id=None,
        status=JobStatus.RUNNING.value,
        priority="LOW",
        job_type=JobType.SYNC,
        source_id=source_id,
        created_at=datetime.now(UTC),
        claimed_at=datetime.now(UTC),
        retry_count=0,
        max_retries=3,
        next_retry_at=None,
        timeout_seconds=300,
        model_run_id=None,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return source_id, job, previous_success


def _source_error(db: Session, source_id: UUID) -> str | None:
    return db.execute(
        text("SELECT last_error FROM data_sources WHERE id = :id"),
        {"id": source_id},
    ).scalar_one()


def _campaign_count(db: Session, organization_id: UUID) -> int:
    return db.execute(
        text("SELECT COUNT(*) FROM campaigns WHERE organization_id = :id"),
        {"id": organization_id},
    ).scalar_one()


def _cleanup(db: Session, organization_id: UUID) -> None:
    db.execute(delete(Job).where(Job.organization_id == organization_id))
    db.execute(
        text("DELETE FROM campaigns WHERE organization_id = :id"),
        {"id": organization_id},
    )
    db.execute(
        text(
            "DELETE FROM raw_api_responses WHERE data_source_id IN "
            "(SELECT id FROM data_sources WHERE organization_id = :id)"
        ),
        {"id": organization_id},
    )
    db.execute(
        text("DELETE FROM data_sources WHERE organization_id = :id"), {"id": organization_id}
    )
    db.execute(delete(Organization).where(Organization.id == organization_id))
    db.commit()


def _valid_response() -> RawResponse:
    return RawResponse(
        parsed_rows=[
            {
                "date": "2024-01-15",
                "campaign_name": "Error Test Campaign",
                "platform": "meta",
                "spend": 100.5,
                "impressions": 1000,
                "clicks": 50,
                "conversions": 5,
                "revenue": 250.0,
                "sessions": 0,
                "bounces": 0,
            }
        ],
        row_count=1,
        parse_warnings=[],
    )


def test_retryable_connector_error_retries_twice_then_fails(
    db_session: Session,
    monkeypatch,
) -> None:
    organization_id = _create_org(db_session)
    attempts = 0

    def retryable_failure(db: Session, source: object) -> ConnectorError:
        nonlocal attempts
        attempts += 1
        return ConnectorError(
            kind="rate_limit_exceeded",
            message="Provider details stay out of source freshness.",
            user_message="The provider is temporarily unavailable.",
            retryable=True,
        )

    try:
        source_id, job, previous_success = _create_source_and_job(
            db_session,
            organization_id,
        )
        monkeypatch.setattr(loop_module, "_last_sync_check", datetime.now(UTC))
        monkeypatch.setattr(synch_module, "fetch_raw", retryable_failure)

        run_once(db_session)
        db_session.refresh(job)
        assert job.status == JobStatus.PENDING.value
        assert job.retry_count == 1
        assert job.next_retry_at is not None
        assert datetime.now(UTC) <= job.next_retry_at <= datetime.now(UTC) + timedelta(seconds=3)
        assert _source_error(db_session, source_id) == "The provider is temporarily unavailable."

        for expected_retry_count in (2, 3):
            job.next_retry_at = datetime.now(UTC) - timedelta(seconds=1)
            db_session.commit()
            # One tick claims the retry; the following tick executes it.
            run_once(db_session)
            db_session.refresh(job)
            assert job.status == JobStatus.RUNNING.value
            run_once(db_session)
            db_session.refresh(job)
            assert job.retry_count == expected_retry_count

        assert job.status == JobStatus.FAILED.value
        assert attempts == 3
        run_once(db_session)
        assert attempts == 3
        source = db_session.execute(
            text("SELECT last_synced_at FROM data_sources WHERE id = :id"),
            {"id": source_id},
        ).scalar_one()
        assert source == previous_success
    finally:
        _cleanup(db_session, organization_id)


def test_non_retryable_parse_error_fails_without_retry(
    db_session: Session,
    monkeypatch,
) -> None:
    organization_id = _create_org(db_session)

    try:
        source_id, job, previous_success = _create_source_and_job(
            db_session,
            organization_id,
            csv_text="date,campaign_name\n2024-01-15,Incomplete\n",
        )
        monkeypatch.setattr(loop_module, "_last_sync_check", datetime.now(UTC))

        run_once(db_session)
        db_session.refresh(job)

        assert job.status == JobStatus.FAILED.value
        assert job.retry_count == 0
        assert _source_error(db_session, source_id) is not None
        source = db_session.execute(
            text("SELECT sync_status, last_synced_at FROM data_sources WHERE id = :id"),
            {"id": source_id},
        ).one()
        assert source.sync_status == "failed"
        assert source.last_synced_at == previous_success
    finally:
        _cleanup(db_session, organization_id)


def test_unexpected_ingest_exception_rolls_back_and_stores_generic_message(
    db_session: Session,
    monkeypatch,
) -> None:
    organization_id = _create_org(db_session)

    def raise_ingest_error(**kwargs: object) -> None:
        raise RuntimeError("synthetic private parser payload")

    try:
        source_id, job, previous_success = _create_source_and_job(
            db_session,
            organization_id,
        )
        monkeypatch.setattr(loop_module, "_last_sync_check", datetime.now(UTC))
        monkeypatch.setattr(synch_module, "fetch_raw", lambda db, source: _valid_response())
        monkeypatch.setattr(synch_module, "ingest_csv_upload", raise_ingest_error)

        run_once(db_session)
        db_session.refresh(job)

        assert job.status == JobStatus.FAILED.value
        assert job.retry_count == 0
        assert _source_error(db_session, source_id) == "Unexpected sync error."
        assert "synthetic private parser payload" not in (
            _source_error(db_session, source_id) or ""
        )
        assert _campaign_count(db_session, organization_id) == 0
        source = db_session.execute(
            text("SELECT sync_status, last_synced_at FROM data_sources WHERE id = :id"),
            {"id": source_id},
        ).one()
        assert source.sync_status == "failed"
        assert source.last_synced_at == previous_success
    finally:
        _cleanup(db_session, organization_id)
