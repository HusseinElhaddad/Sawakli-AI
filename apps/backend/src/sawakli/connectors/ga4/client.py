"""GA4 API client for reading analytics data.

This module implements the GA4 connector per CONN-03 requirements:
- One real external read integration
- Returns RawResponse from real/test account when credentials permit
- Typed errors for auth, rate-limit, and timeout scenarios
- Documented blockers if external access prevents completion
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from ..errors import ConnectorError

logger = logging.getLogger(__name__)


class GA4ErrorKind(str):
    """GA4-specific error codes."""

    AUTHENTICATION_FAILED = "authentication_failed"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    TIMEOUT = "timeout"
    INVALID_REQUEST = "invalid_request"
    NO_DATA = "no_data"
    PERMISSION_DENIED = "permission_denied"


@dataclass(frozen=True)
class GA4Config:
    """Configuration for GA4 API client."""

    property_id: str
    credentials: dict[str, Any]  # OAuth token or service account key
    timeout_seconds: int = 30
    max_retries: int = 3


@dataclass(frozen=True)
class GA4QueryParams:
    """Parameters for GA4 data query."""

    start_date: str  # YYYY-MM-DD
    end_date: str  # YYYY-MM-DD
    metrics: list[str] = field(default_factory=lambda: ["sessions", "bounces"])
    dimensions: list[str] = field(default_factory=lambda: ["date"])
    filters: dict[str, Any] | None = None


class GA4APIClient(Protocol):
    """Protocol for GA4 API client implementation."""

    def fetch_report(
        self,
        property_id: str,
        access_token: str,
        params: GA4QueryParams,
    ) -> dict[str, Any] | ConnectorError:
        """Fetch analytics report from GA4 API.

        Returns either:
        - dict with 'rows' key containing analytics data
        - ConnectorError with typed error kind
        """
        ...


class MockGA4Client:
    """Mock GA4 client for testing without external API access.

    This implementation allows CONN-03 to proceed even when:
    - No real GA4 credentials are available
    - External API access is blocked
    - Testing in isolated environments

    It demonstrates the connector architecture and validates error handling.
    """

    def fetch_report(
        self,
        property_id: str,
        access_token: str,
        params: GA4QueryParams,
    ) -> dict[str, Any] | ConnectorError:
        """Return mock GA4 data matching the expected schema.

        This simulates a successful GA4 API response for development/testing.
        """
        if not access_token:
            return ConnectorError(
                kind=GA4ErrorKind.AUTHENTICATION_FAILED,
                message="No access token provided for GA4 API",
                user_message="Please reconnect your Google Analytics account.",
                retryable=False,
            )

        if not property_id:
            return ConnectorError(
                kind=GA4ErrorKind.INVALID_REQUEST,
                message="Property ID is required for GA4 API",
                user_message="Please select a Google Analytics property.",
                retryable=False,
            )

        # Generate mock data matching GA4 response schema
        mock_rows = []
        current_date = datetime.strptime(params.start_date, "%Y-%m-%d")
        end_date = datetime.strptime(params.end_date, "%Y-%m-%d")

        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            mock_rows.append(
                {
                    "dimensions": [date_str],
                    "metrics": [
                        {"value": "100"},  # sessions
                        {"value": "20"},  # bounces
                    ],
                }
            )
            current_date = current_date.replace(day=current_date.day + 1)

        return {
            "rows": mock_rows,
            "total_rows": len(mock_rows),
            "property_id": property_id,
        }


class RealGA4Client:
    """Real GA4 API client using Google Analytics Data API.

    IMPORTANT: This implementation requires:
    1. Valid Google Cloud project with Analytics API enabled
    2. OAuth credentials or service account key
    3. Access to a GA4 property with analytics.read scope

    Implementation Status: BLOCKED
    - No external Google Cloud project available for testing
    - No GA4 property with real data for validation
    - OAuth credentials not configured in development environment

    BLOCKER EVIDENCE:
    - Would require Google Cloud project setup (outside MVP scope)
    - Need analytics.read OAuth scope approval from Google
    - Requires real GA4 property with traffic data

    This class is included for architectural completeness and future implementation.
    The CSV fallback connector remains fully usable and is the recommended path
    for Month One MVP.
    """

    def fetch_report(
        self,
        property_id: str,
        access_token: str,
        params: GA4QueryParams,
    ) -> dict[str, Any] | ConnectorError:
        """Fetch real GA4 data via Google Analytics Data API.

        Current Status: NOT IMPLEMENTED (Blocked)

        Would use google-analytics-data Python client library:
        ```
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import RunReportRequest

        client = BetaAnalyticsDataClient(credentials=credentials)
        request = RunReportRequest(property=f"properties/{property_id}", ...)
        response = client.run_report(request)
        ```

        Error handling would map to ConnectorError:
        - google.auth.exceptions.RefreshError → AUTHENTICATION_FAILED
        - google.api_core.exceptions.TooManyRequests → RATE_LIMIT_EXCEEDED
        - google.api_core.exceptions.DeadlineExceeded → TIMEOUT
        - google.api_core.exceptions.PermissionDenied → PERMISSION_DENIED
        """
        return ConnectorError(
            kind=GA4ErrorKind.AUTHENTICATION_FAILED,
            message="Real GA4 API integration blocked: No external project configured",
            user_message="GA4 integration is not yet available. Please use CSV upload.",
            retryable=False,
        )
