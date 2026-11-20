"""Synthetic canonical ingestion and real Worker claim query for AI-06 evidence.

Test/evidence setup only: WORK-04 still owns production reservation/dispatch.
"""

import csv
import io
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session

from sawakli.ai.contracts import PipelineRequest
from sawakli.connectors.csv import parse_csv_upload
from sawakli.data.ingestion.service import ingest_csv_upload
from sawakli.db.models.jobs import Job
from sawakli.db.tables import campaigns_table
from sawakli.worker.jobs.claim import claim_next_job

CUTOFF = date(2026, 1, 21)


def seed_pipeline_case(db: Session, *, days: int = 21) -> PipelineRequest:
    organization, source, upload, job_id, run_id = (uuid4() for _ in range(5))
    db.execute(
        sa.text("INSERT INTO organizations (id,name) VALUES (:id,'AI-06 synthetic')"),
        {"id": organization},
    )
    db.execute(
        sa.text(
            "INSERT INTO data_sources (id,organization_id,provider) VALUES (:id,:org,'csv_demo')"
        ),
        {"id": source, "org": organization},
    )
    if days:
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(
            [
                "date",
                "campaign_name",
                "platform",
                "spend",
                "impressions",
                "clicks",
                "conversions",
                "revenue",
            ]
        )
        for offset in range(days):
            day = CUTOFF - timedelta(days=days - offset - 1)
            last = offset == days - 1
            writer.writerow(
                [
                    str(day),
                    "Synthetic campaign",
                    "meta",
                    400 if last else 100,
                    1000,
                    1 if last else 50,
                    1 if last else 5,
                    1 if last else 300,
                ]
            )
        raw = stream.getvalue()
        parsed = parse_csv_upload(io.BytesIO(raw.encode()), organization, upload)
        ingest_csv_upload(
            db,
            parsed,
            organization,
            source,
            upload,
            "csv://ai06/synthetic.csv",
            {"csv": raw},
            datetime(2026, 1, 21, tzinfo=UTC),
        )
    campaigns: tuple[UUID, ...] = tuple(
        db.scalars(
            sa.select(campaigns_table.c.id).where(campaigns_table.c.organization_id == organization)
        )
    )
    db.add(
        Job(
            id=job_id,
            organization_id=organization,
            campaign_ids=[str(item) for item in campaigns] if campaigns else None,
            status="PENDING",
            priority="HIGH",
            created_at=datetime(2026, 1, 21, tzinfo=UTC),
        )
    )
    db.commit()
    # Use the existing Worker claim query, then apply the reserved-ID handoff in
    # this explicit fixture. This does not assert that production WORK-04 is wired.
    job = db.execute(claim_next_job().where(Job.id == job_id)).scalar_one()
    job.status, job.model_run_id = "RUNNING", run_id
    job.claimed_at = datetime(2026, 1, 21, 1, tzinfo=UTC)
    db.commit()
    return PipelineRequest(
        organization_id=organization,
        job_id=job_id,
        model_run_id=run_id,
        campaign_ids=campaigns or None,
        as_of=CUTOFF,
    )
