from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from sawakli.db.session import Base
from sawakli.shared.enums import JobType


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
    )
    job_type: Mapped[JobType] = mapped_column(
        Enum(JobType, name="job_type_enum", create_type=False),
        nullable=False,
        default=JobType.ANALYSIS,
        server_default="ANALYSIS",
    )
    source_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
    )
    campaign_ids: Mapped[list[object] | None] = mapped_column(
        JSONB,
    )
    triggered_by_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
    )
    status: Mapped[str] = mapped_column(
        Enum(
            "PENDING",
            "RUNNING",
            "SUCCESS",
            "FAILED",
            "CANCELLED",
            "PARTIAL_SUCCESS",
            "ERROR",
            name="job_status_enum",
            create_type=False,
        ),
        nullable=False,
    )
    priority: Mapped[str] = mapped_column(
        Enum(
            "HIGH",
            "LOW",
            name="job_priority_enum",
            create_type=False,
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    max_retries: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        server_default="3",
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    timeout_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=300,
        server_default="300",
    )
    model_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        unique=True,
    )
