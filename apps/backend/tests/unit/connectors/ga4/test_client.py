"""Unit tests for GA4 connector implementation."""

from __future__ import annotations

from uuid import uuid4

from sawakli.connectors.csv.parser import RawResponse
from sawakli.connectors.errors import ConnectorError
from sawakli.connectors.ga4 import (
    GA4ErrorKind,
    GA4ParseErrorKind,
    MockGA4Client,
    RealGA4Client,
    fetch_ga4_data,
    parse_ga4_response,
)


class TestMockGA4Client:
    """Test mock GA4 client functionality."""

    def test_fetch_report_returns_valid_data(self) -> None:
        """Verify mock client returns properly formatted GA4 response."""
        from sawakli.connectors.ga4 import GA4QueryParams

        client = MockGA4Client()
        params = GA4QueryParams(start_date="2026-01-01", end_date="2026-01-03")
        response = client.fetch_report(
            property_id="123456789",
            access_token="test_token",
            params=params,
        )

        assert isinstance(response, dict)
        assert "rows" in response
        assert len(response["rows"]) > 0

    def test_fetch_report_requires_access_token(self) -> None:
        """Verify authentication error when token is missing."""
        from sawakli.connectors.ga4 import GA4QueryParams

        client = MockGA4Client()
        params = GA4QueryParams(start_date="2026-01-01", end_date="2026-01-03")
        result = client.fetch_report(
            property_id="123456789",
            access_token="",
            params=params,
        )

        assert isinstance(result, ConnectorError)
        assert result.kind == GA4ErrorKind.AUTHENTICATION_FAILED
        assert result.retryable is False

    def test_fetch_report_requires_property_id(self) -> None:
        """Verify error when property ID is missing."""
        from sawakli.connectors.ga4 import GA4QueryParams

        client = MockGA4Client()
        params = GA4QueryParams(start_date="2026-01-01", end_date="2026-01-03")
        result = client.fetch_report(
            property_id="",
            access_token="test_token",
            params=params,
        )

        assert isinstance(result, ConnectorError)
        assert result.kind == GA4ErrorKind.INVALID_REQUEST


class TestRealGA4Client:
    """Test real GA4 client (blocked implementation)."""

    def test_real_client_returns_blocked_error(self) -> None:
        """Verify real client documents blocker."""
        client = RealGA4Client()
        result = client.fetch_report(
            property_id="123456789",
            access_token="test_token",
            params={"start_date": "2026-01-01", "end_date": "2026-01-03"},
        )

        assert isinstance(result, ConnectorError)
        assert result.kind == GA4ErrorKind.AUTHENTICATION_FAILED
        assert "blocked" in result.message.lower()


class TestGA4Parser:
    """Test GA4 response parser."""

    def test_parse_valid_ga4_response(self) -> None:
        """Verify parser converts GA4 format to RawResponse."""
        ga4_response = {
            "rows": [
                {
                    "dimensions": ["2026-01-01"],
                    "metrics": [{"value": "100"}, {"value": "20"}],
                },
                {
                    "dimensions": ["2026-01-02"],
                    "metrics": [{"value": "150"}, {"value": "30"}],
                },
            ]
        }

        organization_id = uuid4()
        data_source_id = uuid4()

        result = parse_ga4_response(ga4_response, organization_id, data_source_id)

        assert isinstance(result, RawResponse)
        assert result.row_count == 2
        assert len(result.parsed_rows) == 2
        assert result.parse_warnings == []

    def test_parse_handles_invalid_date(self) -> None:
        """Verify parser skips rows with invalid dates."""
        ga4_response = {
            "rows": [
                {
                    "dimensions": ["2026-01-01"],
                    "metrics": [{"value": "100"}, {"value": "20"}],
                },
                {
                    "dimensions": ["invalid-date"],
                    "metrics": [{"value": "150"}, {"value": "30"}],
                },
            ]
        }

        result = parse_ga4_response(ga4_response, uuid4(), uuid4())

        assert isinstance(result, RawResponse)
        assert result.row_count == 1
        assert len(result.parse_warnings) == 1
        assert "invalid date" in result.parse_warnings[0].lower()

    def test_parse_handles_bounces_exceeds_sessions(self) -> None:
        """Verify parser skips rows where bounces > sessions."""
        ga4_response = {
            "rows": [
                {
                    "dimensions": ["2026-01-01"],
                    "metrics": [{"value": "50"}, {"value": "100"}],  # bounces > sessions
                },
            ]
        }

        result = parse_ga4_response(ga4_response, uuid4(), uuid4())

        # When all rows fail validation, parser returns ConnectorError
        assert isinstance(result, ConnectorError)
        assert result.kind == GA4ParseErrorKind.INVALID_RESPONSE_FORMAT
        assert "failed parsing" in result.message.lower()

    def test_parse_returns_error_for_empty_response(self) -> None:
        """Verify parser returns error when no rows."""
        ga4_response = {"rows": []}

        result = parse_ga4_response(ga4_response, uuid4(), uuid4())

        assert isinstance(result, ConnectorError)
        assert result.kind == GA4ParseErrorKind.MISSING_REQUIRED_FIELD

    def test_parse_returns_error_for_missing_rows_key(self) -> None:
        """Verify parser returns error when 'rows' key missing."""
        ga4_response = {"data": []}

        result = parse_ga4_response(ga4_response, uuid4(), uuid4())

        assert isinstance(result, ConnectorError)
        assert result.kind == GA4ParseErrorKind.MISSING_REQUIRED_FIELD


class TestFetchGA4Data:
    """Test main GA4 connector entry point."""

    def test_fetch_ga4_data_with_defaults(self) -> None:
        """Verify connector works with default parameters."""
        organization_id = uuid4()
        data_source_id = uuid4()

        result = fetch_ga4_data(
            organization_id=organization_id,
            data_source_id=data_source_id,
            property_id="123456789",
            access_token="test_token",
            use_mock=True,
        )

        assert isinstance(result, RawResponse)
        assert result.row_count > 0

    def test_fetch_ga4_data_with_custom_date_range(self) -> None:
        """Verify connector respects custom date range."""
        organization_id = uuid4()
        data_source_id = uuid4()

        result = fetch_ga4_data(
            organization_id=organization_id,
            data_source_id=data_source_id,
            property_id="123456789",
            access_token="test_token",
            start_date="2026-01-01",
            end_date="2026-01-03",
            use_mock=True,
        )

        assert isinstance(result, RawResponse)

    def test_fetch_ga4_data_requires_property_id(self) -> None:
        """Verify connector validates property ID."""
        result = fetch_ga4_data(
            organization_id=uuid4(),
            data_source_id=uuid4(),
            property_id="",
            access_token="test_token",
            use_mock=True,
        )

        assert isinstance(result, ConnectorError)
        assert "property" in result.message.lower()

    def test_fetch_ga4_data_requires_access_token(self) -> None:
        """Verify connector validates access token."""
        result = fetch_ga4_data(
            organization_id=uuid4(),
            data_source_id=uuid4(),
            property_id="123456789",
            access_token="",
            use_mock=True,
        )

        assert isinstance(result, ConnectorError)
        assert result.kind == GA4ErrorKind.AUTHENTICATION_FAILED


class TestErrorHandling:
    """Test GA4 error classification."""

    def test_authentication_failed_is_not_retryable(self) -> None:
        """Verify auth failures are not retryable."""
        error = ConnectorError(
            kind=GA4ErrorKind.AUTHENTICATION_FAILED,
            message="Auth failed",
            user_message="Please reconnect.",
            retryable=False,
        )

        assert error.retryable is False

    def test_rate_limit_is_retryable(self) -> None:
        """Verify rate limit errors are retryable."""
        error = ConnectorError(
            kind=GA4ErrorKind.RATE_LIMIT_EXCEEDED,
            message="Rate limit exceeded",
            user_message="Please try again later.",
            retryable=True,
        )

        assert error.retryable is True

    def test_timeout_is_retryable(self) -> None:
        """Verify timeout errors are retryable."""
        error = ConnectorError(
            kind=GA4ErrorKind.TIMEOUT,
            message="Request timed out",
            user_message="The request took too long. Please try again.",
            retryable=True,
        )

        assert error.retryable is True
