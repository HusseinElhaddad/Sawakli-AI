from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from sawakli.db.models.jobs import Job
from sawakli.db.models.organization import Organization


def _create_test_org(db: Session, name: str = "Test Dedup Org") -> UUID:
    org_id = uuid4()
    org = Organization(id=org_id, name=name)
    db.add(org)
    db.commit()
    return org_id


def _create_test_source(db: Session, organization_id: UUID) -> UUID:
    source_id = uuid4()
    db.execute(
        text(
            "INSERT INTO data_sources (id, organization_id, provider, status) "
            "VALUES (:id, :organization_id, 'csv_demo', 'demo_data')"
        ),
        {"id": source_id, "organization_id": organization_id},
    )
    db.commit()
    return source_id


def _cleanup_test_org(db: Session, organization_id: UUID) -> None:
    db.execute(delete(Job).where(Job.organization_id == organization_id))
    db.execute(
        text("DELETE FROM data_sources WHERE organization_id = :organization_id"),
        {"organization_id": organization_id},
    )
    db.execute(delete(Organization).where(Organization.id == organization_id))
    db.commit()


def test_duplicate_pending_jobs_for_same_org_rejected(db_session: Session) -> None:
    """Inserting a second PENDING job for the same organization raises IntegrityError."""
    org_id = _create_test_org(db_session)
    now = datetime.now(UTC)

    try:
        # First job: PENDING -> succeeds
        job1 = Job(
            id=uuid4(),
            organization_id=org_id,
            status="PENDING",
            priority="LOW",
            created_at=now,
        )
        db_session.add(job1)
        db_session.commit()

        # Second job: PENDING for same org -> IntegrityError
        job2 = Job(
            id=uuid4(),
            organization_id=org_id,
            status="PENDING",
            priority="HIGH",
            created_at=now,
        )
        db_session.add(job2)
        with pytest.raises(IntegrityError):
            db_session.commit()

        db_session.rollback()
    finally:
        db_session.execute(delete(Job).where(Job.organization_id == org_id))
        db_session.execute(delete(Organization).where(Organization.id == org_id))
        db_session.commit()


def test_duplicate_pending_and_running_jobs_for_same_org_rejected(
    db_session: Session,
) -> None:
    """Cannot insert a PENDING job when a RUNNING job is already in flight for that org."""
    org_id = _create_test_org(db_session)
    now = datetime.now(UTC)

    try:
        # First job: RUNNING -> succeeds
        job1 = Job(
            id=uuid4(),
            organization_id=org_id,
            status="RUNNING",
            priority="LOW",
            created_at=now,
        )
        db_session.add(job1)
        db_session.commit()

        # Second job: PENDING for same org -> IntegrityError
        job2 = Job(
            id=uuid4(),
            organization_id=org_id,
            status="PENDING",
            priority="LOW",
            created_at=now,
        )
        db_session.add(job2)
        with pytest.raises(IntegrityError):
            db_session.commit()

        db_session.rollback()
    finally:
        db_session.execute(delete(Job).where(Job.organization_id == org_id))
        db_session.execute(delete(Organization).where(Organization.id == org_id))
        db_session.commit()


def test_multiple_orgs_can_have_concurrent_inflight_jobs(
    db_session: Session,
) -> None:
    """Distinct organizations can each have active in-flight jobs without conflicting."""
    org1_id = _create_test_org(db_session, name="Org 1")
    org2_id = _create_test_org(db_session, name="Org 2")
    now = datetime.now(UTC)

    try:
        job1 = Job(
            id=uuid4(),
            organization_id=org1_id,
            status="PENDING",
            priority="LOW",
            created_at=now,
        )
        job2 = Job(
            id=uuid4(),
            organization_id=org2_id,
            status="PENDING",
            priority="HIGH",
            created_at=now,
        )
        db_session.add_all([job1, job2])
        db_session.commit()

        assert job1.id is not None
        assert job2.id is not None
    finally:
        db_session.execute(delete(Job).where(Job.organization_id.in_([org1_id, org2_id])))
        db_session.execute(delete(Organization).where(Organization.id.in_([org1_id, org2_id])))
        db_session.commit()


@pytest.mark.parametrize("terminal_status", ["SUCCESS", "FAILED", "CANCELLED", "ERROR"])
def test_new_job_allowed_after_previous_job_inactive(
    db_session: Session,
    terminal_status: str,
) -> None:
    """A new PENDING job can be created after the prior job is no longer active.

    Verified for SUCCESS, FAILED, CANCELLED, and ERROR.
    """
    org_id = _create_test_org(db_session)
    now = datetime.now(UTC)

    try:
        # Prior job in inactive / terminal status
        prior_job = Job(
            id=uuid4(),
            organization_id=org_id,
            status=terminal_status,
            priority="LOW",
            created_at=now,
        )
        db_session.add(prior_job)
        db_session.commit()

        # Next job in PENDING status succeeds
        next_job = Job(
            id=uuid4(),
            organization_id=org_id,
            status="PENDING",
            priority="HIGH",
            created_at=now,
        )
        db_session.add(next_job)
        db_session.commit()

        assert next_job.id is not None
    finally:
        db_session.execute(delete(Job).where(Job.organization_id == org_id))
        db_session.execute(delete(Organization).where(Organization.id == org_id))
        db_session.commit()


def test_analysis_and_sync_jobs_can_be_open_for_same_org(
    db_session: Session,
) -> None:
    """An ANALYSIS and a SYNC job can both be open for one organization."""
    org_id = _create_test_org(db_session)
    source_id = _create_test_source(db_session, org_id)
    now = datetime.now(UTC)

    try:
        jobs = [
            Job(
                id=uuid4(),
                organization_id=org_id,
                job_type="ANALYSIS",
                status="PENDING",
                priority="LOW",
                created_at=now,
            ),
            Job(
                id=uuid4(),
                organization_id=org_id,
                job_type="SYNC",
                source_id=source_id,
                status="PENDING",
                priority="LOW",
                created_at=now,
            ),
        ]
        db_session.add_all(jobs)
        db_session.commit()
    finally:
        _cleanup_test_org(db_session, org_id)


def test_two_open_sync_jobs_for_same_source_rejected(
    db_session: Session,
) -> None:
    """Two open SYNC jobs for the same source raise IntegrityError."""
    org_id = _create_test_org(db_session)
    source_id = _create_test_source(db_session, org_id)
    now = datetime.now(UTC)

    try:
        first = Job(
            id=uuid4(),
            organization_id=org_id,
            job_type="SYNC",
            source_id=source_id,
            status="PENDING",
            priority="LOW",
            created_at=now,
        )
        db_session.add(first)
        db_session.commit()

        second = Job(
            id=uuid4(),
            organization_id=org_id,
            job_type="SYNC",
            source_id=source_id,
            status="PENDING",
            priority="LOW",
            created_at=now,
        )
        db_session.add(second)

        with pytest.raises(IntegrityError):
            db_session.commit()

        db_session.rollback()
    finally:
        _cleanup_test_org(db_session, org_id)


def test_sync_jobs_for_different_sources_can_be_open(
    db_session: Session,
) -> None:
    """Different sources can each have an open SYNC job in one organization."""
    org_id = _create_test_org(db_session)
    now = datetime.now(UTC)

    try:
        jobs = [
            Job(
                id=uuid4(),
                organization_id=org_id,
                job_type="SYNC",
                source_id=_create_test_source(db_session, org_id),
                status="PENDING",
                priority="LOW",
                created_at=now,
            ),
            Job(
                id=uuid4(),
                organization_id=org_id,
                job_type="SYNC",
                source_id=_create_test_source(db_session, org_id),
                status="PENDING",
                priority="LOW",
                created_at=now,
            ),
        ]
        db_session.add_all(jobs)
        db_session.commit()
    finally:
        _cleanup_test_org(db_session, org_id)


def test_new_sync_job_allowed_after_previous_sync_finishes(
    db_session: Session,
) -> None:
    """A new SYNC job is allowed after the previous one finishes."""
    org_id = _create_test_org(db_session)
    source_id = _create_test_source(db_session, org_id)
    now = datetime.now(UTC)

    try:
        previous = Job(
            id=uuid4(),
            organization_id=org_id,
            job_type="SYNC",
            source_id=source_id,
            status="SUCCESS",
            priority="LOW",
            created_at=now,
        )
        db_session.add(previous)
        db_session.commit()

        next_job = Job(
            id=uuid4(),
            organization_id=org_id,
            job_type="SYNC",
            source_id=source_id,
            status="PENDING",
            priority="LOW",
            created_at=now,
        )
        db_session.add(next_job)
        db_session.commit()
    finally:
        _cleanup_test_org(db_session, org_id)
