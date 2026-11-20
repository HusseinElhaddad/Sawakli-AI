"""GA4 API response parser.

Converts GA4 Data API responses to RawResponse format,
following the same pattern as CSV parser for consistency.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from ..csv.parser import RawResponse
from ..errors import ConnectorError


class GA4ParseErrorKind(str):
    """GA4 response parsing error codes."""

    INVALID_RESPONSE_FORMAT = "invalid_response_format"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    INVALID_DATE_FORMAT = "invalid_date_format"


def parse_ga4_response(
    api_response: dict[str, Any] | ConnectorError,
    organization_id: UUID,
    data_source_id: UUID,
) -> RawResponse | ConnectorError:
    """Parse GA4 API response into canonical RawResponse format.

    Follows the same contract as parse_csv_upload:
    - Returns RawResponse for successful parses (some rows may be skipped with warnings)
    - Returns ConnectorError for complete parse failures

    Args:
        api_response: Dict from GA4 API or ConnectorError from client
        organization_id: Organization scope for tenant isolation
        data_source_id: Data source that owns this data

    Returns:
        RawResponse with parsed rows and warnings, or ConnectorError
    """
    if isinstance(api_response, ConnectorError):
        return api_response

    if not isinstance(api_response, dict):
        return ConnectorError(
            kind=GA4ParseErrorKind.INVALID_RESPONSE_FORMAT,
            message=f"Expected dict from GA4 API, got {type(api_response).__name__}",
            user_message="Received an invalid response from Google Analytics.",
            retryable=False,
        )

    if "rows" not in api_response:
        return ConnectorError(
            kind=GA4ParseErrorKind.MISSING_REQUIRED_FIELD,
            message="GA4 response missing required 'rows' field",
            user_message="No analytics data was found in the response.",
            retryable=False,
        )

    rows = api_response.get("rows", [])
    if not rows:
        return ConnectorError(
            kind=GA4ParseErrorKind.MISSING_REQUIRED_FIELD,
            message="GA4 response contains empty rows array",
            user_message="No analytics data was found for this period.",
            retryable=False,
        )

    parsed_rows: list[dict[str, Any]] = []
    parse_warnings: list[str] = []

    for row_number, row in enumerate(rows, start=1):
        try:
            parsed_row = _parse_ga4_row(row, row_number)
            if parsed_row:
                parsed_rows.append(parsed_row)
        except ValueError as e:
            parse_warnings.append(f"Row {row_number}: {str(e)}")
            continue

    if not parsed_rows:
        return ConnectorError(
            kind=GA4ParseErrorKind.INVALID_RESPONSE_FORMAT,
            message="All GA4 rows failed parsing",
            user_message="The analytics data format was invalid.",
            retryable=False,
        )

    return RawResponse(
        parsed_rows=parsed_rows,
        row_count=len(parsed_rows),
        parse_warnings=parse_warnings,
    )


def _parse_ga4_row(row: dict[str, Any], row_number: int) -> dict[str, Any] | None:
    """Parse a single GA4 row into canonical format.

    GA4 response structure:
    {
        "dimensions": ["2026-01-01"],  # date
        "metrics": [
            {"value": "100"},  # sessions
            {"value": "20"},   # bounces
        ]
    }

    Returns dict matching CSV parsed format:
    {
        "date": "2026-01-01",
        "sessions": 100,
        "bounces": 20,
    }
    """
    dimensions = row.get("dimensions", [])
    metrics = row.get("metrics", [])

    if not dimensions or not metrics:
        raise ValueError("Missing dimensions or metrics")

    # Extract date from dimensions (GA4 standard order: date first)
    date_str = dimensions[0] if len(dimensions) > 0 else None
    if not date_str:
        raise ValueError("Missing date dimension")

    # Validate date format (YYYY-MM-DD)
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}") from None

    # Extract metric values (GA4 standard order: sessions, bounces)
    sessions = int(metrics[0].get("value", "0")) if len(metrics) > 0 else 0
    bounces = int(metrics[1].get("value", "0")) if len(metrics) > 1 else 0

    # Validate metric constraints
    if bounces > sessions:
        raise ValueError(f"bounces ({bounces}) exceeds sessions ({sessions})")

    return {
        "date": date_str,
        "sessions": sessions,
        "bounces": bounces,
        # Note: GA4 provides sessions/bounces only for this connector
        # Campaign attribution would require additional dimensions
    }
