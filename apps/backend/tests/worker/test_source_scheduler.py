from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from sawakli.core.config import settings
from sawakli.worker.scheduler.source_scheduler import (
    DueSource,
    find_due_sources,
)


def _create_source(
    db: Session,
    *,
    provider: str = "csv_demo",
    last_synced_at: datetime | None = None,
    stored_upload: bool = True,
) -> tuple[object, object]:
    organization_id = uuid4()
    data_source_id = uuid4()

    db.execute(
        sa.text("INSERT INTO organizations (id, name) VALUES (:id, :name)"),
        {"id": organization_id, "name": "Source Scheduler Test"},
    )

    db.execute(
        sa.text(
            "INSERT INTO data_sources "
            "(id, organization_id, provider, status, last_synced_at) "
            "VALUES (:id, :organization_id, :provider, 'demo_data', "
            ":last_synced_at)"
        ),
        {
            "id": data_source_id,
            "organization_id": organization_id,
            "provider": provider,
            "last_synced_at": last_synced_at,
        },
    )

    if stored_upload:
        db.execute(
            sa.text(
                "INSERT INTO raw_api_responses "
                "(id, data_source_id, provider, endpoint, payload, fetched_at) "
                "VALUES (:id, :data_source_id, 'csv_demo', :endpoint, "
                "CAST('{}' AS jsonb), :fetched_at)"
            ),
            {
                "id": uuid4(),
                "data_source_id": data_source_id,
                "endpoint": "test://upload",
                "fetched_at": datetime.now(UTC).replace(tzinfo=None),
            },
        )

    db.commit()
    return organization_id, data_source_id


def _create_sync_job(
    db: Session,
    organization_id: object,
    data_source_id: object,
    *,
    status: str = "PENDING",
    created_at: datetime,
    job_type: str = "SYNC",
) -> None:
    db.execute(
        sa.text(
            "INSERT INTO jobs "
            "(id, organization_id, job_type, source_id, status, priority, created_at) "
            "VALUES (:id, :organization_id, :job_type, :source_id, "
            ":status, 'LOW', :created_at)"
        ),
        {
            "id": uuid4(),
            "organization_id": organization_id,
            "job_type": job_type,
            "source_id": data_source_id,
            "status": status,
            "created_at": created_at,
        },
    )
    db.commit()


def _cleanup(db: Session, organization_id: object) -> None:
    db.execute(
        sa.text("DELETE FROM organizations WHERE id = :id"),
        {"id": organization_id},
    )
    db.commit()


@pytest.fixture
def refresh_interval(monkeypatch: pytest.MonkeyPatch) -> int:
    monkeypatch.setattr(settings, "sync_refresh_every_seconds", 3600)
    return 3600


def test_source_with_stored_upload_and_no_last_sync_is_due(
    db_session: Session,
    refresh_interval: int,
) -> None:
    organization_id, source_id = _create_source(db_session)
    now = datetime.now(UTC).replace(tzinfo=None)

    try:
        result = find_due_sources(db_session, now)

        assert DueSource(source_id, organization_id) in result
    finally:
        _cleanup(db_session, organization_id)


def test_recently_synced_source_is_not_due(
    db_session: Session,
    refresh_interval: int,
) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    organization_id, _ = _create_source(
        db_session,
        last_synced_at=now - timedelta(minutes=1),
    )

    try:
        result = find_due_sources(db_session, now)

        assert all(item.organization_id != organization_id for item in result)
    finally:
        _cleanup(db_session, organization_id)


def test_source_synced_before_refresh_interval_is_due(
    db_session: Session,
    refresh_interval: int,
) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    organization_id, source_id = _create_source(
        db_session,
        last_synced_at=now - timedelta(seconds=refresh_interval + 1),
    )

    try:
        result = find_due_sources(db_session, now)

        assert DueSource(source_id, organization_id) in result
    finally:
        _cleanup(db_session, organization_id)


@pytest.mark.parametrize("status", ["PENDING", "RUNNING"])
def test_source_with_open_sync_job_is_not_due(
    db_session: Session,
    refresh_interval: int,
    status: str,
) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    organization_id, source_id = _create_source(db_session)

    try:
        _create_sync_job(
            db_session,
            organization_id,
            source_id,
            status=status,
            created_at=now - timedelta(days=2),
        )

        result = find_due_sources(db_session, now)

        assert all(item.data_source_id != source_id for item in result)
    finally:
        _cleanup(db_session, organization_id)


@pytest.mark.parametrize("status", ["SUCCESS", "FAILED", "CANCELLED", "ERROR"])
def test_recent_sync_job_prevents_another_sync(
    db_session: Session,
    refresh_interval: int,
    status: str,
) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    organization_id, source_id = _create_source(db_session)

    try:
        _create_sync_job(
            db_session,
            organization_id,
            source_id,
            status=status,
            created_at=(now - timedelta(minutes=5)).replace(tzinfo=UTC),
        )

        result = find_due_sources(db_session, now)

        assert all(item.data_source_id != source_id for item in result)
    finally:
        _cleanup(db_session, organization_id)


def test_old_terminal_sync_job_does_not_prevent_due_source(
    db_session: Session,
    refresh_interval: int,
) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    organization_id, source_id = _create_source(db_session)

    try:
        _create_sync_job(
            db_session,
            organization_id,
            source_id,
            status="FAILED",
            created_at=(now - timedelta(seconds=refresh_interval + 1)).replace(tzinfo=UTC),
        )

        result = find_due_sources(db_session, now)

        assert DueSource(source_id, organization_id) in result
    finally:
        _cleanup(db_session, organization_id)


def test_source_without_stored_upload_is_not_due(
    db_session: Session,
    refresh_interval: int,
) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    organization_id, source_id = _create_source(
        db_session,
        stored_upload=False,
    )

    try:
        result = find_due_sources(db_session, now)

        assert all(item.data_source_id != source_id for item in result)
    finally:
        _cleanup(db_session, organization_id)


def test_source_with_another_provider_is_not_due(
    db_session: Session,
    refresh_interval: int,
) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    organization_id, source_id = _create_source(
        db_session,
        provider="googleads",
    )

    try:
        result = find_due_sources(db_session, now)

        assert all(item.data_source_id != source_id for item in result)
    finally:
        _cleanup(db_session, organization_id)


def test_analysis_job_does_not_prevent_source_from_being_due(
    db_session: Session,
    refresh_interval: int,
) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    organization_id, source_id = _create_source(db_session)

    try:
        _create_sync_job(
            db_session,
            organization_id,
            source_id,
            job_type="ANALYSIS",
            created_at=now.replace(tzinfo=UTC),
        )

        result = find_due_sources(db_session, now)

        assert DueSource(source_id, organization_id) in result
    finally:
        _cleanup(db_session, organization_id)
