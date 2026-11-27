import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from sawakli.connectors.csv.parser import RawResponse
from sawakli.db.models.jobs import Job
from sawakli.db.models.organization import Organization
from sawakli.shared.enums import JobStatus, JobType
from sawakli.worker.orchestration import synch as synch_module
from sawakli.worker.orchestration.synch import run_sync_job

VALID_CSV = (
    "date,campaign_name,platform,spend,impressions,clicks,conversions,"
    "revenue,sessions,bounces\n"
    "2024-01-15,Spring Sale,meta,100.50,1000,50,5,250.00,300,20\n"
    "2024-01-16,Summer Blast,google,200.00,2000,80,10,500.00,400,30\n"
)


def _create_org(db: Session, name: str) -> UUID:
    organization_id = uuid4()
    db.add(Organization(id=organization_id, name=name))
    db.commit()
    return organization_id


def _create_source_with_upload(
    db: Session,
    organization_id: UUID,
    *,
    csv_text: str = VALID_CSV,
    last_synced_at: datetime | None = None,
) -> tuple[UUID, UUID]:
    data_source_id = uuid4()
    upload_id = uuid4()

    db.execute(
        text(
            "INSERT INTO data_sources "
            "(id, organization_id, provider, status, last_synced_at) "
            "VALUES (:id, :organization_id, 'csv_demo', 'demo_data', "
            ":last_synced_at)"
        ),
        {
            "id": data_source_id,
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
            "id": upload_id,
            "data_source_id": data_source_id,
            "endpoint": "csv://test/sync.csv",
            "payload": json.dumps({"csv": csv_text}),
        },
    )
    db.commit()
    return data_source_id, upload_id


def _create_running_sync_job(
    db: Session,
    organization_id: UUID,
    source_id: UUID,
) -> Job:
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
    return job


def _source_row(db: Session, data_source_id: UUID) -> dict[str, object]:
    row = (
        db.execute(
            text("SELECT sync_status, last_synced_at, last_error FROM data_sources WHERE id = :id"),
            {"id": data_source_id},
        )
        .mappings()
        .one()
    )
    return dict(row)


def _count_campaigns(db: Session, organization_id: UUID) -> int:
    return db.execute(
        text("SELECT COUNT(*) FROM campaigns WHERE organization_id = :organization_id"),
        {"organization_id": organization_id},
    ).scalar_one()


def _count_daily_metrics(db: Session, organization_id: UUID) -> int:
    return db.execute(
        text("SELECT COUNT(*) FROM daily_metrics WHERE organization_id = :organization_id"),
        {"organization_id": organization_id},
    ).scalar_one()


def _count_raw_rows(db: Session, data_source_id: UUID) -> int:
    return db.execute(
        text("SELECT COUNT(*) FROM raw_api_responses WHERE data_source_id = :data_source_id"),
        {"data_source_id": data_source_id},
    ).scalar_one()


def _cleanup(db: Session, organization_ids: list[UUID]) -> None:
    db.execute(delete(Job).where(Job.organization_id.in_(organization_ids)))
    db.execute(
        text("DELETE FROM campaigns WHERE organization_id = ANY(:organization_ids)"),
        {"organization_ids": organization_ids},
    )
    db.execute(
        text(
            "DELETE FROM raw_api_responses "
            "WHERE data_source_id IN "
            "(SELECT id FROM data_sources "
            "WHERE organization_id = ANY(:organization_ids))"
        ),
        {"organization_ids": organization_ids},
    )
    db.execute(
        text("DELETE FROM data_sources WHERE organization_id = ANY(:organization_ids)"),
        {"organization_ids": organization_ids},
    )
    db.execute(delete(Organization).where(Organization.id.in_(organization_ids)))
    db.commit()


def test_successful_sync_persists_campaigns_and_freshness(
    db_session: Session,
) -> None:
    organization_id = _create_org(db_session, "SYNC Success Org")
    previous_synced_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=2)

    try:
        data_source_id, _upload_id = _create_source_with_upload(
            db_session,
            organization_id,
            last_synced_at=previous_synced_at,
        )
        job = _create_running_sync_job(
            db_session,
            organization_id,
            data_source_id,
        )
        raw_before = _count_raw_rows(db_session, data_source_id)

        status = run_sync_job(db_session, job)
        db_session.commit()

        assert status == JobStatus.SUCCESS
        assert _count_campaigns(db_session, organization_id) == 2
        assert _count_daily_metrics(db_session, organization_id) == 2
        assert _count_raw_rows(db_session, data_source_id) == raw_before

        source = _source_row(db_session, data_source_id)
        assert source["sync_status"] == "success"
        assert source["last_synced_at"] is not None
        assert source["last_synced_at"] > previous_synced_at
        assert source["last_error"] is None
    finally:
        _cleanup(db_session, [organization_id])


def test_running_sync_twice_does_not_duplicate_campaigns(
    db_session: Session,
) -> None:
    organization_id = _create_org(db_session, "SYNC Dedupe Org")

    try:
        data_source_id, _upload_id = _create_source_with_upload(
            db_session,
            organization_id,
        )
        job = _create_running_sync_job(
            db_session,
            organization_id,
            data_source_id,
        )

        assert run_sync_job(db_session, job) == JobStatus.SUCCESS
        db_session.commit()
        first_count = _count_campaigns(db_session, organization_id)

        assert run_sync_job(db_session, job) == JobStatus.SUCCESS
        db_session.commit()

        assert first_count == 2
        assert _count_campaigns(db_session, organization_id) == first_count
    finally:
        _cleanup(db_session, [organization_id])


def test_cancelled_job_writes_nothing(
    db_session: Session,
    monkeypatch,
) -> None:
    organization_id = _create_org(db_session, "SYNC Cancel Org")

    try:
        data_source_id, _upload_id = _create_source_with_upload(
            db_session,
            organization_id,
        )
        job = _create_running_sync_job(
            db_session,
            organization_id,
            data_source_id,
        )

        def fetch_then_cancel(db: Session, source: object) -> RawResponse:
            db.execute(
                text("UPDATE jobs SET status = 'CANCELLED' WHERE id = :id"),
                {"id": job.id},
            )
            db.flush()
            return RawResponse(
                parsed_rows=[
                    {
                        "date": "2024-01-15",
                        "campaign_name": "Should Not Persist",
                        "platform": "meta",
                        "spend": 1.0,
                        "impressions": 1,
                        "clicks": 1,
                        "conversions": 1,
                        "revenue": 1.0,
                        "sessions": 1,
                        "bounces": 0,
                    }
                ],
                row_count=1,
                parse_warnings=[],
            )

        monkeypatch.setattr(synch_module, "fetch_raw", fetch_then_cancel)

        status = run_sync_job(db_session, job)
        db_session.commit()

        assert status == JobStatus.CANCELLED
        assert _count_campaigns(db_session, organization_id) == 0
        source = _source_row(db_session, data_source_id)
        assert source["sync_status"] is None
        assert source["last_synced_at"] is None
    finally:
        _cleanup(db_session, [organization_id])


def test_sync_ingests_the_upload_that_was_parsed(
    db_session: Session,
    monkeypatch,
) -> None:
    organization_id = _create_org(db_session, "SYNC Pinned Upload Org")

    try:
        data_source_id, original_upload_id = _create_source_with_upload(
            db_session,
            organization_id,
        )
        job = _create_running_sync_job(
            db_session,
            organization_id,
            data_source_id,
        )
        inserted_upload_ids: list[UUID] = []

        def parse_and_add_newer_upload(
            file_stream: object,
            org_id: object,
            upload_id: object,
        ) -> RawResponse:
            assert upload_id == original_upload_id
            newer_upload_id = uuid4()
            inserted_upload_ids.append(newer_upload_id)
            db_session.execute(
                text(
                    "INSERT INTO raw_api_responses "
                    "(id, data_source_id, provider, endpoint, payload, fetched_at) "
                    "VALUES (:id, :data_source_id, 'csv_demo', :endpoint, "
                    "CAST(:payload AS jsonb), :fetched_at)"
                ),
                {
                    "id": newer_upload_id,
                    "data_source_id": data_source_id,
                    "endpoint": "csv://test/newer.csv",
                    "payload": json.dumps({"csv": "newer upload"}),
                    "fetched_at": datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=1),
                },
            )
            return RawResponse(
                parsed_rows=[
                    {
                        "date": "2024-01-15",
                        "campaign_name": "Parsed Original Upload",
                        "platform": "meta",
                        "spend": 1.0,
                        "impressions": 1,
                        "clicks": 1,
                        "conversions": 1,
                        "revenue": 1.0,
                        "sessions": 1,
                        "bounces": 0,
                    }
                ],
                row_count=1,
                parse_warnings=[],
            )

        ingested_uploads: list[tuple[UUID, str, dict[str, object]]] = []
        real_ingest = synch_module.ingest_csv_upload

        def record_ingest_upload(**kwargs: object) -> object:
            ingested_uploads.append(
                (
                    kwargs["upload_id"],
                    kwargs["endpoint"],
                    kwargs["raw_payload"],
                )
            )
            return real_ingest(**kwargs)

        monkeypatch.setattr(synch_module, "parse_csv_upload", parse_and_add_newer_upload)
        monkeypatch.setattr(synch_module, "ingest_csv_upload", record_ingest_upload)

        status = run_sync_job(db_session, job)
        db_session.commit()

        assert status == JobStatus.SUCCESS
        assert len(inserted_upload_ids) == 1
        assert ingested_uploads == [(original_upload_id, "csv://test/sync.csv", {"csv": VALID_CSV})]
        assert _count_raw_rows(db_session, data_source_id) == 2
        assert _count_campaigns(db_session, organization_id) == 1
    finally:
        _cleanup(db_session, [organization_id])


def test_sync_does_not_touch_another_organization(
    db_session: Session,
) -> None:
    org_a = _create_org(db_session, "SYNC Org A")
    org_b = _create_org(db_session, "SYNC Org B")

    try:
        source_a, _upload_a = _create_source_with_upload(db_session, org_a)
        source_b, _upload_b = _create_source_with_upload(db_session, org_b)
        job_a = _create_running_sync_job(db_session, org_a, source_a)

        status = run_sync_job(db_session, job_a)
        db_session.commit()

        assert status == JobStatus.SUCCESS
        assert _count_campaigns(db_session, org_a) == 2
        assert _count_campaigns(db_session, org_b) == 0

        source_b_row = _source_row(db_session, source_b)
        assert source_b_row["sync_status"] is None
        assert source_b_row["last_synced_at"] is None
        assert _count_raw_rows(db_session, source_b) == 1
    finally:
        _cleanup(db_session, [org_a, org_b])
