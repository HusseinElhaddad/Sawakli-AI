"""Real restricted-login fixtures; migrations/grants are never repaired by these tests."""

import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from sawakli.ai import pipeline
from tests.fixtures.ai06 import seed_pipeline_case


@pytest.fixture
def security_case(monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "scripts"))
    from integration_harness import _require_disposable, _verify_connected

    url = sa.engine.make_url(os.environ["TEST_DATABASE_URL"])
    _require_disposable("TEST_DATABASE_URL", url, "_test")
    _verify_connected("TEST_DATABASE_URL", url, "_test")
    engine = sa.create_engine(url)
    factory = sessionmaker(engine)
    monkeypatch.setattr(pipeline, "SessionLocal", factory)
    with factory() as db:
        requests = (seed_pipeline_case(db), seed_pipeline_case(db))
    try:
        yield engine, factory, requests
    finally:
        with factory.begin() as db:
            for request in requests:
                db.execute(
                    sa.text("DELETE FROM organizations WHERE id=:id"),
                    {"id": request.organization_id},
                )
        engine.dispose()


@pytest.fixture
def restricted_ai(security_case):
    engine, _, _ = security_case
    name = "ai07_" + uuid4().hex
    password = uuid4().hex  # Disposable random test credential, never logged.
    with engine.begin() as db:
        # Generated hexadecimal identifiers/credentials only. PostgreSQL utility DDL
        # does not accept a bound parameter here; no user input is interpolated.
        db.exec_driver_sql(
            'CREATE ROLE "' + name + "\" LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD '" + password + "'"
        )
        db.execute(sa.text(f'GRANT ai_layer_role TO "{name}"'))
    restricted = sa.create_engine(engine.url.set(username=name, password=password))
    try:
        yield restricted
    finally:
        restricted.dispose()
        with engine.begin() as db:
            db.execute(sa.text(f'DROP ROLE "{name}"'))
