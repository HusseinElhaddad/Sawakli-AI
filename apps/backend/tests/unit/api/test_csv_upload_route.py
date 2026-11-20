"""Route tests for POST /orgs/{org}/data-sources/csv.

No real database here. Auth, the DB session and the saving step are faked, so these
tests check only what the route itself does: checks, parser errors, status codes,
response bodies, and commit / rollback.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sawakli.api.deps import AuthContext, get_auth_context
from sawakli.api.routes import data_sources as route_module
from sawakli.core.config import settings
from sawakli.db.models.data_source import DataSourceStatus
from sawakli.db.session import get_db

ORG_ID = uuid4()
DATA_SOURCE_ID = uuid4()
URL = f"/orgs/{ORG_ID}/data-sources/csv"

HEADER = "date,campaign_name,platform,spend,revenue,impressions,clicks,conversions,sessions,bounces\n"
GOOD_ROW = "2026-01-01,Spring Sale,meta,10.5,30,1000,50,5,40,10\n"
NEGATIVE_SPEND_ROW = "2026-01-02,Spring Sale,meta,-5,30,1000,50,5,40,10\n"


# ---------- fixtures ----------


@pytest.fixture
def fake_db():
    return MagicMock()


@pytest.fixture
def app(fake_db):
    app = FastAPI()
    app.include_router(route_module.router)
    app.dependency_overrides[get_db] = lambda: fake_db
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def signed_in(app):
    """Pretend a valid token for ORG_ID was sent."""
    context = AuthContext(
        user=SimpleNamespace(id=uuid4()),
        organization=SimpleNamespace(id=ORG_ID),
    )
    app.dependency_overrides[get_auth_context] = lambda: context


@pytest.fixture
def ingest(monkeypatch):
    """Replace the saving step. Returns the mock so tests can check how it was called."""
    mock = MagicMock()
    monkeypatch.setattr(route_module, "ingest_csv_upload", mock)
    monkeypatch.setattr(
        route_module,
        "_get_or_create_csv_data_source",
        lambda db, organization_id: SimpleNamespace(
            id=DATA_SOURCE_ID, status=DataSourceStatus.demo_data
        ),
    )
    return mock


def upload(client, content: bytes, filename: str = "data.csv"):
    return client.post(URL, files={"file": (filename, content, "text/csv")})


# ---------- auth ----------


def test_no_token_returns_401(client):
    response = upload(client, (HEADER + GOOD_ROW).encode())
    assert response.status_code == 401


@pytest.mark.usefixtures("signed_in")
def test_org_not_matching_token_returns_404(client):
    response = client.post(
        f"/orgs/{uuid4()}/data-sources/csv",
        files={"file": ("data.csv", (HEADER + GOOD_ROW).encode(), "text/csv")},
    )
    assert response.status_code == 404


# ---------- upload checks ----------


@pytest.mark.usefixtures("signed_in")
def test_missing_file_field_returns_422(client, ingest):
    response = client.post(URL)
    assert response.status_code == 422
    ingest.assert_not_called()


@pytest.mark.usefixtures("signed_in")
def test_wrong_file_type_returns_415(client, ingest):
    response = upload(client, (HEADER + GOOD_ROW).encode(), filename="data.txt")
    assert response.status_code == 415
    assert response.json()["detail"]["code"] == "unsupported_file_type"
    ingest.assert_not_called()


@pytest.mark.usefixtures("signed_in")
def test_file_too_large_returns_413(client, ingest, monkeypatch):
    monkeypatch.setattr(settings, "csv_max_upload_bytes", 50)
    response = upload(client, (HEADER + GOOD_ROW).encode())  # longer than 50 bytes
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "file_too_large"
    ingest.assert_not_called()


@pytest.mark.usefixtures("signed_in")
def test_empty_file_returns_422(client, ingest):
    response = upload(client, b"")
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "empty_file"
    ingest.assert_not_called()


# ---------- parser errors ----------


@pytest.mark.usefixtures("signed_in")
def test_invalid_header_returns_422(client, ingest):
    response = upload(client, b"date,campaign_name\n2026-01-01,Spring Sale\n")
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "invalid_header"
    assert detail["retryable"] is False
    assert detail["user_message"]
    assert "message" not in detail  # the internal message must never be returned
    ingest.assert_not_called()


@pytest.mark.usefixtures("signed_in")
def test_non_utf8_file_returns_422(client, ingest):
    response = upload(client, b"\xff\xfe\xfd not utf-8")
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "unreadable_encoding"
    ingest.assert_not_called()


@pytest.mark.usefixtures("signed_in")
def test_all_rows_bad_returns_no_valid_rows(client, ingest):
    response = upload(client, (HEADER + NEGATIVE_SPEND_ROW).encode())
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "no_valid_rows"
    assert len(detail["parse_warnings"]) == 1
    ingest.assert_not_called()


# ---------- success ----------


@pytest.mark.usefixtures("signed_in")
def test_one_bad_row_still_succeeds_with_warning(client, ingest, fake_db):
    response = upload(client, (HEADER + GOOD_ROW + NEGATIVE_SPEND_ROW).encode())

    assert response.status_code == 201
    body = response.json()
    assert body["row_count"] == 1
    assert body["status"] == "demo_data"
    assert body["data_source_id"] == str(DATA_SOURCE_ID)
    assert len(body["parse_warnings"]) == 1
    assert "Row 3" in body["parse_warnings"][0]
    ingest.assert_called_once()
    fake_db.commit.assert_called_once()


@pytest.mark.usefixtures("signed_in")
def test_file_with_bom_succeeds(client, ingest):
    content = (HEADER + GOOD_ROW).encode("utf-8-sig")  # adds the BOM bytes
    assert content.startswith(b"\xef\xbb\xbf")

    response = upload(client, content)

    assert response.status_code == 201
    assert response.json()["row_count"] == 1


@pytest.mark.usefixtures("signed_in")
def test_ingest_gets_org_from_token_and_parsed_rows(client, ingest):
    upload(client, (HEADER + GOOD_ROW).encode())

    kwargs = ingest.call_args.kwargs
    assert kwargs["organization_id"] == ORG_ID
    assert kwargs["data_source_id"] == DATA_SOURCE_ID
    assert kwargs["raw_response"].row_count == 1
    assert kwargs["raw_payload"]["row_count"] == 1


@pytest.mark.usefixtures("signed_in")
def test_save_failure_rolls_back_and_hides_details(client, ingest, fake_db):
    ingest.side_effect = RuntimeError("secret database detail")

    response = upload(client, (HEADER + GOOD_ROW).encode())

    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "ingest_failed"
    assert "secret database detail" not in response.text
    fake_db.rollback.assert_called_once()
    fake_db.commit.assert_not_called()
