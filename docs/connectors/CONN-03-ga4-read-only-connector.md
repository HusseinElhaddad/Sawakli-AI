# CONN-03 — Implement GA4 Read-Only Connector Attempt

## 1. Overview

**Status:** Implemented (Mock client ready; Real client blocked by external dependencies)  
**Owner:** Connector Layer  
**Deadline:** Thu 29 Oct 23:59 Africa/Cairo (2026-10-29)

Proves one real external read integration without making the MVP dependent on external approval. Implements GA4 connector following the ARCH-04 raw-response-canonical-handoff contract with typed errors for auth, rate-limit, and timeout scenarios.

## 2. Scope

### In Scope

- GA4 read path returning RawResponse from real/test account when credentials permit
- Typed errors for authentication failures, rate limits, and timeouts
- Mock GA4 client for development without external API access
- Parser converting GA4 API responses to canonical RawResponse format
- Documentation of blockers if external access prevents completion
- CSV fallback remains fully usable

### Out of Scope

- OAuth token exchange flow (handled by existing oauth/ infrastructure)
- GA4 property selection UI (API-03 responsibility)
- Worker retry orchestration (WORK-03)
- Real Google Cloud project setup (external dependency)

## 3. Prerequisites

- **CONN-02:** OAuth credentials infrastructure (implemented in `connectors/oauth/`)
- **ARCH-04:** Connector-to-Data handoff contracts (accepted)
- **ING-01:** Data-owned ingestion service (implemented)
- **API-03:** Authenticated API routes (implemented)
- Raw-response-canonical-handoff contract (accepted 2026-10-08)

## 4. Architecture

The GA4 connector follows the same pattern as the CSV connector:

```
GA4 Property
    ↓ (via Google Analytics Data API)
GA4APIClient.fetch_report()
    ↓ Returns dict response or ConnectorError
parse_ga4_response()
    ↓ Returns RawResponse or ConnectorError
Data-owned ingest_csv_upload()
    ↓
Canonical tables (campaigns, daily_metrics, ga_events)
```

**Ownership:**
- Connector: Parse GA4 API responses, return typed errors
- Data: Persist raw evidence, normalize to canonical format
- API: Authenticate, validate org ownership, handle HTTP
- Worker: Retry policy based on error.retryable flag

## 5. Step-by-Step Implementation Walkthrough

### Practical Outcome

This task provides a GA4 connector path that can be exercised safely in development today through a
mock client, while preserving the production contract shape expected by the connector and data
layers. It also standardizes typed error behavior so API and Worker handling can remain consistent
with existing connector semantics.

### Acceptance Criteria → Steps and Evidence

| Acceptance Criterion | Implementation Step(s) | Verification Evidence / Status |
|---|---|---|
| Return connector output in raw-response contract shape | Steps 1–3 | `python -m pytest tests/unit/connectors/ga4/test_client.py -v` — PASS |
| Expose typed retryable vs non-retryable GA4 errors | Steps 1, 2 | `python -m pytest tests/unit/connectors/ga4/test_client.py -v` — PASS |
| Keep development unblocked without external GA4 access | Step 1 | Mock-client unit coverage in `test_client.py` — PASS |
| Document external blocker evidence without misreporting implementation state | Step 4 | Documentation review in this PR — PASS |

### Step 1 — Implement Connector Clients

- **What:** Add a mock GA4 client for deterministic local and CI behavior, and a real-client entry
  point that returns a clear blocked status until external provisioning exists.
- **Where:** `apps/backend/src/sawakli/connectors/ga4/client.py`
- **How it works:** The connector validates required inputs, then routes through mock or real client
  mode; real mode currently returns typed blocked behavior instead of pretending external readiness.
- **Testing:** Unit tests validate required-token and required-property behavior and blocked real
  client behavior.

### Step 2 — Implement GA4 Parsing and Error Semantics

- **What:** Convert GA4-style rows into canonical raw-response payloads and classify connector
  errors for retry handling.
- **Where:** `apps/backend/src/sawakli/connectors/ga4/parser.py`,
  `apps/backend/src/sawakli/connectors/ga4/connector.py`
- **How it works:** Parser-level validation filters malformed rows, records warnings, and returns
  typed connector errors for empty or structurally invalid responses.
- **Testing:** Unit tests validate successful parsing, malformed-date handling, metric constraints,
  and empty/malformed response behavior.

### Step 3 — Expose Connector Entry Points

- **What:** Provide module-level GA4 entry points aligned to connector-layer usage.
- **Where:** `apps/backend/src/sawakli/connectors/ga4/__init__.py`
- **How it works:** Public exports provide one consistent import surface for connector usage and
  tests, while keeping implementation details in dedicated modules.
- **Testing:** Unit tests call public entry points and validate behavior across default and custom
  date ranges.

### Step 4 — Record Blockers and Operational Boundaries

- **What:** Document real-integration prerequisites that are external to repository code ownership.
- **Where:** This task document (`docs/connectors/CONN-03-ga4-read-only-connector.md`)
- **How it works:** The document distinguishes implemented behavior from deferred external setup and
  captures why CSV fallback remains operationally sufficient for current scope.
- **Testing:** Documentation governance check validates required structure; connector tests verify
  implemented behavior.

## 6. Inputs

| Field / Input | Type | Required | Source | Description |
|---|---|---|---|---|
| `organization_id` | UUID | Yes | Auth token | Organization scope for tenant isolation |
| `data_source_id` | UUID | Yes | API route | Must belong to authenticated org |
| `property_id` | str | Yes | User selection | GA4 property ID (e.g., "123456789") |
| `access_token` | str | Yes | OAuth token store | Encrypted at rest, decrypted for API calls |
| `start_date` | str | No | API parameter | YYYY-MM-DD format (defaults to 7 days ago) |
| `end_date` | str | No | API parameter | YYYY-MM-DD format (defaults to today) |

## 7. Outputs

| Field / Output | Type | Nullable | Consumer | Description |
|---|---|---|---|---|
| `RawResponse.parsed_rows` | list[dict] | No | Data layer | Parsed analytics rows |
| `RawResponse.row_count` | int | No | Data layer | Number of successfully parsed rows |
| `RawResponse.parse_warnings` | list[str] | No | Data layer | Warnings for skipped rows |
| `ConnectorError.kind` | str | No | Worker/API | Error classification for retry logic |
| `ConnectorError.message` | str | No | Logging | Internal error details |
| `ConnectorError.user_message` | str | No | UI | User-friendly error message |
| `ConnectorError.retryable` | bool | No | Worker | Whether Worker should retry |

## 8. Rules and Semantics

### Error Classification

| Error Kind | Retryable? | User Message |
|------------|------------|--------------|
| `AUTHENTICATION_FAILED` | No | "Please reconnect your Google Analytics account." |
| `RATE_LIMIT_EXCEEDED` | Yes | "Too many requests. We'll try again shortly." |
| `TIMEOUT` | Yes | "The request took too long. Please try again." |
| `PERMISSION_DENIED` | No | "You don't have access to this GA4 property." |
| `INVALID_REQUEST` | No | "Please select a valid Google Analytics property." |
| `NO_DATA` | No | "No analytics data was found for this period." |

### Data Validation

- Date format: YYYY-MM-DD (validated via `datetime.strptime`)
- Metric constraints: `bounces <= sessions` (rows violating this are skipped with warnings)
- Empty responses: Return `ConnectorError` (not empty `RawResponse`)
- Malformed rows: Skipped with parse warnings (partial success allowed)

## 9. Public Interfaces

### Module: `sawakli.connectors.ga4`

```python
def fetch_ga4_data(
    organization_id: UUID,
    data_source_id: UUID,
    property_id: str,
    access_token: str,
    start_date: str | None = None,
    end_date: str | None = None,
    use_mock: bool = True,
) -> RawResponse | ConnectorError:
    """Fetch analytics data from GA4 API."""

def check_ga4_connection(
    data_source_id: UUID,
    property_id: str,
    access_token: str,
) -> bool | ConnectorError:
    """Check if GA4 connection is valid."""

class MockGA4Client:
    """Mock GA4 client for testing without external API access."""
    def fetch_report(...) -> dict[str, Any] | ConnectorError: ...

class RealGA4Client:
    """Real GA4 API client (BLOCKED: requires external setup)."""
    def fetch_report(...) -> dict[str, Any] | ConnectorError: ...
```

## 10. Data Ownership

### Reads

- OAuth access token from `connector_tokens` (Connector-owned, encrypted)
- `data_sources` row to verify org ownership (API-03 responsibility)

### Writes

- None (Connector only reads and parses; Data layer owns persistence)

### Must Never Read

- Unencrypted credentials or tokens
- Data from other organizations

### Must Never Write

- Database tables (Data layer responsibility)
- Unencrypted credentials to logs or errors

## 11. Security

- Access tokens encrypted at rest via AES-256-GCM (existing `oauth/crypto.py`)
- Organization isolation enforced at API layer before calling connector
- Error messages never expose token values or credentials
- Safe user messages hide internal implementation details

## 12. Error and Edge-Case Behavior

| Scenario | Behavior |
|----------|----------|
| Missing access token | `ConnectorError(AUTHENTICATION_FAILED, retryable=False)` |
| Empty property ID | `ConnectorError(INVALID_REQUEST, retryable=False)` |
| No rows in response | `ConnectorError(NO_DATA, retryable=False)` |
| Malformed date | Row skipped with warning in `parse_warnings` |
| bounces > sessions | Row skipped with warning |
| All rows invalid | `ConnectorError(INVALID_RESPONSE_FORMAT, retryable=False)` |

## 13. Testing

### Unit Tests

Location: `apps/backend/tests/unit/connectors/ga4/test_client.py`

Coverage (16 tests):

**MockGA4Client:**
- `test_fetch_report_returns_valid_data` — verifies mock returns GA4-formatted data
- `test_fetch_report_requires_access_token` — validates auth requirement
- `test_fetch_report_requires_property_id` — validates property ID requirement

**RealGA4Client:**
- `test_real_client_returns_blocked_error` — documents external blocker

**GA4 Parser:**
- `test_parse_valid_ga4_response` — converts GA4 format to RawResponse
- `test_parse_handles_invalid_date` — skips malformed dates with warnings
- `test_parse_handles_bounces_exceeds_sessions` — validates metric constraints
- `test_parse_returns_error_for_empty_response` — handles empty data
- `test_parse_returns_error_for_missing_rows_key` — handles malformed responses

**fetch_ga4_data:**
- `test_fetch_ga4_data_with_defaults` — works with default date range (last 7 days)
- `test_fetch_ga4_data_with_custom_date_range` — respects custom dates
- `test_fetch_ga4_data_requires_property_id` — validates inputs
- `test_fetch_ga4_data_requires_access_token` — validates credentials

**Error Handling:**
- `test_authentication_failed_is_not_retryable` — verifies error classification
- `test_rate_limit_is_retryable` — verifies retry logic
- `test_timeout_is_retryable` — verifies transient error handling

Run: `pytest tests/unit/connectors/ga4/test_client.py -v`

### Integration Tests

Not implemented — requires real GA4 property with traffic data (external blocker).

## 14. Verification

### Type Checking

```bash
cd apps/backend
python -m mypy src/sawakli/connectors/ga4/
```

**Result:** PASS — no errors

### Linting

```bash
cd apps/backend
ruff check src/sawakli/connectors/ga4/ tests/unit/connectors/ga4/
ruff format --check src/sawakli/connectors/ga4/ tests/unit/connectors/ga4/
```

**Result:** PASS — All checks passed! 6 files already formatted

### Unit Tests

```bash
cd apps/backend
python -m pytest tests/unit/connectors/ga4/test_client.py -v
```

**Result:** PASS — 16 passed in 0.09s

## 15. Known Limitations

### 1. Real GA4 API Integration: BLOCKED

**Blocker Evidence:**
- Requires Google Cloud project with Analytics Data API enabled
- Needs OAuth 2.0 credentials with `analytics.read` scope
- Requires approval from Google for production OAuth consent screen
- Needs real GA4 property with traffic data for validation
- Would need `google-analytics-data` Python client library (`pip install google-analytics-data`)

**Impact:**
- Real GA4 client returns `ConnectorError(AUTHENTICATION_FAILED)` with message: "Real GA4 API integration blocked: No external project configured"
- CSV connector remains the primary data source for Month One MVP
- Mock client allows development and testing to proceed

**Workaround:**
- Mock client demonstrates architecture and validates error handling
- Definition of Done met: "If external access blocks completion, blocker evidence is documented and CSV fallback remains fully usable"

### 2. Campaign Attribution

GA4 API returns sessions/bounces aggregated by date but does not include campaign attribution by default. Full integration would require:
- Additional dimensions: `campaignName`, `sessionSource`, `sessionMedium`
- UTM parameter tracking in GA4
- Mapping GA4 campaign names to internal campaigns table

Current implementation focuses on sessions/bounces metrics only, matching the existing CSV connector schema.

### 3. Rate Limiting

No rate limit detection implemented in mock client. Real implementation would need to:
- Detect HTTP 429 responses from GA4 API
- Parse `Retry-After` header for backoff duration
- Return `ConnectorError(RATE_LIMIT_EXCEEDED, retryable=True)`

### 4. OAuth Token Refresh

Token refresh is handled by existing `oauth/tokens.py` infrastructure but not integrated into GA4 connector flow. API layer responsible for refreshing near-expiry tokens before calling connector.

## 16. Follow-Up Tasks

1. **External Setup (Blocked):**
   - Create Google Cloud project with Analytics Data API enabled
   - Configure OAuth credentials for `analytics.read` scope
   - Submit OAuth consent screen for Google approval
   - Obtain real GA4 property for testing

2. **Real API Implementation:**
   - Install `google-analytics-data` Python library
   - Implement `RealGA4Client.fetch_report()` using `BetaAnalyticsDataClient`
   - Map Google API exceptions to `ConnectorError` types
   - Handle rate limiting with exponential backoff

3. **Campaign Attribution:**
   - Add `campaignName` dimension to GA4 queries
   - Map GA4 campaigns to internal campaigns table
   - Handle UTM parameter variations

4. **API Route Integration:**
   - Create `/api/connectors/ga4/{data_source_id}/fetch` endpoint
   - Wire up OAuth token retrieval from `connector_tokens`
   - Call `fetch_ga4_data()` and `ingest_csv_upload()`
   - Return progress/status to UI

5. **UI Integration:**
   - GA4 property selection dropdown
   - Date range picker
   - Connection status indicator
   - Error message display

## 17. References and Evidence

- **Contract:** [docs/contracts/raw-response-canonical-handoff.md](../contracts/raw-response-canonical-handoff.md)
- **Architecture:** [docs/architecture/ARCH-04-connector-to-data-handoff-contracts.md](../architecture/ARCH-04-connector-to-data-handoff-contracts.md)
- **OAuth Infrastructure:** [apps/backend/src/sawakli/connectors/oauth/](../../apps/backend/src/sawakli/connectors/oauth/)
- **CSV Reference:** [apps/backend/src/sawakli/connectors/csv/parser.py](../../apps/backend/src/sawakli/connectors/csv/parser.py)

**Implementation Evidence:**
- Files added: `src/sawakli/connectors/ga4/client.py`, `src/sawakli/connectors/ga4/parser.py`, `src/sawakli/connectors/ga4/connector.py`, `tests/unit/connectors/ga4/test_client.py`
- Files modified: `src/sawakli/connectors/ga4/__init__.py`
- Tests: 16 unit tests PASS
- Verification: mypy PASS, ruff PASS

**Definition of Done:**
- ✅ One GA4 read path returns RawResponse (mock client implemented)
- ✅ Auth, rate-limit and timeout errors are typed (error classification complete)
- ✅ External blocker documented (Real GA4 API requires external Google Cloud setup)
- ✅ CSV fallback remains fully usable (no changes to CSV connector)

**Blocker Documentation:**
The real GA4 API integration is blocked by external dependencies (Google Cloud project, OAuth approval, real GA4 property). The mock client demonstrates the connector architecture and proves the error handling patterns work correctly. CSV upload remains the primary data source for Month One MVP, keeping the project on schedule without external dependencies.
