from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import case, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from sawakli.core.config import settings
from sawakli.data.ingestion import record_sync_failure
from sawakli.db.models.jobs import Job
from sawakli.shared.enums import JobStatus, JobType
from sawakli.worker.jobs.claim import claim_next_job
from sawakli.worker.jobs.lifecycle import transition_job_status
from sawakli.worker.jobs.timeout import is_job_timed_out
from sawakli.worker.orchestration.execute import execute_job
from sawakli.worker.orchestration.synch import run_sync_job
from sawakli.worker.scheduler.source_scheduler import find_due_sources

# Tracks the last sync scheduling check in this worker process.
_last_sync_check: datetime | None = None


def _save_transition(
    db: Session,
    job: Job,
    proposed_status: JobStatus,
) -> JobStatus:
    current_status = JobStatus(job.status)

    if current_status == JobStatus.RUNNING and proposed_status == JobStatus.ERROR:
        job.retry_count += 1

        if job.retry_count >= job.max_retries:
            job.status = JobStatus.FAILED.value
            db.flush()
            return JobStatus.FAILED

        job.status = JobStatus.PENDING.value
        job.next_retry_at = datetime.now(UTC) + timedelta(seconds=2**job.retry_count)

        db.flush()
        return JobStatus.PENDING

    try:
        final_status = transition_job_status(
            current_status,
            proposed_status,
        )
    except ValueError:
        final_status = JobStatus.FAILED

    job.status = final_status.value
    db.flush()

    return final_status


def _get_running_job(db: Session) -> Job | None:
    """Select the oldest RUNNING job, preferring HIGH priority then oldest creation time."""

    # HIGH jobs rank before LOW jobs.
    priority_rank = case(
        (Job.priority == "HIGH", 0),
        (Job.priority == "LOW", 1),
    )

    stmt = (
        select(Job)
        .where(Job.status == JobStatus.RUNNING.value)
        .order_by(
            priority_rank.asc(),
            Job.created_at.asc(),
        )
        .with_for_update(skip_locked=True)
        .limit(1)
    )

    return db.execute(stmt).scalar_one_or_none()


def _get_current_job_status(
    db: Session,
    job_id: UUID,
) -> JobStatus | None:
    """Read the current status of one specific job before finalizing it."""
    statement = select(Job.status).where(Job.id == job_id)
    status = db.execute(statement).scalar_one_or_none()

    if status is None:
        return None

    return JobStatus(status)


def _get_timed_out_job(db: Session) -> Job | None:
    """
    Find the oldest RUNNING job that has actually exceeded its timeout.

    RUNNING jobs can have different timeout_seconds values, so timeout
    cannot be determined from created_at alone. We inspect RUNNING jobs
    in oldest-first order and check each job against its own timeout.

    A timed-out RUNNING job takes priority over the normal oldest
    RUNNING job because it requires recovery. If no RUNNING job has
    timed out, return None so normal execution can continue.
    """
    stmt = (
        select(Job)
        .where(Job.status == JobStatus.RUNNING.value)
        .order_by(Job.created_at.asc())
        .with_for_update(skip_locked=True)
    )

    running_jobs = db.execute(stmt).scalars().all()
    now = datetime.now(UTC)

    for job in running_jobs:
        if is_job_timed_out(job, now):
            return job

    return None


def run_once(db: Session) -> list[Job]:
    global _last_sync_check
    processed_jobs: list[Job] = []

    now = datetime.now(UTC)
    check_interval = timedelta(seconds=settings.sync_check_every_seconds)

    # Check for due sources only when the configured interval has passed.
    if _last_sync_check is None or now - _last_sync_check >= check_interval:
        due_sources = find_due_sources(db, now.replace(tzinfo=None))

        for source in due_sources:
            try:
                # Isolate each insertion so one duplicate cannot roll back others.
                with db.begin_nested():
                    db.add(
                        Job(
                            id=uuid4(),
                            organization_id=source.organization_id,
                            status=JobStatus.PENDING.value,
                            priority="LOW",
                            job_type=JobType.SYNC.value,
                            source_id=source.data_source_id,
                            created_at=now,
                        )
                    )
                    db.flush()
            except IntegrityError:
                # Another worker may have created the SYNC job first.
                continue

        # Make newly created jobs visible to the claim query.
        db.flush()
        _last_sync_check = now

    # Select a PENDING job for the claim pipeline.
    claim_stmt = claim_next_job()
    pending_job = db.execute(claim_stmt).scalar_one_or_none()

    # Check RUNNING jobs for timeout before selecting one for normal execution.
    # A timed-out job gets priority because it requires recovery.
    timed_out_job = _get_timed_out_job(db)

    # Select the oldest RUNNING job for normal execution.
    running_job = _get_running_job(db)

    if pending_job is not None:
        proposed_status = JobStatus.RUNNING

        final_status = _save_transition(
            db,
            pending_job,
            proposed_status,
        )

        if final_status == JobStatus.RUNNING:
            pending_job.claimed_at = datetime.now(UTC)

        processed_jobs.append(pending_job)

    if timed_out_job is not None:
        # A timeout is treated like an execution error and enters
        # the same retry/backoff logic used by failed executions.
        if timed_out_job.job_type == JobType.SYNC and timed_out_job.source_id is not None:
            record_sync_failure(
                db=db,
                data_source_id=timed_out_job.source_id,
                organization_id=timed_out_job.organization_id,
                message="The sync took too long and will be retried.",
            )
        _save_transition(
            db,
            timed_out_job,
            JobStatus.ERROR,
        )

        processed_jobs.append(timed_out_job)

    elif running_job is not None:
        if running_job.job_type == JobType.SYNC:
            proposed_status = run_sync_job(db, running_job)
        else:
            proposed_status = execute_job(running_job)

        # Re-check the database immediately before writing the execution result.
        # The job may have been cancelled while execute_job() was running.
        current_status = _get_current_job_status(
            db,
            running_job.id,
        )

        if current_status != JobStatus.CANCELLED:
            _save_transition(
                db,
                running_job,
                proposed_status,
            )

        processed_jobs.append(running_job)

    db.commit()

    for job in processed_jobs:
        db.refresh(job)

    return processed_jobs
