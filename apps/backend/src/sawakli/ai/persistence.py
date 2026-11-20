"""Short SQLAlchemy units of work for AI-owned runs and whole-run publication.

All writers lock jobs before inspecting model_runs. AI never transitions jobs.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, TypedDict, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from sawakli.ai.contracts import ContractError, PipelineOutcome, PipelineRequest, RunStatus
from sawakli.db.models.jobs import Job
from sawakli.db.tables import campaigns_table, model_runs_table


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def lock_job(db: Session, request: PipelineRequest) -> Job:
    job = db.execute(
        sa.select(Job)
        .where(Job.id == request.job_id, Job.organization_id == request.organization_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if job is None or job.model_run_id != request.model_run_id:
        raise ContractError("job/run ownership mismatch")
    if utc(job.created_at).date() != request.as_of:
        raise ContractError("cutoff differs from job UTC creation date")
    try:
        selection = (
            tuple(sorted((UUID(str(item)) for item in job.campaign_ids), key=lambda item: item.int))
            if job.campaign_ids is not None
            else None
        )
    except (ValueError, TypeError) as exc:
        raise ContractError("invalid stored campaign selection") from exc
    if selection is not None and (not selection or len(set(selection)) != len(selection)):
        raise ContractError("invalid stored campaign selection")
    if selection != request.campaign_ids:
        raise ContractError("selection differs from stored job")
    return job


def read_run(db: Session, request: PipelineRequest) -> RowMapping | None:
    owner = db.scalar(
        sa.select(model_runs_table.c.organization_id).where(
            model_runs_table.c.id == request.model_run_id
        )
    )
    if owner is not None and owner != request.organization_id:
        raise ContractError("model run belongs to another organization")
    row = (
        db.execute(
            sa.select(model_runs_table).where(
                model_runs_table.c.id == request.model_run_id,
                model_runs_table.c.organization_id == request.organization_id,
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is not None and row["organization_id"] != request.organization_id:
        raise ContractError("model run belongs to another organization")
    if row is not None and metadata(row).get("request") != request.model_dump(mode="json"):
        raise ContractError("run request differs or legacy replay metadata is absent")
    return row


def metadata(row: RowMapping) -> dict[str, Any]:
    value = row["execution_metadata"]
    if not isinstance(value, dict):
        raise ContractError("run has no execution metadata")
    return cast(dict[str, Any], value)


def terminal(row: RowMapping | None) -> PipelineOutcome | None:
    if row is None or row["status"] not in {"SUCCESS", "CANCELLED"}:
        return None
    result = PipelineOutcome.model_validate_json(json.dumps(metadata(row)["outcome"]))
    if result.status.value != row["status"]:
        raise ContractError("stored outcome differs from run state")
    return result


def validate_claim(job: Job) -> None:
    if (
        job.status != "RUNNING"
        or job.claimed_at is None
        or not 0 <= job.retry_count < min(job.max_retries, 3)
        or (job.next_retry_at is not None and utc(job.next_retry_at) > utc(job.claimed_at))
    ):
        raise ContractError("job is not an eligible Worker claim")


def same_claim(job: Job, row: RowMapping) -> None:
    validate_claim(job)
    context = metadata(row)
    if (
        context["retry_count"] != job.retry_count
        or context["claimed_at"] != utc(cast(datetime, job.claimed_at)).isoformat()
    ):
        raise ContractError("Worker claim changed during execution")


def register(db: Session, request: PipelineRequest) -> PipelineOutcome | None:
    db.execute(sa.text("SET LOCAL TIME ZONE 'UTC'"))
    job = lock_job(db, request)
    # The organization FK on jobs is checked by PostgreSQL; explicitly confirm existence too.
    from sawakli.db.models.organization import Organization

    if (
        db.scalar(sa.select(Organization.id).where(Organization.id == request.organization_id))
        is None
    ):
        raise ContractError("organization does not exist")
    row = read_run(db, request)
    completed = terminal(row)
    if completed is not None:
        return completed
    if job.status != "CANCELLED":
        validate_claim(job)
    if request.campaign_ids is not None:
        owned: set[UUID] = set(
            db.scalars(
                sa.select(campaigns_table.c.id).where(
                    campaigns_table.c.organization_id == request.organization_id,
                    campaigns_table.c.id.in_(request.campaign_ids),
                )
            )
        )
        if owned != set(request.campaign_ids):
            raise ContractError("campaign selection is not owned by organization")
    context: dict[str, Any] = {
        "request": request.model_dump(mode="json"),
        "retry_count": job.retry_count,
        "claimed_at": utc(job.claimed_at).isoformat() if job.claimed_at else None,
        "omissions": [],
    }
    if row is None:
        db.execute(
            model_runs_table.insert().values(
                id=request.model_run_id,
                organization_id=request.organization_id,
                triggered_by_user_id=job.triggered_by_user_id,
                status="RUNNING",
                execution_metadata=context,
            )
        )
    elif job.status == "CANCELLED":
        pass
    elif row["status"] == "FAILED":
        previous = metadata(row)
        failed = PipelineOutcome.model_validate_json(json.dumps(previous["outcome"]))
        if (
            not failed.retryable
            or job.status != "RUNNING"
            or job.retry_count <= previous["retry_count"]
            or context["claimed_at"] <= previous["claimed_at"]
        ):
            raise ContractError("failed run needs a later eligible Worker retry claim")
        db.execute(
            model_runs_table.update()
            .where(
                model_runs_table.c.id == request.model_run_id,
                model_runs_table.c.organization_id == request.organization_id,
            )
            .values(
                status="RUNNING",
                completed_at=None,
                error_message=None,
                campaigns_analyzed=None,
                execution_metadata=context,
            )
        )
    elif row["status"] == "RUNNING":
        if job.status != "CANCELLED":
            same_claim(job, row)
    else:
        raise ContractError("unexpected run state")
    if job.status == "CANCELLED":
        current = read_run(db, request)
        assert current is not None
        outcome = PipelineOutcome(
            **request_identity(request), status=RunStatus.CANCELLED, error_code="cancelled"
        )
        save_outcome(db, request, current, outcome)
        return outcome
    return None


def save_outcome(
    db: Session,
    request: PipelineRequest,
    row: RowMapping,
    outcome: PipelineOutcome,
    *,
    omissions: list[dict[str, object]] | None = None,
) -> None:
    context = {**metadata(row), "outcome": outcome.model_dump(mode="json")}
    if omissions is not None:
        context["omissions"] = omissions
    db.execute(
        model_runs_table.update()
        .where(
            model_runs_table.c.id == request.model_run_id,
            model_runs_table.c.organization_id == request.organization_id,
        )
        .values(
            status=outcome.status.value,
            campaigns_analyzed=[str(item) for item in outcome.campaigns_analyzed],
            completed_at=datetime.now(UTC).replace(tzinfo=None),
            error_message=outcome.error_code,
            execution_metadata=context,
        )
    )


def finalize_failure(
    db: Session,
    request: PipelineRequest,
    outcome: PipelineOutcome,
) -> PipelineOutcome:
    job = lock_job(db, request)
    row = read_run(db, request)
    completed = terminal(row)
    if completed is not None:
        return completed
    if row is None:
        raise ContractError("registered run disappeared")
    if job.status == "CANCELLED":
        outcome = PipelineOutcome(
            **request_identity(request), status=RunStatus.CANCELLED, error_code="cancelled"
        )
    else:
        same_claim(job, row)
    save_outcome(db, request, row, outcome)
    return outcome


class RequestIdentity(TypedDict):
    organization_id: UUID
    job_id: UUID
    model_run_id: UUID


def request_identity(request: PipelineRequest) -> RequestIdentity:
    return {
        "organization_id": request.organization_id,
        "job_id": request.job_id,
        "model_run_id": request.model_run_id,
    }
