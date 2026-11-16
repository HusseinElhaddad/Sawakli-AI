"""AI-07: application behavior and actual migrated role capabilities are separate proofs."""

import json
import re

import pytest
import sqlalchemy as sa

from sawakli.ai import pipeline
from sawakli.ai.contracts import RunStatus
from sawakli.ai.features import DatabaseDataLoader


def canonical_snapshot(engine):
    with engine.connect() as db:
        return {
            table: sorted(db.execute(sa.text(f"SELECT * FROM {table}")).all(), key=repr)
            for table in ("campaigns", "daily_metrics", "feature_daily", "ga_events", "jobs")
        }


def test_real_chain_access_audit_immutable_inputs_and_alternating_tenants(security_case):
    engine, _, requests = security_case
    before = canonical_snapshot(engine)
    statements = []

    def observe(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lower())  # Bind values deliberately excluded.

    sa.event.listen(engine, "before_cursor_execute", observe)
    try:
        outcomes = [
            pipeline.run_pipeline(request, cancellation=lambda: False)
            for request in (*requests, requests[0])
        ]
    finally:
        sa.event.remove(engine, "before_cursor_execute", observe)
    assert all(outcome.status == RunStatus.SUCCESS for outcome in outcomes)
    assert outcomes[0] == outcomes[2]
    assert canonical_snapshot(engine) == before
    assert statements
    forbidden = {"users", "oauth_connections", "connector_tokens", "raw_api_responses"}
    tables = {
        t for sql in statements for t in re.findall(r'\b(?:from|join|into|update)\s+"?(\w+)', sql)
    }
    assert not tables & forbidden
    writes = [
        sql for sql in statements if re.match(r"\s*(insert|update|delete|alter|create|drop)\b", sql)
    ]
    assert writes
    assert all(
        re.match(
            r"\s*(?:insert into|update) "
            r"(?:model_runs|forecasts|anomalies|recommendations|action_simulations)\b",
            sql,
        )
        for sql in writes
    )


def test_failure_cannot_leak_secret_canary(security_case, monkeypatch, caplog):
    engine, _, requests = security_case
    before = canonical_snapshot(engine)
    canary = "SYNTHETIC_SECRET_CANARY_AI07"

    def fail(*args):
        raise RuntimeError(canary)

    monkeypatch.setattr(pipeline, "_compute", fail)
    outcome = pipeline.run_pipeline(requests[0], cancellation=lambda: False)
    assert outcome.error_code == "computation_failed"
    with engine.connect() as db:
        row = db.execute(
            sa.text("SELECT error_message,execution_metadata FROM model_runs WHERE id=:id"),
            {"id": requests[0].model_run_id},
        ).one()
    assert canary not in json.dumps([outcome.model_dump(mode="json"), list(row)], default=str)
    assert canary not in caplog.text
    assert canonical_snapshot(engine) == before


@pytest.mark.parametrize(
    "table", ["users", "oauth_connections", "connector_tokens", "raw_api_responses"]
)
def test_migrated_ai_bundle_denies_sensitive_reads(restricted_ai, table):
    with restricted_ai.connect() as db:
        with pytest.raises(sa.exc.ProgrammingError) as error:
            db.execute(sa.text(f"SELECT * FROM {table}"))
        assert error.value.orig.sqlstate == "42501"


@pytest.mark.parametrize(
    "operation",
    [
        "INSERT INTO daily_metrics DEFAULT VALUES",
        "UPDATE daily_metrics SET spend=0",
        "DELETE FROM daily_metrics",
        "UPDATE recommendations SET status='approved'",
    ],
)
def test_migrated_ai_bundle_denies_canonical_and_human_decision_writes(restricted_ai, operation):
    with restricted_ai.connect() as db:
        with pytest.raises(sa.exc.ProgrammingError) as error:
            db.execute(sa.text(operation))
        assert error.value.orig.sqlstate == "42501"


def test_restricted_identity_rls_positive_controls_and_context_reset(restricted_ai, security_case):
    _, _, requests = security_case
    with restricted_ai.connect() as db:
        attrs = db.execute(
            sa.text("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user")
        ).one()
        assert attrs == (False, False)
        assert db.scalar(sa.text("SELECT count(*) FROM daily_metrics")) == 0
        for request in requests:
            db.execute(
                sa.text("SELECT set_config('app.current_org_id',:org,true)"),
                {"org": str(request.organization_id)},
            )
            rows = DatabaseDataLoader(db).load_metrics(request.organization_id)
            assert len(rows) == 21
            assert {r.organization_id for r in rows} == {request.organization_id}
            assert (
                db.scalar(
                    sa.text("SELECT count(*) FROM daily_metrics WHERE organization_id <> :org"),
                    {"org": request.organization_id},
                )
                == 0
            )
            db.commit()
            assert db.scalar(sa.text("SELECT count(*) FROM daily_metrics")) == 0
            db.rollback()
        db.execute(sa.text("SELECT set_config('app.current_org_id','invalid',true)"))
        assert db.scalar(sa.text("SELECT count(*) FROM daily_metrics")) == 0
        db.rollback()
    with restricted_ai.connect() as db:
        assert db.scalar(sa.text("SELECT count(*) FROM daily_metrics")) == 0


def test_actual_ai_bundle_lacks_pipeline_job_lock_privileges(restricted_ai):
    # A measured prerequisite gap, not an expected-success pipeline or a repaired fixture.
    with restricted_ai.connect() as db:
        assert not db.scalar(sa.text("SELECT has_table_privilege(current_user,'jobs','SELECT')"))
        with pytest.raises(sa.exc.ProgrammingError) as error:
            db.execute(sa.text("SELECT * FROM jobs FOR UPDATE"))
        assert error.value.orig.sqlstate == "42501"


def test_restricted_ai_can_publish_owned_forecast_but_not_foreign_row(restricted_ai, security_case):
    from uuid import uuid4

    from sawakli.db.tables import forecasts_table, model_runs_table

    _, _, requests = security_case
    own, foreign = requests
    run_id = uuid4()
    with restricted_ai.connect() as db:
        db.execute(
            sa.text("SELECT set_config('app.current_org_id',:org,true)"),
            {"org": str(own.organization_id)},
        )
        db.execute(
            model_runs_table.insert().values(
                id=run_id, organization_id=own.organization_id, status="RUNNING"
            )
        )
        db.execute(
            forecasts_table.insert().values(
                id=uuid4(),
                model_run_id=run_id,
                organization_id=own.organization_id,
                campaign_id=own.campaign_ids[0],
                metric_name="spend",
                forecast_date=own.as_of,
                value=10,
            )
        )
        assert db.scalar(sa.select(sa.func.count()).select_from(forecasts_table)) == 1
        # Roll back all synthetic output; canonical seed remains for the foreign-write probe.
        db.rollback()
        db.execute(
            sa.text("SELECT set_config('app.current_org_id',:org,true)"),
            {"org": str(own.organization_id)},
        )
        with pytest.raises(sa.exc.ProgrammingError) as error:
            db.execute(
                model_runs_table.insert().values(
                    id=uuid4(), organization_id=foreign.organization_id, status="RUNNING"
                )
            )
        assert error.value.orig.sqlstate == "42501"


def test_input_transaction_rejects_actual_write(security_case, monkeypatch):
    _, _, requests = security_case
    original = pipeline.DatabaseDataLoader.load_metrics
    observed = []

    def read(self, *args, **kwargs):
        with pytest.raises(sa.exc.InternalError) as error:
            with self._session.begin_nested():
                self._session.execute(sa.text("UPDATE daily_metrics SET spend=spend WHERE false"))
        assert error.value.orig.sqlstate == "25006"
        observed.append(True)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(pipeline.DatabaseDataLoader, "load_metrics", read)
    assert (
        pipeline.run_pipeline(requests[0], cancellation=lambda: False).status == RunStatus.SUCCESS
    )
    assert observed == [True]
