"""Persist and replay real AI-01..05 outputs in an explicitly disposable database.

Run with PYTHONPATH=apps/backend/src:apps/backend from the repository root.
Run the existing fresh-db harness first. DATABASE_URL must match TEST_DATABASE_URL.
Rows are retained for inspection; each invocation creates a new synthetic tenant.
"""

from __future__ import annotations

import json
import os
from uuid import UUID

import sqlalchemy as sa
from integration_harness import _require_disposable, _verify_connected

from sawakli.ai.pipeline import run_pipeline
from sawakli.db.models.jobs import Job
from sawakli.db.session import SessionLocal
from sawakli.db.tables import (
    action_simulations_table as simulations,
)
from sawakli.db.tables import (
    anomalies_table as anomalies,
)
from sawakli.db.tables import (
    forecasts_table as forecasts,
)
from sawakli.db.tables import (
    model_runs_table as runs,
)
from sawakli.db.tables import (
    recommendations_table as recommendations,
)
from tests.fixtures.ai06 import seed_pipeline_case


def snapshot(run_id: UUID) -> dict[str, object]:
    result: dict[str, object] = {}
    with SessionLocal() as db:
        for table in (runs, anomalies, forecasts, recommendations):
            column = table.c.id if table is runs else table.c.model_run_id
            result[table.name] = [
                dict(row)
                for row in db.execute(
                    sa.select(table).where(column == run_id).order_by(table.c.id)
                ).mappings()
            ]
        result["action_simulations"] = [
            dict(row)
            for row in db.execute(
                sa.select(simulations)
                .join(
                    recommendations,
                    simulations.c.recommendation_id == recommendations.c.id,
                )
                .where(recommendations.c.model_run_id == run_id)
                .order_by(simulations.c.id)
            ).mappings()
        ]
    return result


def main() -> None:
    url = os.environ.get("TEST_DATABASE_URL", "")
    if not url or url != os.environ.get("DATABASE_URL"):
        raise SystemExit(
            "refusing: set matching DATABASE_URL and TEST_DATABASE_URL to a disposable DB"
        )
    parsed = sa.engine.make_url(url)
    _require_disposable("TEST_DATABASE_URL", parsed, "_test")
    _verify_connected("TEST_DATABASE_URL", parsed, "_test")
    with SessionLocal() as db:
        request = seed_pipeline_case(db)
    outcome = run_pipeline(request, cancellation=lambda: False)
    assert outcome.status == "SUCCESS", outcome
    before = snapshot(request.model_run_id)
    replay = run_pipeline(request, cancellation=lambda: False)
    after = snapshot(request.model_run_id)
    assert before == after and outcome == replay
    with SessionLocal() as db:
        job_status = db.get(Job, request.job_id).status
        version = db.scalar(sa.text("SELECT version()"))
    print(
        json.dumps(
            {
                "request": request.model_dump(mode="json"),
                "outcome": outcome.model_dump(mode="json"),
                "postgres": version,
                "job_status_after_publication": job_status,
                "counts_before": {key: len(value) for key, value in before.items()},
                "counts_after": {key: len(value) for key, value in after.items()},
                "exact_row_replay_equal": before == after,
                "stored_rows": before,
            },
            default=str,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
