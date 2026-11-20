from uuid import UUID

from pydantic import BaseModel

from sawakli.db.models.data_source import DataSourceStatus


class CsvUploadResponse(BaseModel):
    """Returned on a successful CSV upload."""

    data_source_id: UUID
    row_count: int
    parse_warnings: list[str]
    status: DataSourceStatus


class UploadError(BaseModel):
    """Returned (inside a 4xx) when an upload fails."""

    code: str
    user_message: str
    retryable: bool
    parse_warnings: list[str] | None = None  # only used for no_valid_rows