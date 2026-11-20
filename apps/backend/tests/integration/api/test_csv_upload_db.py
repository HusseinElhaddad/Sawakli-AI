"""Database test: upload a CSV for real and check what lands in the database.

Uses your dev database (DATABASE_URL). It creates a temporary organization and deletes
it at the end. Every other table cascades from organizations, so nothing is left behind.
The test is skipped automatically if the database is not reachable.
"""

from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from sawakli.api.deps import AuthContext, get_auth_context
from sawakli.api.routes import data_sources as route_module
from sawakli.db.session import SessionLocal

HEADER = "date,campaign_name,platform,spend,revenue,impressions,clicks,conversions,sessions,bounces\n"
ROWS = (
    "2026-01-01,Spring Sale,meta,10.5,30,1000,50,5,40,10\n"
    "2026-01-02,Spring Sale,meta,20,60,2000,100,10,80,20\n"
    "2026-01-01,Brand Search,google,5,15,500,25,2,20,4\n"
)
ROWS_SPEND_CHANGED = ROWS.replace("2026-01-01,Spring Sale,meta,10.5", "2026-01-01,Spring Sale,meta,99")


@pytest.fixture
def org_id():
    new_id = uuid4()
    try:
        with SessionLocal() as db:
            db.execute(
                text("INSERT INTO organizations (id, name) VALUES (:id, 'csv-upload-test')"),
                {"id": new_id},
            )
            db.commit()
    except OperationalError:
        pytest.skip("Database is not reachable")
    yield new_id
    with SessionLocal() as db:
        db.execute(text("DELETE FROM organizations WHERE id = :id"), {"id": new_id})
        db.commit()


@pytest.fixture
def client(org_id):
    app = FastAPI()
    app.include_router(route_module.router)
    context = AuthContext(
        user=SimpleNamespace(id=uuid4()),
        organization=SimpleNamespace(id=org_id),
    )
    app.dependency_overrides[get_auth_context] = lambda: context  # real DB, fake login
    return TestClient(app)


@contextmanager
def db_for(org_id):
    """A DB session that also sets the org for row-level security, so we can read."""
    with SessionLocal() as db:
        db.execute(
            text("SELECT set_config('app.current_org_id', :o, true)"), {"o": str(org_id)}
        )
        yield db


def upload(client, org_id, rows: str):
    return client.post(
        f"/orgs/{org_id}/data-sources/csv",
        files={"file": ("data.csv", (HEADER + rows).encode(), "text/csv")},
    )


def count(db, table: str, org_id) -> int:
    return db.scalar(
        text(f"SELECT count(*) FROM {table} WHERE organization_id = :o"), {"o": org_id}
    )


def spring_sale_spend(db, org_id):
    return db.scalar(
        text(
            "SELECT m.spend FROM daily_metrics m JOIN campaigns c ON c.id = m.campaign_id "
            "WHERE c.organization_id = :o AND c.name = 'Spring Sale' AND m.date = :d"
        ),
        {"o": org_id, "d": date(2026, 1, 1)},
    )


def test_valid_file_is_saved_and_reupload_updates(client, org_id):
    first = upload(client, org_id, ROWS)

    assert first.status_code == 201
    body = first.json()
    assert body["row_count"] == 3
    assert body["status"] == "demo_data"

    with db_for(org_id) as db:
        assert count(db, "data_sources", org_id) == 1
        assert count(db, "campaigns", org_id) == 2
        assert count(db, "daily_metrics", org_id) == 3
        assert count(db, "ga_events", org_id) == 3
        raw_count = db.scalar(
            text(
                "SELECT count(*) FROM raw_api_responses r "
                "JOIN data_sources d ON d.id = r.data_source_id WHERE d.organization_id = :o"
            ),
            {"o": org_id},
        )
        assert raw_count == 1
        assert spring_sale_spend(db, org_id) == Decimal("10.5")

    # Same campaigns and days again, with one changed number.
    second = upload(client, org_id, ROWS_SPEND_CHANGED)

    assert second.status_code == 201
    assert second.json()["data_source_id"] == body["data_source_id"]  # data source reused
    with db_for(org_id) as db:
        assert count(db, "data_sources", org_id) == 1
        assert count(db, "campaigns", org_id) == 2  # no duplicate campaigns
        assert count(db, "daily_metrics", org_id) == 3  # replaced, not added
        assert spring_sale_spend(db, org_id) == Decimal("99")
