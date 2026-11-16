from dataclasses import FrozenInstanceError
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from sawakli.ai.contracts import PipelineRequest
from sawakli.ai.features.schemas import MetricRecord


@pytest.mark.parametrize("organization", [None, "", "not-a-uuid"])
def test_pipeline_requires_typed_organization(organization):
    with pytest.raises(ValidationError):
        PipelineRequest(
            organization_id=organization,
            job_id=uuid4(),
            model_run_id=uuid4(),
            as_of=date(2026, 1, 21),
        )


def test_request_rejects_credentials_and_is_frozen():
    values = dict(
        organization_id=uuid4(), job_id=uuid4(), model_run_id=uuid4(), as_of=date(2026, 1, 21)
    )
    with pytest.raises(ValidationError):
        PipelineRequest(**values, access_token="synthetic-canary")
    request = PipelineRequest(**values)
    with pytest.raises(ValidationError):
        request.organization_id = uuid4()


def test_canonical_records_are_immutable():
    record = MetricRecord(
        uuid4(),
        uuid4(),
        "same name",
        "meta",
        date(2026, 1, 21),
        Decimal(100),
        1000,
        50,
        5,
        Decimal(300),
    )
    with pytest.raises(FrozenInstanceError):
        record.spend = Decimal(0)
