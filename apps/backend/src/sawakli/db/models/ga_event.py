import datetime as dt
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Integer, Numeric
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from sawakli.db.session import Base


class GaEvent(Base):
    __tablename__ = "ga_events"

    campaign_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("campaigns.id"), primary_key=True
    )
    date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    sessions: Mapped[int] = mapped_column(Integer, nullable=False)
    bounces: Mapped[int] = mapped_column(Integer, nullable=False)
    session_duration: Mapped[Decimal | None] = mapped_column(Numeric)