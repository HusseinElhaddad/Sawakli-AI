from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from sawakli.api.deps import AuthContext, get_auth_context
from sawakli.api.schemas.jobs import AnalysisRefreshRequest, AnalysisRefreshResponse
from sawakli.db.campaigns_lookup import find_missing_campaign_ids
from sawakli.db.models.jobs import Job
from sawakli.db.session import get_db
from sawakli.shared.enums import JobStatus, JobType

router = APIRouter()

_ON_DEMAND_PRIORITY = "HIGH"
_IN_FLIGHT_STATUSES = (JobStatus.PENDING.value, JobStatus.RUNNING.value)

DbSession = Annotated[Session, Depends(get_db)]
CurrentAuth = Annotated[AuthContext, Depends(get_auth_context)]


def _find_in_flight_job(db: Session, organization_id: UUID) -> Job | None:
    return db.scalar(
        select(Job)
        .where(
            Job.organization_id == organization_id,
            Job.status.in_(_IN_FLIGHT_STATUSES),
            Job.job_type == JobType.ANALYSIS,
        )
        .order_by(Job.created_at.desc())
        .limit(1)
    )


@router.post(
    "/refresh",
    response_model=AnalysisRefreshResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_analysis_refresh(
    payload: AnalysisRefreshRequest,
    auth: CurrentAuth,
    db: DbSession,
) -> AnalysisRefreshResponse:
    """Queue an analysis job for the caller's org, or hand back the one already running.

    Never calls the AI pipeline directly -- this only ever inserts a PENDING
    row into `jobs`. The Worker is the sole consumer of that queue.
    """
    if payload.campaign_ids:
        missing = find_missing_campaign_ids(db, auth.organization.id, payload.campaign_ids)
        if missing:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "campaign_ids not found for this organization: "
                    f"{sorted(str(campaign_id) for campaign_id in missing)}"
                ),
            )

    # Fast path: an in-flight job for this org almost certainly already
    # exists by the time a second click comes in. Checking first avoids an
    # insert-then-rollback for the common (non-racing) case.
    existing = _find_in_flight_job(db, auth.organization.id)
    if existing is not None:
        return AnalysisRefreshResponse(job_id=existing.id, status=JobStatus(existing.status))

    new_job = Job(
        id=uuid4(),
        organization_id=auth.organization.id,
        campaign_ids=(
            [str(campaign_id) for campaign_id in payload.campaign_ids]
            if payload.campaign_ids
            else None
        ),
        triggered_by_user_id=auth.user.id,
        status=JobStatus.PENDING.value,
        priority=_ON_DEMAND_PRIORITY,
        created_at=datetime.now(UTC),
        claimed_at=None,
        model_run_id=None,
    )
    db.add(new_job)
    try:
        db.commit()
    except IntegrityError:
        # True race: another request for this org won between our check
        # above and our insert. uq_jobs_org_inflight is what actually
        # prevents the duplicate row -- this is just recovering gracefully
        # from it.
        db.rollback()
        winner = _find_in_flight_job(db, auth.organization.id)
        if winner is None:
            raise
        return AnalysisRefreshResponse(job_id=winner.id, status=JobStatus(winner.status))

    db.refresh(new_job)
    return AnalysisRefreshResponse(job_id=new_job.id, status=JobStatus(new_job.status))
