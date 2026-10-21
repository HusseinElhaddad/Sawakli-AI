from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from sawakli.db.models.data_source import Provider
from sawakli.db.session import Base


class RawApiResponse(Base):
    __tablename__ = "raw_api_responses"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    data_source_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("data_sources.id"), nullable=False
    )
    provider: Mapped[Provider] = mapped_column(
        Enum(Provider, name="provider_enum", create_type=False), nullable=False
    )
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[Any | None] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)