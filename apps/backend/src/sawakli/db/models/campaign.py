import enum
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from sawakli.db.session import Base


class Platform(enum.StrEnum):
    meta = "meta"
    google = "google"


class CampaignStatus(enum.StrEnum):
    active = "active"
    paused = "paused"
    removed = "removed"
    unknown = "unknown"


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    
    # No ForeignKey here: there is no DataSource model yet, and SQLAlchemy would error.
    # data_source_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    
    data_source_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("data_sources.id"), nullable=False
    )
    external_id: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[Platform] = mapped_column(
        Enum(Platform, name="platform_enum", create_type=False), nullable=False
    )
    objective: Mapped[str | None] = mapped_column(Text)
    status: Mapped[CampaignStatus | None] = mapped_column(
        Enum(CampaignStatus, name="campaign_status_enum", create_type=False)
    )
    budget: Mapped[Decimal | None] = mapped_column(Numeric)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
