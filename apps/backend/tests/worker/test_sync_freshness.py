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
from sawakli.worker.orchestration.synch import run_sync_job
from sawakli.worker.scheduler import loop as loop_module
from sawakli.worker.scheduler.loop import run_once

VALID_CSV = (
    "date,campaign_name,platform,spend,impressions,clicks,conversions,revenue\n"
    "2024-01-15,Freshness Campaign,meta,100.50,1000,50,5,250.00\n"
)


def _create_org(db: Session, name: str) -> UUID:
    organization_id = uuid4()
    db.add(Organization(id=organization_id, name=name))
    db.commit()
    return organization_id


def _create_source(db: Session, organization_id: UUID) -> tuple[UUID, datetime]:
    source_id = uuid4()
    last_synced_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
    db.execute(
        text(
            "INSERT INTO data_sources "
            "(id, organization_id, provider, status, last_synced_at) "
            "VALUES (:id, :organization_id, 'csv_demo', 'demo_data', :last_synced_at)"
        ),
        {
            "id": source_id,
            "organization_id": organization_id,
            "last_synced_at": last_synced_at,
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
            "endpoint": "csv://test/freshness.csv",
            "payload": json.dumps({"csv": VALID_CSV}),
        },
    )
    db.commit()
    return source_id, last_synced_at


def _create_running_sync_job(
    db: Session,
    organization_id: UUID,
    source_id: UUID,
    *,
    timeout_seconds: int = 300,
    claimed_at: datetime | None = None,
) -> Job:
    now = datetime.now(UTC)
    job = Job(
        id=uuid4(),
        organization_id=organization_id,
        campaign_ids=None,
        triggered_by_user_id=None,
        status=JobStatus.RUNNING.value,
        priority="LOW",
        job_type=JobType.SYNC,
        source_id=source_id,
        created_at=now,
        claimed_at=claimed_at or now,
        retry_count=0,
        max_retries=3,
        next_retry_at=None,
        timeout_seconds=timeout_seconds,
        model_run_id=None,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _source_freshness(db: Session, source_id: UUID) -> dict[str, object]:
    row = (
        db.execute(
            text("SELECT sync_status, last_synced_at, last_error FROM data_sources WHERE id = :id"),
            {"id": source_id},
        )
        .mappings()
        .one()
    )
    return dict(row)


def _cleanup(db: Session, organization_ids: list[UUID]) -> None:
    db.execute(delete(Job).where(Job.organization_id.in_(organization_ids)))
    db.execute(
        text("DELETE FROM campaigns WHERE organization_id = ANY(:organization_ids)"),
        {"organization_ids": organization_ids},
    )
    db.execute(
        text(
            "DELETE FROM raw_api_responses WHERE data_source_id IN "
            "(SELECT id FROM data_sources WHERE organization_id = ANY(:organization_ids))"
        ),
        {"organization_ids": organization_ids},
    )
    db.execute(
        text("DELETE FROM data_sources WHERE organization_id = ANY(:organization_ids)"),
        {"organization_ids": organization_ids},
    )
    db.execute(delete(Organization).where(Organization.id.in_(organization_ids)))
    db.commit()


def test_failure_then_success_updates_only_the_owned_source(
    db_session: Session,
    monkeypatch,
) -> None:
    organization_id = _create_org(db_session, "SYNC Freshness Org")
    other_organization_id = _create_org(db_session, "Other Freshness Org")

    try:
        source_id, previous_success = _create_source(db_session, organization_id)
        other_source_id, other_previous_success = _create_source(
            db_session,
            other_organization_id,
        )
        job = _create_running_sync_job(db_session, organization_id, source_id)
        monkeypatch.setattr(
            synch_module,
            "fetch_raw",
            lambda db, source: ConnectorError(
                kind="invalid_header",
                message="Detailed parser failure.",
                user_message="The uploaded file is missing required columns.",
                retryable=False,
            ),
        )

        assert run_sync_job(db_session, job) == JobStatus.FAILED
        db_session.commit()

        failed_freshness = _source_freshness(db_session, source_id)
        assert failed_freshness["sync_status"] == "failed"
        assert failed_freshness["last_error"] == "The uploaded file is missing required columns."
        assert failed_freshness["last_synced_at"] == previous_success

        other_freshness = _source_freshness(db_session, other_source_id)
        assert other_freshness["sync_status"] is None
        assert other_freshness["last_error"] is None
        assert other_freshness["last_synced_at"] == other_previous_success

        valid_response = RawResponse(
            parsed_rows=[
                {
                    "date": "2024-01-15",
                    "campaign_name": "Freshness Campaign",
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
        monkeypatch.setattr(synch_module, "fetch_raw", lambda db, source: valid_response)

        assert run_sync_job(db_session, job) == JobStatus.SUCCESS
        db_session.commit()

        success_freshness = _source_freshness(db_session, source_id)
        assert success_freshness["sync_status"] == "success"
        assert success_freshness["last_error"] is None
        assert success_freshness["last_synced_at"] > previous_success
    finally:
        _cleanup(db_session, [organization_id, other_organization_id])


def test_timed_out_sync_records_failure_before_retry(
    db_session: Session,
    monkeypatch,
) -> None:
    organization_id = _create_org(db_session, "SYNC Timeout Freshness Org")

    try:
        source_id, previous_success = _create_source(db_session, organization_id)
        old_claim_time = datetime.now(UTC) - timedelta(minutes=2)
        job = _create_running_sync_job(
            db_session,
            organization_id,
            source_id,
            timeout_seconds=1,
            claimed_at=old_claim_time,
        )
        monkeypatch.setattr(loop_module, "_last_sync_check", datetime.now(UTC))

        run_once(db_session)
        db_session.refresh(job)

        assert job.status == JobStatus.PENDING.value
        assert job.retry_count == 1
        assert job.next_retry_at is not None
        assert job.next_retry_at > datetime.now(UTC)
        freshness = _source_freshness(db_session, source_id)
        assert freshness["sync_status"] == "failed"
        assert freshness["last_error"] == "The sync took too long and will be retried."
        assert freshness["last_synced_at"] == previous_success
    finally:
        _cleanup(db_session, [organization_id])
