import os
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from alembic import command

_REPO_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "docker-compose.yml").is_file()
)
_BACKEND_DIR = _REPO_ROOT / "apps" / "backend"

os.environ.setdefault("JWT_SECRET", "change-this-to-a-real-secret")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:change-me@localhost:5434/sawakli_test",
)
load_dotenv(_REPO_ROOT / ".env", override=False)


@pytest.fixture(scope="session")
def migrated_database() -> None:
    alembic_cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    command.upgrade(alembic_cfg, "head")


@pytest.fixture()
def client(migrated_database: None) -> Generator[TestClient, None, None]:
    from sawakli.api.main import app
    from sawakli.db.models.jobs import Job
    from sawakli.db.models.organization import Organization
    from sawakli.db.models.organization_member import OrganizationMember
    from sawakli.db.models.user import User
    from sawakli.db.session import SessionLocal

    with TestClient(app) as test_client:
        yield test_client

    db = SessionLocal()
    try:
        db.execute(delete(Job))
        db.execute(delete(OrganizationMember))
        db.execute(delete(User))
        db.execute(delete(Organization))
        db.commit()
    finally:
        db.close()


@pytest.fixture()
def db_session(migrated_database: None) -> Generator[Session, None, None]:
    from sawakli.db.session import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def register_user(
    client: TestClient,
    *,
    name: str,
    email: str,
    password: str,
    organization_name: str,
) -> dict[str, object]:
    response = client.post(
        "/api/auth/register",
        json={
            "name": name,
            "email": email,
            "password": password,
            "organization_name": organization_name,
        },
    )
    assert response.status_code == 201, response.text
    payload: dict[str, object] = response.json()
    return payload


def login_user(client: TestClient, *, email: str, password: str) -> dict[str, object]:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    payload: dict[str, object] = response.json()
    return payload


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def insert_job(db_session: Session, organization_id: UUID) -> UUID:
    from sawakli.db.models.jobs import Job

    job_id = uuid4()
    db_session.add(
        Job(
            id=job_id,
            organization_id=organization_id,
            campaign_ids=None,
            triggered_by_user_id=None,
            status="PENDING",
            priority="LOW",
            created_at=datetime.now(UTC),
            claimed_at=None,
            model_run_id=None,
        )
    )
    db_session.commit()
    return job_id


def insert_campaign(db_session: Session, organization_id: UUID) -> UUID:
    """Insert a campaign (plus the data_source it must reference) for a test org.

    No ORM model exists for either table yet (API-02 owns that) -- raw SQL
    against the real schema is the lightest way to get a valid row for tests
    that need to prove campaign_ids ownership-checking actually works.
    """
    data_source_id = uuid4()
    campaign_id = uuid4()
    db_session.execute(
        text(
            "INSERT INTO data_sources (id, organization_id, provider) "
            "VALUES (:id, :organization_id, 'csv_demo')"
        ),
        {"id": data_source_id, "organization_id": organization_id},
    )
    db_session.execute(
        text(
            "INSERT INTO campaigns (id, organization_id, data_source_id, name, platform) "
            "VALUES (:id, :organization_id, :data_source_id, 'Test Campaign', 'google')"
        ),
        {
            "id": campaign_id,
            "organization_id": organization_id,
            "data_source_id": data_source_id,
        },
    )
    db_session.commit()
    return campaign_id
