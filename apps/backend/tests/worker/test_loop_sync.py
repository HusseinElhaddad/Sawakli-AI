import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import UUID, uuid4

from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from sawakli.db.models.jobs import Job
from sawakli.db.models.organization import Organization
from sawakli.shared.enums import JobStatus, JobType
from sawakli.worker.scheduler import loop as loop_module
from sawakli.worker.scheduler.loop import run_once

VALID_CSV = (
    "date,campaign_name,platform,spend,impressions,clicks,conversions,"
    "revenue,sessions,bounces\n"
    "2024-01-15,Spring Sale,meta,100.50,1000,50,5,250.00,300,20\n"
    "2024-01-16,Summer Blast,google,200.00,2000,80,10,500.00,400,30\n"
)


# Creates an organization needed by the database foreign keys.
def _create_org(db: Session, name: str) -> UUID:
    organization_id = uuid4()
    db.add(Organization(id=organization_id, name=name))
    db.commit()
    return organization_id


# Creates a CSV data source and a stored raw upload.
# The stored upload makes the source eligible for synchronization.
def _create_due_source(
    db: Session,
    organization_id: UUID,
    *,
    csv_text: str = "date,campaign_name\n",
) -> UUID:
    data_source_id = uuid4()

    db.execute(
        text(
            "INSERT INTO data_sources "
            "(id, organization_id, provider, status) "
            "VALUES (:id, :organization_id, 'csv_demo', 'demo_data')"
        ),
        {
            "id": data_source_id,
            "organization_id": organization_id,
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
            "data_source_id": data_source_id,
            "endpoint": "csv://test/sync.csv",
            "payload": json.dumps({"csv": csv_text}),
        },
    )

    db.commit()
    return data_source_id


# Creates a RUNNING analysis job with the requested priority and age.
def _create_running_job(
    db: Session,
    organization_id: UUID,
    *,
    priority: str,
    created_at: datetime,
) -> Job:
    job = Job(
        id=uuid4(),
        organization_id=organization_id,
        campaign_ids=None,
        triggered_by_user_id=None,
        status=JobStatus.RUNNING.value,
        priority=priority,
        job_type=JobType.ANALYSIS,
        source_id=None,
        created_at=created_at,
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


# Removes all test data belonging to the supplied organizations.
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


# A due source should produce exactly one LOW-priority SYNC job.
def test_due_source_creates_one_low_sync_job(
    db_session: Session,
    monkeypatch,
) -> None:
    # Reset the scheduler timer so this test always checks for due sources.
    monkeypatch.setattr(loop_module, "_last_sync_check", None)

    organization_id = _create_org(db_session, "SYNC Scheduling Org")

    try:
        data_source_id = _create_due_source(db_session, organization_id)

        # Run one scheduler tick.
        run_once(db_session)

        # Find SYNC jobs created for this specific source.
        jobs = (
            db_session.query(Job)
            .filter(
                Job.organization_id == organization_id,
                Job.job_type == JobType.SYNC,
                Job.source_id == data_source_id,
            )
            .all()
        )

        assert len(jobs) == 1
        assert jobs[0].priority == "LOW"
    finally:
        _cleanup(db_session, [organization_id])


# A second scheduler tick should not create a duplicate SYNC job.
def test_second_tick_does_not_create_another_sync_job(
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(loop_module, "_last_sync_check", None)

    # Mark executed jobs as successful so the first tick can finish normally.
    monkeypatch.setattr(
        loop_module,
        "execute_job",
        lambda _: JobStatus.SUCCESS,
    )

    organization_id = _create_org(db_session, "SYNC Interval Org")

    try:
        data_source_id = _create_due_source(db_session, organization_id)

        # The first tick schedules the SYNC job.
        run_once(db_session)

        # The immediate second tick should not schedule another one.
        run_once(db_session)

        job_count = (
            db_session.query(Job)
            .filter(
                Job.organization_id == organization_id,
                Job.job_type == JobType.SYNC,
                Job.source_id == data_source_id,
            )
            .count()
        )

        assert job_count == 1
    finally:
        _cleanup(db_session, [organization_id])


# Two workers checking the same source simultaneously should create only one job.
def test_concurrent_workers_create_one_sync_job_per_source(
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(loop_module, "_last_sync_check", None)

    organization_id = _create_org(db_session, "Concurrent SYNC Org")

    try:
        data_source_id = _create_due_source(db_session, organization_id)

        from sawakli.db.session import SessionLocal

        # Make both workers start their scheduler checks at nearly the same time.
        barrier = Barrier(2)

        def worker_attempt() -> None:
            # Each worker uses its own database session.
            session = SessionLocal()
            try:
                barrier.wait()
                run_once(session)
            finally:
                session.close()

        # Run two workers concurrently against the same source.
        with ThreadPoolExecutor(max_workers=2) as executor:
            list(executor.map(lambda _: worker_attempt(), range(2)))

        # Verify that the database contains only one SYNC job for this source.
        job_count = (
            db_session.query(Job)
            .filter(
                Job.organization_id == organization_id,
                Job.job_type == JobType.SYNC,
                Job.source_id == data_source_id,
            )
            .count()
        )

        assert job_count == 1
    finally:
        _cleanup(db_session, [organization_id])


# HIGH-priority RUNNING jobs should execute before older LOW-priority jobs.
def test_running_high_job_executes_before_older_running_low_job(
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(loop_module, "_last_sync_check", None)

    high_org_id = _create_org(db_session, "HIGH Priority Org")
    low_org_id = _create_org(db_session, "LOW Priority Org")

    try:
        now = datetime.now(UTC)

        # The HIGH job is newer than the LOW job.
        high_job = _create_running_job(
            db_session,
            high_org_id,
            priority="HIGH",
            created_at=now - timedelta(minutes=5),
        )

        # The LOW job is older, but should still execute second.
        low_job = _create_running_job(
            db_session,
            low_org_id,
            priority="LOW",
            created_at=now - timedelta(minutes=10),
        )

        # Record execution order so the test can verify which job ran first.
        executed_job_ids: list[UUID] = []

        def record_execution(job: Job) -> JobStatus:
            executed_job_ids.append(job.id)
            return JobStatus.SUCCESS

        # Replace execution with a recorder to observe which job is selected.
        monkeypatch.setattr(
            loop_module,
            "execute_job",
            record_execution,
        )

        run_once(db_session)

        # Only the HIGH job should have been selected in this tick.
        assert executed_job_ids == [high_job.id]

        db_session.refresh(high_job)
        db_session.refresh(low_job)

        assert high_job.status == JobStatus.SUCCESS.value
        assert low_job.status == JobStatus.RUNNING.value
    finally:
        _cleanup(db_session, [high_org_id, low_org_id])


def test_analysis_job_still_reaches_placeholder(
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(loop_module, "_last_sync_check", datetime.now(UTC))

    organization_id = _create_org(db_session, "ANALYSIS Placeholder Org")
    executed_job_ids: list[UUID] = []

    def record_execution(job: Job) -> JobStatus:
        executed_job_ids.append(job.id)
        return JobStatus.SUCCESS

    monkeypatch.setattr(loop_module, "execute_job", record_execution)

    try:
        job = _create_running_job(
            db_session,
            organization_id,
            priority="HIGH",
            created_at=datetime.now(UTC),
        )

        run_once(db_session)

        assert executed_job_ids == [job.id]
        db_session.refresh(job)
        assert job.status == JobStatus.SUCCESS.value
    finally:
        _cleanup(db_session, [organization_id])


def test_sync_job_executes_on_second_tick(
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(loop_module, "_last_sync_check", None)

    organization_id = _create_org(db_session, "SYNC Execute Org")

    try:
        data_source_id = _create_due_source(
            db_session,
            organization_id,
            csv_text=VALID_CSV,
        )

        run_once(db_session)

        jobs = (
            db_session.query(Job)
            .filter(
                Job.organization_id == organization_id,
                Job.job_type == JobType.SYNC,
                Job.source_id == data_source_id,
            )
            .all()
        )
        assert len(jobs) == 1
        assert jobs[0].status == JobStatus.RUNNING.value

        run_once(db_session)
        db_session.refresh(jobs[0])

        assert jobs[0].status == JobStatus.SUCCESS.value

        campaign_count = db_session.execute(
            text("SELECT COUNT(*) FROM campaigns WHERE organization_id = :organization_id"),
            {"organization_id": organization_id},
        ).scalar_one()
        assert campaign_count == 2
    finally:
        _cleanup(db_session, [organization_id])
