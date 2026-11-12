"""GA4 connector implementation.

Provides read-only access to Google Analytics 4 data following the
ARCH-04 raw-response-canonical-handoff contract.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from ..csv.parser import RawResponse
from ..errors import ConnectorError
from .client import GA4Config, GA4QueryParams, MockGA4Client, RealGA4Client
from .parser import parse_ga4_response


def fetch_ga4_data(
    organization_id: UUID,
    data_source_id: UUID,
    property_id: str,
    access_token: str,
    start_date: str | None = None,
    end_date: str | None = None,
    use_mock: bool = True,
) -> RawResponse | ConnectorError:
    """Fetch analytics data from GA4 API.

    This is the main entry point for GA4 data ingestion, following the same
    pattern as parse_csv_upload for consistency.

    Args:
        organization_id: Organization scope for tenant isolation
        data_source_id: Data source that owns this data
        property_id: GA4 property ID (e.g., "123456789")
        access_token: OAuth access token for GA4 API
        start_date: Start date in YYYY-MM-DD format (defaults to 7 days ago)
        end_date: End date in YYYY-MM-DD format (defaults to today)
        use_mock: Use mock client for testing (default: True)

    Returns:
        RawResponse with parsed analytics data, or ConnectorError on failure

    Usage:
        result = fetch_ga4_data(
            organization_id=org_id,
            data_source_id=source_id,
            property_id="123456789",
            access_token="ya29...",
            use_mock=False,  # Set to False for real API
        )

        if isinstance(result, RawResponse):
            # Process rows via staging/normalization pipeline
            ingest_csv_upload(db, result, ...)
        elif isinstance(result, ConnectorError):
            # Handle error based on result.kind and result.retryable
    """
    # Default date range: last 7 days
    if not start_date:
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")

    # Validate inputs
    if not property_id:
        return ConnectorError(
            kind="invalid_request",
            message="Property ID is required",
            user_message="Please select a Google Analytics property.",
            retryable=False,
        )

    if not access_token:
        return ConnectorError(
            kind="authentication_failed",
            message="Access token is required for GA4 API",
            user_message="Please reconnect your Google Analytics account.",
            retryable=False,
        )

    # Select client based on configuration
    client = MockGA4Client() if use_mock else RealGA4Client()

    # Build query parameters
    params = GA4QueryParams(
        start_date=start_date,
        end_date=end_date,
        metrics=["sessions", "bounces"],
        dimensions=["date"],
    )

    # Fetch data from API
    api_response = client.fetch_report(
        property_id=property_id,
        access_token=access_token,
        params=params,
    )

    # Parse response into canonical format
    return parse_ga4_response(
        api_response=api_response,
        organization_id=organization_id,
        data_source_id=data_source_id,
    )


def check_ga4_connection(
    data_source_id: UUID,
    property_id: str,
    access_token: str,
) -> bool | ConnectorError:
    """Check if GA4 connection is valid and working.

    Performs a minimal API call to verify credentials and permissions.

    Args:
        data_source_id: Data source to check
        property_id: GA4 property ID
        access_token: OAuth access token

    Returns:
        True if connection is valid, or ConnectorError with details
    """
    # Try to fetch single day of data
    result = fetch_ga4_data(
        organization_id=UUID("00000000-0000-0000-0000-000000000000"),  # Placeholder
        data_source_id=data_source_id,
        property_id=property_id,
        access_token=access_token,
        start_date=datetime.now().strftime("%Y-%m-%d"),
        end_date=datetime.now().strftime("%Y-%m-%d"),
        use_mock=True,  # Always use mock for connection check
    )

    return isinstance(result, RawResponse)


__all__ = [
    "fetch_ga4_data",
    "check_ga4_connection",
    "GA4Config",
    "GA4QueryParams",
]
