import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from threading import Barrier, Event
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from sawakli.ai import persistence, pipeline
from sawakli.ai.contracts import RunStatus
from sawakli.db.models.jobs import Job
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


@pytest.fixture
def case(monkeypatch):
    # Existing CI harness prepares TEST_DATABASE_URL. Never fall back to a development DB.
    url = os.environ.get("TEST_DATABASE_URL", "")
    if not url:
        pytest.fail("TEST_DATABASE_URL must name a migrated disposable _test database")
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "scripts"))
    from integration_harness import _require_disposable, _verify_connected

    parsed = sa.engine.make_url(url)
    _require_disposable("TEST_DATABASE_URL", parsed, "_test")
    _verify_connected("TEST_DATABASE_URL", parsed, "_test")
    engine = sa.create_engine(url)
    factory = sessionmaker(engine)
    monkeypatch.setattr(pipeline, "SessionLocal", factory)
    with factory() as db:
        request = seed_pipeline_case(db)
    yield request, factory
    with factory.begin() as db:
        db.execute(
            sa.text("DELETE FROM organizations WHERE id=:id"), {"id": request.organization_id}
        )
    engine.dispose()


def counts(factory, request):
    with factory() as db:
        values = [
            db.scalar(
                sa.select(sa.func.count())
                .select_from(table)
                .where(table.c.model_run_id == request.model_run_id)
            )
            for table in (anomalies, forecasts, recommendations)
        ]
        values.append(
            db.scalar(
                sa.select(sa.func.count())
                .select_from(
                    simulations.join(
                        recommendations, simulations.c.recommendation_id == recommendations.c.id
                    )
                )
                .where(recommendations.c.model_run_id == request.model_run_id)
            )
        )
        return tuple(values)


def execute(request):
    return pipeline.run_pipeline(request, cancellation=lambda: False)


def test_real_chain_atomic_tags_foreign_keys_markers_and_human_replay(case, monkeypatch):
    request, factory = case
    outcome = execute(request)
    assert outcome.status == RunStatus.SUCCESS, outcome
    before = counts(factory, request)
    assert before[0] > 0 and before[1] == 9 and before[2] > 0 and before[3] == 3 * before[2]
    with factory.begin() as db:
        rows = (
            db.execute(
                sa.select(recommendations).where(
                    recommendations.c.model_run_id == request.model_run_id
                )
            )
            .mappings()
            .all()
        )
        for row in rows:
            assert row["organization_id"] == request.organization_id
            assert row["campaign_id"] in request.campaign_ids
            assert isinstance(row["evidence"], list)
            assert any("historical-repeat-v1" in item for item in row["evidence"])
            assert "scenario:pause;undefined_ratios:cpa,roas" in row["evidence"]
            linked = (
                db.execute(
                    sa.select(simulations).where(simulations.c.recommendation_id == row["id"])
                )
                .mappings()
                .all()
            )
            assert {item["scenario_type"] for item in linked} == {
                "budget_decrease_20",
                "budget_increase_15",
                "pause",
            }
            if row["source_anomaly_id"]:
                source = (
                    db.execute(
                        sa.select(anomalies).where(anomalies.c.id == row["source_anomaly_id"])
                    )
                    .mappings()
                    .one()
                )
                assert source["model_run_id"] == request.model_run_id
                assert source["organization_id"] == row["organization_id"]
                assert source["campaign_id"] == row["campaign_id"]
                assert source["detectors_triggered"]["score_scope"] == "campaign_day"
                assert (
                    source["detected_at"].date().isoformat()
                    == source["detectors_triggered"]["observed_on"]
                )
        assert any(row["source_anomaly_id"] for row in rows)
        ids = {row["id"] for row in rows}
        db.execute(
            recommendations.update().where(recommendations.c.id.in_(ids)).values(status="approved")
        )
        # Crash window: Worker has not completed its job status.
        assert db.get(Job, request.job_id).status == "RUNNING"
    monkeypatch.setattr(pipeline, "_compute", lambda *a: pytest.fail("replay recomputed"))
    assert execute(request) == outcome
    assert counts(factory, request) == before
    with factory() as db:
        assert (
            set(
                db.scalars(
                    sa.select(recommendations.c.id).where(
                        recommendations.c.model_run_id == request.model_run_id
                    )
                )
            )
            == ids
        )
        assert set(
            db.scalars(sa.select(recommendations.c.status).where(recommendations.c.id.in_(ids)))
        ) == {"approved"}


def test_empty_workspace(case):
    request, factory = case
    with factory.begin() as db:
        db.execute(
            sa.text("DELETE FROM campaigns WHERE organization_id=:id"),
            {"id": request.organization_id},
        )
        db.get(Job, request.job_id).campaign_ids = None
    request = request.model_copy(update={"campaign_ids": None})
    outcome = execute(request)
    assert outcome.status == RunStatus.SUCCESS and "no_data" in outcome.warnings
    assert outcome.campaigns_analyzed == () and counts(factory, request) == (0, 0, 0, 0)
    assert execute(request) == outcome


@pytest.mark.parametrize("sparse", [True, False])
def test_sparse_and_gapped_baselines_preserve_independent_outputs(case, sparse):
    request, factory = case
    with factory.begin() as db:
        db.execute(
            sa.text(
                "DELETE FROM daily_metrics WHERE organization_id=:id AND "
                + ("date < :day" if sparse else "date = :day")
            ),
            {
                "id": request.organization_id,
                "day": request.as_of - timedelta(days=1 if sparse else 3),
            },
        )
    outcome = execute(request)
    assert outcome.status == RunStatus.SUCCESS and "insufficient_history" in outcome.warnings
    actual = counts(factory, request)
    assert actual[2:] == (0, 0)
    assert actual[1] == (0 if sparse else 9)
    with factory() as db:
        metadata = db.scalar(
            sa.select(runs.c.execution_metadata).where(runs.c.id == request.model_run_id)
        )
        assert metadata["omissions"][0]["campaign_id"] == str(request.campaign_ids[0])


@pytest.mark.parametrize(
    "field", ["organization_id", "job_id", "model_run_id", "campaign_ids", "as_of"]
)
def test_foreign_or_inconsistent_request_rejected(case, field):
    request, factory = case
    value = (
        (uuid4(),)
        if field == "campaign_ids"
        else (request.as_of - timedelta(days=1) if field == "as_of" else uuid4())
    )
    outcome = execute(request.model_copy(update={field: value}))
    assert outcome.status == RunStatus.FAILED and outcome.error_code == "invalid_input"
    assert not outcome.retryable and counts(factory, request) == (0, 0, 0, 0)


def test_foreign_campaign_in_stored_job_rejected(case):
    request, factory = case
    foreign = uuid4()
    with factory.begin() as db:
        db.get(Job, request.job_id).campaign_ids = [str(foreign)]
    assert (
        execute(request.model_copy(update={"campaign_ids": (foreign,)})).error_code
        == "invalid_input"
    )


def test_foreign_existing_run_rejected_without_mutation(case):
    request, factory = case
    with factory.begin() as db:
        other = uuid4()
        db.execute(
            sa.text("INSERT INTO organizations (id,name) VALUES (:id,'foreign')"), {"id": other}
        )
        db.execute(
            runs.insert().values(id=request.model_run_id, organization_id=other, status="RUNNING")
        )
    try:
        assert execute(request).error_code == "invalid_input"
        with factory() as db:
            assert (
                db.scalar(sa.select(runs.c.status).where(runs.c.id == request.model_run_id))
                == "RUNNING"
            )
    finally:
        with factory.begin() as db:
            db.execute(sa.text("DELETE FROM organizations WHERE id=:id"), {"id": other})


@pytest.mark.parametrize("fault", ["duplicate", "metric_evidence"])
def test_invalid_loaded_or_structured_data_is_nonretryable(case, monkeypatch, fault):
    request, factory = case
    if fault == "duplicate":
        original = pipeline.DatabaseDataLoader.load_metrics

        def duplicate(self, *args, **kwargs):
            values = original(self, *args, **kwargs)
            return (*values, values[-1])

        monkeypatch.setattr(pipeline.DatabaseDataLoader, "load_metrics", duplicate)
    else:
        original = pipeline.detect_anomalies

        def invalid(records):
            results = original(records)
            last = results[-1]
            bad = last.metric_evidence[0].model_copy(update={"campaign_id": uuid4()})
            return (*results[:-1], replace(last, metric_evidence=(bad,)))

        monkeypatch.setattr(pipeline, "detect_anomalies", invalid)
    outcome = execute(request)
    assert outcome.error_code == "invalid_input" and not outcome.retryable
    assert counts(factory, request) == (0, 0, 0, 0)


def test_publication_failure_rolls_back_every_output(case, monkeypatch):
    request, factory = case
    original = pipeline._insert_outputs

    def fail(db, publication):
        original(db, publication)
        raise RuntimeError("sensitive SQL/password never persisted")

    monkeypatch.setattr(pipeline, "_insert_outputs", fail)
    outcome = execute(request)
    assert outcome.error_code == "storage_failed" and outcome.retryable
    assert counts(factory, request) == (0, 0, 0, 0)
    with factory() as db:
        row = db.execute(sa.select(runs).where(runs.c.id == request.model_run_id)).mappings().one()
        assert row["status"] == "FAILED" and row["error_message"] == "storage_failed"
        assert "sensitive" not in str(row["execution_metadata"])


def test_computation_failure_eligible_retry_and_attempt_limit(case, monkeypatch):
    request, factory = case
    original = pipeline.detect_anomalies

    def fail(*args):
        raise RuntimeError("private provider response")

    monkeypatch.setattr(pipeline, "detect_anomalies", fail)
    failed = execute(request)
    assert failed.error_code == "computation_failed" and failed.retryable
    assert execute(request).error_code == "invalid_input"  # same claim cannot restart FAILED
    with factory.begin() as db:
        job = db.get(Job, request.job_id)
        job.retry_count = 3
        job.claimed_at += timedelta(seconds=10)
    assert execute(request).error_code == "invalid_input"
    with factory.begin() as db:
        job = db.get(Job, request.job_id)
        job.retry_count = 1
        started = db.scalar(sa.select(runs.c.started_at).where(runs.c.id == request.model_run_id))
    monkeypatch.setattr(pipeline, "detect_anomalies", original)
    assert execute(request).status == RunStatus.SUCCESS
    with factory() as db:
        assert (
            db.scalar(sa.select(runs.c.started_at).where(runs.c.id == request.model_run_id))
            == started
        )


@pytest.mark.parametrize("point", ["before_compute", "before_publish", "stored"])
def test_cancellation_is_terminal_and_publishes_nothing(case, monkeypatch, point):
    request, factory = case
    cancel = Event()
    if point == "before_compute":
        cancel.set()
    elif point == "stored":
        with factory.begin() as db:
            db.get(Job, request.job_id).status = "CANCELLED"
    else:
        original = pipeline._publish

        def before(*args):
            cancel.set()
            return original(*args)

        monkeypatch.setattr(pipeline, "_publish", before)
    outcome = pipeline.run_pipeline(request, cancellation=cancel.is_set)
    assert outcome.status == RunStatus.CANCELLED and counts(factory, request) == (0, 0, 0, 0)
    monkeypatch.setattr(pipeline, "_compute", lambda *a: pytest.fail("cancelled run recomputed"))
    assert execute(request) == outcome


def test_concurrent_publishers_recheck_success_after_optimistic_check(case, monkeypatch):
    request, factory = case
    ready = Barrier(2)
    original = pipeline._publish

    def publish(*args):
        ready.wait(timeout=30)
        return original(*args)

    monkeypatch.setattr(pipeline, "_publish", publish)
    with ThreadPoolExecutor(2) as executor:
        futures = [executor.submit(execute, request) for _ in range(2)]
        outcomes = [future.result(timeout=60) for future in futures]
    assert outcomes[0] == outcomes[1] and outcomes[0].status == RunStatus.SUCCESS
    actual = counts(factory, request)
    assert actual[1] == 9 and actual[3] == 3 * actual[2]
    with factory() as db:
        keys = list(
            db.scalars(
                sa.select(recommendations.c.evidence).where(
                    recommendations.c.model_run_id == request.model_run_id
                )
            )
        )
    rules = [next(item for item in evidence if item.startswith("rule_id:")) for evidence in keys]
    assert len(rules) == len(set(rules))


@pytest.mark.parametrize("winner", ["publication", "cancellation"])
def test_publication_cancellation_lock_ordering_separate_sessions(case, monkeypatch, winner):
    request, factory = case
    reached, release, attempted = Event(), Event(), Event()
    original_insert = pipeline._insert_outputs
    original_publish = pipeline._publish
    if winner == "publication":

        def insert(db, publication):
            reached.set()  # publisher owns job lock
            assert release.wait(30)
            original_insert(db, publication)

        monkeypatch.setattr(pipeline, "_insert_outputs", insert)
    else:

        def publish(*args):
            reached.set()  # before publisher acquires lock
            assert release.wait(30)
            return original_publish(*args)

        monkeypatch.setattr(pipeline, "_publish", publish)

    def cancel():
        with factory.begin() as db:
            attempted.set()
            job = persistence.lock_job(db, request)
            row = persistence.read_run(db, request)
            if row is not None and row["status"] == "SUCCESS":
                return "SUCCESS"
            job.status = "CANCELLED"
            return "CANCELLED"

    with ThreadPoolExecutor(2) as executor:
        publisher = executor.submit(execute, request)
        assert reached.wait(30)
        canceller = executor.submit(cancel)
        assert attempted.wait(30)
        if winner == "cancellation":
            assert canceller.result(timeout=30) == "CANCELLED"
        release.set()
        outcome = publisher.result(timeout=60)
        assert canceller.result(timeout=30) == (
            "SUCCESS" if winner == "publication" else "CANCELLED"
        )
    assert outcome.status == (RunStatus.SUCCESS if winner == "publication" else RunStatus.CANCELLED)
    if winner == "cancellation":
        assert counts(factory, request) == (0, 0, 0, 0)


def test_failure_recording_outage_propagates_to_worker(case, monkeypatch):
    request, factory = case

    def fail(*args):
        raise RuntimeError("computation")

    monkeypatch.setattr(pipeline, "_compute", fail)

    def unavailable(*args):
        raise sa.exc.OperationalError("redacted", {}, Exception("unavailable"))

    monkeypatch.setattr(persistence, "finalize_failure", unavailable)
    with pytest.raises(sa.exc.OperationalError):
        execute(request)


def test_read_snapshot_is_read_only_consistent_and_released_before_compute(case, monkeypatch):
    request, factory = case
    original_load = pipeline.DatabaseDataLoader.load_metrics
    original_compute = pipeline._compute

    def load(self, *args, **kwargs):
        assert self._session.scalar(sa.text("SHOW transaction_isolation")) == "repeatable read"
        assert self._session.scalar(sa.text("SHOW transaction_read_only")) == "on"
        return original_load(self, *args, **kwargs)

    def compute(*args):
        assert factory.kw["bind"].pool.checkedout() == 0
        return original_compute(*args)

    monkeypatch.setattr(pipeline.DatabaseDataLoader, "load_metrics", load)
    monkeypatch.setattr(pipeline, "_compute", compute)
    assert execute(request).status == RunStatus.SUCCESS


def test_actual_foreign_campaign_rejected_even_when_stored_on_job(case):
    request, factory = case
    with factory() as db:
        foreign = seed_pipeline_case(db)
    try:
        with factory.begin() as db:
            db.get(Job, request.job_id).campaign_ids = [str(foreign.campaign_ids[0])]
        assert (
            execute(request.model_copy(update={"campaign_ids": foreign.campaign_ids})).error_code
            == "invalid_input"
        )
        assert counts(factory, request) == counts(factory, foreign) == (0, 0, 0, 0)
    finally:
        with factory.begin() as db:
            db.execute(
                sa.text("DELETE FROM organizations WHERE id=:id"), {"id": foreign.organization_id}
            )


def test_zero_conversion_baseline_preserves_nonpause_undefined_ratio_markers(case):
    request, factory = case
    with factory.begin() as db:
        db.execute(
            sa.text("UPDATE daily_metrics SET conversions=0,revenue=0 WHERE organization_id=:id"),
            {"id": request.organization_id},
        )
    assert execute(request).status == RunStatus.SUCCESS
    with factory() as db:
        evidence = list(
            db.scalars(
                sa.select(recommendations.c.evidence).where(
                    recommendations.c.model_run_id == request.model_run_id
                )
            )
        )
        assert evidence
        for strings in evidence:
            assert "scenario:budget_decrease_20;undefined_ratios:cpa" in strings
            assert "scenario:budget_increase_15;undefined_ratios:cpa" in strings


@pytest.mark.parametrize(
    "field,value", [("status", "PENDING"), ("claimed_at", None), ("retry_count", 3)]
)
def test_unclaimed_or_ineligible_job_rejected(case, field, value):
    request, factory = case
    with factory.begin() as db:
        setattr(db.get(Job, request.job_id), field, value)
    assert execute(request).error_code == "invalid_input"
    assert counts(factory, request) == (0, 0, 0, 0)


def test_as_of_uses_utc_creation_date_and_never_future_facts(case):
    request, factory = case
    from datetime import UTC, datetime, timezone

    with factory.begin() as db:
        # Canonical jobs.created_at is TIMESTAMP without zone: writers store UTC.
        db.execute(sa.text("SET LOCAL TIME ZONE 'UTC'"))
        # Local Jan 22 is UTC Jan 21. Retry cutoff must remain Jan 21.
        db.get(Job, request.job_id).created_at = datetime(
            2026, 1, 22, 1, tzinfo=timezone(timedelta(hours=2))
        )
        db.execute(
            sa.text(
                "INSERT INTO daily_metrics "
                "SELECT organization_id,campaign_id,:future,9999,9999,9999,9999,9999 "
                "FROM daily_metrics WHERE organization_id=:id AND date=:day"
            ),
            {
                "future": request.as_of + timedelta(days=1),
                "id": request.organization_id,
                "day": request.as_of,
            },
        )
    assert execute(request).status == RunStatus.SUCCESS
    with factory() as db:
        row = db.scalar(
            sa.select(runs.c.execution_metadata).where(runs.c.id == request.model_run_id)
        )
        assert row["request"]["as_of"] == "2026-01-21"
        anomaly_dates = list(
            db.scalars(
                sa.select(anomalies.c.detected_at).where(
                    anomalies.c.model_run_id == request.model_run_id
                )
            )
        )
        assert all(item.replace(tzinfo=UTC).date() <= request.as_of for item in anomaly_dates)


def test_historical_anomalies_do_not_enrich_current_recommendations(case, monkeypatch):
    request, factory = case
    with factory.begin() as db:
        db.execute(
            sa.text(
                "UPDATE daily_metrics SET spend=400,clicks=1,conversions=1,revenue=1 "
                "WHERE organization_id=:id AND date=:previous"
            ),
            {"id": request.organization_id, "previous": request.as_of - timedelta(days=1)},
        )
        db.execute(
            sa.text(
                "UPDATE daily_metrics SET spend=100,clicks=50,conversions=5,revenue=300 "
                "WHERE organization_id=:id AND date=:day"
            ),
            {"id": request.organization_id, "day": request.as_of},
        )
    original = pipeline.generate_recommendations

    def recommend(history, signals, forecasts):
        assert not signals
        return original(history, signals, forecasts)

    monkeypatch.setattr(pipeline, "generate_recommendations", recommend)
    assert execute(request).status == RunStatus.SUCCESS
    with factory() as db:
        dates = list(
            db.scalars(
                sa.select(anomalies.c.detected_at).where(
                    anomalies.c.model_run_id == request.model_run_id
                )
            )
        )
        assert dates and all(item.date() < request.as_of for item in dates)
