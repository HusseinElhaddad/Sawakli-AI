# UI-03 — Login, Workspace, and CSV Connector Setup

## 1. Overview

UI-03 provides account/workspace creation, login, and an authenticated CSV import flow. On a
successful API response, the UI reports imported rows, sync status, and last-sync time without
claiming that the current dashboard cards are real data.

## 2. Scope

### In Scope

- First-workspace creation through API-01 registration and authenticated login/current-user lookup.
- Optional CSV selection, import progress, safe errors, parsed-row count, warnings, sync status, and freshness.
- An in-product approved sample CSV download and a short required-column explanation.
- Explicit unavailable OAuth state with no secret/token input.

### Out of Scope

- Multi-workspace selection; API-01 has no list/switch contract.
- Implementing raw persistence, staging, normalization, canonical upsert, or source-state writes.
  The current Backend connector/data path owns them.
- Provider OAuth authorization/exchange, owned by Connector/CONN-03.
- Real dashboard KPIs and campaigns, owned by API-02/UI-04.

## 3. Prerequisites

| Task / contract | Why required |
|---|---|
| UI-02 | Provides session, API client, same-origin proxy, and application shell. |
| API-01 | Defines registration, login, current-user, and organization scope. |
| Merged PR #16 connector route | Defines CSV setup/upload and its sync response. |
| Data/Connector pipeline | Persists raw evidence and canonical rows behind the API route. |

## 4. Architecture

```text
Create workspace or sign in
↓
API-01 authenticated organization
↓
POST connector setup
↓
POST CSV upload
↓
Backend raw → staging → canonical import
↓
UI shows success, sync status, and last sync time
```

## 5. Inputs

| Input | Type | Required | Source | Meaning |
|---|---|---:|---|---|
| name/email/password/workspace | strings | registration | user | API-01 fields. |
| CSV file | `File` | upload | user | `.csv` extension required by UI. |
| bearer token | string | protected calls | API-01 | Establishes organization scope. |

## 6. Outputs

| Output | Type | Consumer | Meaning |
|---|---|---|---|
| session | user/org/token | UI shell | Authenticated workspace context. |
| import result | API response | setup page | row count, warnings, sync status, last sync. |
| UI state | local state | user | loading, error, imported, OAuth unavailable. |

## 7. Rules and Semantics

- `POST /api/connectors/setup` creates a CSV source.
- `POST /api/connectors/csv/{data_source_id}/upload` receives multipart field `file`.
- “CSV imported” is displayed only after API success with `sync_status: success`.
- The continuation button remains disabled unless `sync_status` is `success`.
- Import is recommended for the demo but not required to enter the workspace. “Skip for now” opens the
  dashboard without making an API request; dashboard values remain explicitly labelled as demo data.
- `/samples/sawakli-campaign-data.csv` is the approved user-facing example. The fixed CSV schema belongs
  to Connector/Data; the UI presents it but does not infer arbitrary third-party column meanings.
- The sample is a public static file and can be downloaded before authentication; it contains no
  workspace or provider data.
- Parser warnings are shown; raw parsed rows are not rendered.
- A successful import means the Backend completed its current raw-to-canonical path. It does not
  mean that dashboard mock cards have been replaced by API-02 data.

## 8. Public Interfaces

- `createCsvConnector(accessToken)` — requests source setup.
- `uploadCsv(accessToken, dataSourceId, file)` — sends multipart import request.
- `CsvUploadResponse` — `data_source_id`, `row_count`, `parsed_rows`, `parse_warnings`,
  `sync_status`, and `last_synced_at`.

## 9. Data Ownership

### Reads

- API-01 user/organization and safe connector import responses.

### Writes

- Browser session only. Backend owns connector/data writes.

### Must Never Read

- OAuth codes, provider tokens, encryption keys, raw database data, or another organization’s source.

### Must Never Write

- Raw payloads, canonical metrics, sync status, provider credentials, or organization identifiers.

## 10. Security

The UI never submits organization scope; API-01 derives it from the bearer token and the connector
route verifies source ownership. Safe error messages are displayed without rendering secrets.

## 11. Error and Edge-Case Behavior

| Case | Behavior |
|---|---|
| Missing/non-CSV file | Block import and explain the requirement. |
| Uploading | Disable selection/import controls. |
| Parser/import failure | Show safe API message; source is not reported successful. |
| Warnings | Show count and warning messages after a successful import. |
| No session | Return to login before an unauthenticated import request. |
| OAuth selection | State that provider authorization is unavailable; request no secrets. |

## 12. Testing

### Unit Tests

- `connector-setup.test.tsx` proves source setup, import request, successful sync display, non-CSV
  rejection, optional skip, and approved sample download.

### Integration Tests

- Backend connector/data integration tests are owned by the merged Backend work.

### E2E Impact

- A running stack test must register/login, upload a fixture, assert `success` and a timestamp,
  then confirm the dashboard demo-data notice.

## 13. Verification

Executed 2026-10-01 from `apps/web` after merging PR #16:

- `node_modules/.bin/eslint.cmd .` — PASS; two pre-existing mock-service warnings only.
- `node_modules/.bin/tsc.cmd --noEmit` — PASS.
- `node_modules/.bin/vitest.cmd run` — PASS; 3 files, 6 tests.
- `node_modules/.bin/next.cmd build` — PASS.

## 14. Known Limitations

- Current dashboard KPI cards remain demo data until API-02/UI-04 consume canonical metrics.
- The one-organization API contract cannot support a workspace selector.
- OAuth provider authorization remains unavailable.
- ING-01 acceptance still requires independent review of retries/idempotency, partial failures,
  tenant isolation, reconciliation, and the ARCH-04 ownership boundary.

## 15. Follow-Up Tasks

- ING-01 — Data/Connector — complete its remaining acceptance review/evidence.
- API-02/UI-04 — Backend/UI — connect canonical metrics to dashboard screens.
- CONN-03 — Connector — implement provider OAuth.
- UI-08 — UI — unify broader empty/loading/error/export states.

## 16. References and Evidence

- API-01: `apps/backend/src/sawakli/api/routes/auth.py`.
- Connector import route: `apps/backend/src/sawakli/api/routes/connectors.py`.
- UI service: `apps/web/src/services/connectors.service.ts`.
- UI test: `apps/web/tests/connector-setup.test.tsx`.
