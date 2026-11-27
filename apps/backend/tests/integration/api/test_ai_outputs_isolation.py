"""API-05 evidence: organizations cannot see each other's AI outputs; states resolve.

Needs the repo's Postgres test harness. Two fixtures are assumed: ``client`` (a FastAPI
TestClient) and ``db_session`` (a SQLAlchemy Session on the test database). Org scoping is
exercised by overriding ``get_org_id`` (which wraps API-01's ``get_auth_context``);
the JWT path itself is covered by API-01's tests.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from sawakli.api.routes.ai_outputs import get_org_id

NOW = datetime(2026, 11, 20, 12, 0, 0)
_CLEANUP = [
    (
        "DELETE FROM action_simulations WHERE recommendation_id IN "
        "(SELECT id FROM recommendations WHERE organization_id = :o)"
    ),
    "DELETE FROM recommendations WHERE organization_id = :o",
    "DELETE FROM anomalies WHERE organization_id = :o",
    "DELETE FROM forecasts WHERE organization_id = :o",
    "DELETE FROM model_runs WHERE organization_id = :o",
    "DELETE FROM campaigns WHERE organization_id = :o",
    "DELETE FROM data_sources WHERE organization_id = :o",
    "DELETE FROM organizations WHERE id = :o",
]


@dataclass
class Seeded:
    org_id: uuid.UUID
    campaign_id: uuid.UUID
    rec_id: uuid.UUID


def _run(db: Session, sql: str, **params: Any) -> None:
    db.execute(sa.text(sql), params)


def _org(db: Session) -> uuid.UUID:
    org = uuid.uuid4()
    _run(
        db,
        "INSERT INTO organizations (id, name, created_at) VALUES (:i, :n, :t)",
        i=org,
        n=f"org-{org.hex[:6]}",
        t=NOW,
    )
    return org


def _seed(db: Session, status: str = "SUCCESS") -> Seeded:
    org, ds, camp, run, rec = (uuid.uuid4() for _ in range(5))
    _run(
        db,
        "INSERT INTO organizations (id, name, created_at) VALUES (:i, :n, :t)",
        i=org,
        n=f"org-{org.hex[:6]}",
        t=NOW,
    )
    _run(
        db,
        "INSERT INTO data_sources (id, organization_id, provider, status) "
        "VALUES (:i, :o, 'csv_demo', 'demo_data')",
        i=ds,
        o=org,
    )
    _run(
        db,
        "INSERT INTO campaigns (id, organization_id, data_source_id, name, platform, "
        "updated_at) VALUES (:i, :o, :d, 'Camp', 'google', :t)",
        i=camp,
        o=org,
        d=ds,
        t=NOW,
    )
    meta = {"request": {"as_of": "2026-11-20"}, "outcome": {"warnings": []}, "omissions": []}
    _run(
        db,
        "INSERT INTO model_runs (id, organization_id, started_at, status, completed_at, "
        "campaigns_analyzed, execution_metadata) VALUES (:i, :o, :t, :s, :t, "
        "CAST(:ca AS jsonb), CAST(:m AS jsonb))",
        i=run,
        o=org,
        t=NOW,
        s=status,
        ca=json.dumps([str(camp)]),
        m=json.dumps(meta),
    )
    if status == "SUCCESS":
        common = {"r": run, "o": org, "c": camp, "t": NOW}
        _run(
            db,
            "INSERT INTO forecasts (id, model_run_id, organization_id, campaign_id, "
            "metric_name, forecast_date, value, created_at) VALUES "
            "(:i, :r, :o, :c, 'spend', '2026-11-21', 10, :t)",
            i=uuid.uuid4(),
            **common,
        )
        _run(
            db,
            "INSERT INTO anomalies (id, model_run_id, organization_id, campaign_id, "
            "metric_name, detected_at, anomaly_score, severity, direction, created_at) VALUES "
            "(:i, :r, :o, :c, 'cpa', :t, 3.2, 'high', 'above', :t)",
            i=uuid.uuid4(),
            **common,
        )
        _run(
            db,
            "INSERT INTO recommendations (id, model_run_id, organization_id, campaign_id, "
            "problem, status, created_at) VALUES (:i, :r, :o, :c, 'p', 'pending', :t)",
            i=rec,
            **common,
        )
        for scenario, spend, conv in (
            ("budget_decrease_20", 8, 2),
            ("budget_increase_15", 12, 3),
            ("pause", 0, 0),
        ):
            _run(
                db,
                "INSERT INTO action_simulations (id, recommendation_id, scenario_type, "
                "projected_spend, projected_conversions, projected_cpa, projected_roas, "
                "created_at) VALUES (:i, :rec, :s, :sp, :cv, 0, 0, :t)",
                i=uuid.uuid4(),
                rec=rec,
                s=scenario,
                sp=spend,
                cv=conv,
                t=NOW,
            )
    db.commit()
    return Seeded(org, camp, rec)


@pytest.fixture
def cleanup(db_session: Session) -> Iterator[list[uuid.UUID]]:
    orgs: list[uuid.UUID] = []
    yield orgs
    for org in orgs:
        for sql in _CLEANUP:
            _run(db_session, sql, o=org)
    db_session.commit()


@pytest.fixture
def as_org(client: TestClient) -> Iterator[Callable[[uuid.UUID], None]]:
    app: Any = client.app

    def _set(org_id: uuid.UUID) -> None:
        app.dependency_overrides[get_org_id] = lambda: org_id

    yield _set
    app.dependency_overrides.pop(get_org_id, None)


def test_each_org_sees_only_its_own_outputs(
    client: TestClient,
    db_session: Session,
    cleanup: list[uuid.UUID],
    as_org: Callable[[uuid.UUID], None],
) -> None:
    a, b = _seed(db_session), _seed(db_session)
    cleanup += [a.org_id, b.org_id]
    as_org(a.org_id)
    for path in ("/api/forecasts", "/api/anomalies", "/api/recommendations"):
        body = client.get(path).json()
        assert body["state"] == "ready"
        assert len(body["data"]) == 1
        assert {row["campaign_id"] for row in body["data"]} == {str(a.campaign_id)}
    assert len(client.get(f"/api/recommendations/{a.rec_id}/simulations").json()["data"]) == 3


def test_other_orgs_ids_are_404(
    client: TestClient,
    db_session: Session,
    cleanup: list[uuid.UUID],
    as_org: Callable[[uuid.UUID], None],
) -> None:
    a, b = _seed(db_session), _seed(db_session)
    cleanup += [a.org_id, b.org_id]
    as_org(a.org_id)
    assert client.get(f"/api/recommendations/{b.rec_id}/simulations").status_code == 404
    for path in ("/api/forecasts", "/api/anomalies", "/api/recommendations"):
        assert client.get(path, params={"campaign_id": str(b.campaign_id)}).status_code == 404


def test_pause_ratios_are_null_and_flagged(
    client: TestClient,
    db_session: Session,
    cleanup: list[uuid.UUID],
    as_org: Callable[[uuid.UUID], None],
) -> None:
    a = _seed(db_session)
    cleanup.append(a.org_id)
    as_org(a.org_id)
    body = client.get(f"/api/recommendations/{a.rec_id}/simulations").json()
    assert [s["scenario_type"] for s in body["data"]] == [
        "budget_decrease_20",
        "budget_increase_15",
        "pause",
    ]
    pause = body["data"][2]
    assert pause["projected_cpa"] is None and pause["projected_roas"] is None
    assert pause["unavailable"] == ["cpa", "roas"]
    assert (body["horizon_start"], body["horizon_end"]) == ("2026-11-21", "2026-11-27")


def test_states_no_data_and_processing(
    client: TestClient,
    db_session: Session,
    cleanup: list[uuid.UUID],
    as_org: Callable[[uuid.UUID], None],
) -> None:
    empty = _org(db_session)
    running = _seed(db_session, status="RUNNING")
    db_session.commit()
    cleanup += [empty, running.org_id]
    as_org(empty)
    assert client.get("/api/ai/status").json()["state"] == "no_data"
    assert client.get("/api/forecasts").json()["data"] == []
    as_org(running.org_id)
    body = client.get("/api/ai/status").json()
    assert body["state"] == "processing" and body["refreshing"] is True
    assert client.get("/api/recommendations").json()["data"] == []
