"""Data source routes. Only the CSV upload exists for now."""

import io
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from sawakli.api.deps import DbSession, OrgAuth, apply_org_scope
from sawakli.api.schemas.data_source import CsvUploadResponse, UploadError
from sawakli.connectors.csv import parse_csv_upload
from sawakli.connectors.errors import ConnectorError
from sawakli.core.config import settings
from sawakli.data.ingestion.service import ingest_csv_upload
from sawakli.db.models.data_source import DataSource, DataSourceStatus, Provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orgs/{org}/data-sources", tags=["data-sources"])


def _error(
    status_code: int,
    code: str,
    user_message: str,
    *,
    retryable: bool = False,
    parse_warnings: list[str] | None = None,
) -> HTTPException:
    """Build an HTTP error whose body is {"detail": {code, user_message, retryable}}."""
    body = UploadError(
        code=code,
        user_message=user_message,
        retryable=retryable,
        parse_warnings=parse_warnings,
    )
    return HTTPException(status_code=status_code, detail=body.model_dump(exclude_none=True))


def _read_upload(file: UploadFile) -> bytes:
    """Check the file before parsing and return its bytes."""
    filename = (file.filename or "").lower()
    if not filename.endswith(".csv"):
        raise _error(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "unsupported_file_type",
            "Please upload a .csv file.",
        )

    max_bytes = settings.csv_max_upload_bytes
    # Read one byte more than the limit: if we get it, the file is too big,
    # and we never load a huge file fully into memory.
    data = file.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise _error(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            "file_too_large",
            f"This file is too large. The maximum size is {max_bytes // (1024 * 1024)} MB.",
        )
    if len(data) == 0:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "empty_file",
            "This file is empty. Please upload a file with a header row and at least one data row.",
        )
    return data


def _get_or_create_csv_data_source(db: Session, organization_id: UUID) -> DataSource:
    """One CSV data source per organization, reused on every upload."""
    data_source = db.scalar(
        apply_org_scope(
            select(DataSource).where(DataSource.provider == Provider.csv_demo),
            DataSource,
            organization_id,
        )
    )
    if data_source is None:
        data_source = DataSource(
            organization_id=organization_id,
            provider=Provider.csv_demo,
            status=DataSourceStatus.demo_data,
        )
        db.add(data_source)
        # autoflush is off, so flush by hand: the ingestion service updates this
        # row with raw SQL and the row must already exist in the database.
        db.flush()
    return data_source


@router.post(
    "/csv",
    response_model=CsvUploadResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        413: {"model": UploadError},
        415: {"model": UploadError},
        422: {"model": UploadError},
    },
)
def upload_csv(auth: OrgAuth, db: DbSession, file: UploadFile) -> CsvUploadResponse:
    organization_id = auth.organization.id

    data = _read_upload(file)

    upload_id = uuid4()
    result = parse_csv_upload(io.BytesIO(data), organization_id, upload_id)

    if isinstance(result, ConnectorError):
        # message is for our logs only; the user only sees user_message.
        logger.warning(
            "CSV upload rejected: kind=%s org=%s message=%s",
            result.kind,
            organization_id,
            result.message,
        )
        raise _error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            str(result.kind),
            result.user_message,
            retryable=result.retryable,
        )

    if result.row_count == 0:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "no_valid_rows",
            "None of the rows in this file were valid. See the warnings for details.",
            parse_warnings=result.parse_warnings,
        )

    try:
        data_source = _get_or_create_csv_data_source(db, organization_id)
        ingest_csv_upload(
            db=db,
            raw_response=result,
            organization_id=organization_id,
            data_source_id=data_source.id,
            upload_id=upload_id,
            endpoint="csv_upload",
            raw_payload={"row_count": result.row_count, "parsed_rows": result.parsed_rows},
            synced_at=datetime.now(UTC),
        )
        db.commit()  # all or nothing: everything above is saved here, in one go
    except Exception:
        db.rollback()
        logger.exception("CSV ingest failed: org=%s upload=%s", organization_id, upload_id)
        raise _error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "ingest_failed",
            "We couldn't save this file. Please try again.",
            retryable=True,
        ) from None

    # After commit, SQLAlchemy reloads data_source, so status is the one the service set.
    return CsvUploadResponse(
        data_source_id=data_source.id,
        row_count=result.row_count,
        parse_warnings=result.parse_warnings,
        status=data_source.status,
    )