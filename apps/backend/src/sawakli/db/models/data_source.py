import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from sawakli.db.session import Base


class Provider(enum.StrEnum):
    googleads = "googleads"
    metaads = "metaads"
    googleanalytics = "googleanalytics"
    csv_demo = "csv_demo"


class DataSourceStatus(enum.StrEnum):
    connected = "connected"
    disconnected = "disconnected"
    syncing = "syncing"
    failed = "failed"
    stale = "stale"
    demo_data = "demo_data"


class SyncStatus(enum.StrEnum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    provider: Mapped[Provider] = mapped_column(
        Enum(Provider, name="provider_enum", create_type=False), nullable=False
    )
    external_account_id: Mapped[str | None] = mapped_column(Text)
    status: Mapped[DataSourceStatus] = mapped_column(
        Enum(DataSourceStatus, name="data_source_status_enum", create_type=False),
        nullable=False,
        default=DataSourceStatus.disconnected,
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime)
    sync_status: Mapped[SyncStatus | None] = mapped_column(
        Enum(SyncStatus, name="sync_status_enum", create_type=False)
    )
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )