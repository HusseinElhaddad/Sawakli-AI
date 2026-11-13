# Release and Demo Checklist

Run this checklist before any supervisor demo or release cut. It is maintained by System QA and was
introduced by [QA-00](QA-00-contract-validators-and-integration-harness.md). Every item has a
command, an expected result and an owner. Record each result as `PASS`, `FAIL` or
`NOT RUN — <reason>`; never mark an item from memory or from the GitHub web UI alone.

Commands assume a clone of the repository root, Node 24, Docker, and a Python 3.12 environment with
the backend installed (`pip install -e "apps/backend[dev]"`). Shell examples use bash; on Windows
PowerShell set variables with `$env:NAME = "value"` instead of `export`.

## 1. Preconditions

| # | Check | Command | Expected | Owner |
|---|---|---|---|---|
| 1.1 | Release commit identified | `git fetch origin && git rev-parse origin/main` | SHA recorded in the sign-off table | System QA |
| 1.2 | Working tree clean | `git status --porcelain` | No output | System QA |
| 1.3 | Open PRs reviewed | `gh pr list --state open` | Each open PR is either merged, or recorded as excluded from this release | Project lead |
| 1.4 | No real secrets in the tree | `git ls-files \| grep -E '(^\|/)\.env$'` | No output (only `.env.example` is tracked) | System QA |

## 2. CI on the exact commit

| # | Check | Command | Expected | Owner |
|---|---|---|---|---|
| 2.1 | All check runs green on the release SHA | `gh api repos/elfaroukomaradmission-a11y/Sawakli-AI/commits/<sha>/check-runs --jq '.check_runs[] \| [.name, .conclusion] \| @tsv'` | `Contracts`, `Backend`, `Frontend`, `Integration` all `success`; `Documentation governance` `success` on the PR that produced the commit | System QA |
| 2.2 | No skipped real-database tests | Open the `Backend` job log, `Tests` step | The step prints `skipped tests: 0` (the job fails on any skip) and the pytest summary has no `skipped` count | System QA |

## 3. Contract checks

| # | Check | Command | Expected | Owner |
|---|---|---|---|---|
| 3.1 | All contract validators and negative tests | `node scripts/run-contracts.mjs` | `5/5 PASS`; the negative suite reports every injected mismatch caught and `canonical.json` unchanged | System QA |
| 3.2 | Known deviations reviewed | Read `tests/contracts/known-deviations.json` | Every entry still has an owner and an open follow-up; any `breaking-mismatch` entry is either fixed or explicitly accepted for this demo by its owner | System QA + entry owners |

## 4. Integration harness

Uses the Compose `postgres-test` service (host port 5434, synthetic password from
`docker-compose.yml`). Never point these commands at the team's `postgres` service. As a hard guard, `fresh-db`
refuses (before connecting) any database whose name is not plain `a-z0-9_` ending in `_test`, and
`roundtrip` any name not ending in `_roundtrip`; both refuse URLs with query parameters and check
`SELECT current_database()` after connecting, before any migration.

| # | Check | Command | Expected | Owner |
|---|---|---|---|---|
| 4.1 | Start the test database | `docker compose up -d postgres-test` | Container `sawakli-test-postgres` healthy | System QA |
| 4.2 | Fresh, migrated test databases | `export DATABASE_URL=postgresql+psycopg://postgres:change-me@localhost:5434/sawakli_test TEST_DATABASE_URL=postgresql+psycopg://postgres:change-me@localhost:5434/sawakli_integration_test` then `python scripts/integration_harness.py fresh-db DATABASE_URL TEST_DATABASE_URL` | Two `PASS fresh-db` lines | System QA |
| 4.3 | Backend suite against real PostgreSQL | `(cd apps/backend && pytest -rs)` (returns to the repository root) | All passed, no `skipped` count in the summary line (QA-00 baseline: 296 passed after merging `main` `7c66664`) | System QA |
| 4.4 | Migration round-trip on a fresh server | `docker run -d --rm --name sawakli-roundtrip -e POSTGRES_PASSWORD=<synthetic> -e POSTGRES_DB=sawakli_roundtrip -p 5435:5432 postgres:18`, then `ROUNDTRIP_DATABASE_URL=postgresql+psycopg://postgres:<synthetic>@localhost:5435/sawakli_roundtrip python scripts/integration_harness.py roundtrip`, then `docker rm -f sawakli-roundtrip` | `PASS roundtrip: 23 tables at head, 0 after downgrade base, 23 after re-upgrade` | System QA |

## 5. Demo login (API level)

| # | Check | Command | Expected | Owner |
|---|---|---|---|---|
| 5.1 | Seed the demo login on the demo database (never on a non-demo deployment: the seed has no environment guard) | With `DATABASE_URL` pointing at the demo database and `SAWAKLI_DEMO_PASSWORD` set (no leading/trailing spaces): `(cd apps/backend && python -m tests.fixtures.seed)` (run twice) | First run `created/updated`, second run `already up to date` | System QA |
| 5.2 | Login and organization | `POST /api/auth/login` with `demo@nourfashion.example`, then `GET /api/auth/me` | `200`; organization `Nour Fashion Co.` (`550e8400-e29b-41d4-a716-446655440000`) | System QA |
| 5.3 | Org-scoped action on seeded data | `POST /api/analysis/refresh` with campaign `770e8400-e29b-41d4-a716-44665544000a` | `202` with a `PENDING` job; a campaign from another organization returns `422` | System QA |
| 5.4 | Demo password handling | Inspect the terminal and any shared logs | The password appears nowhere; it was typed only into the environment variable | Presenter |

## 6. Supervisor demo flow (QA-04 story)

Status as verified on `main` at `622ed92` (14 Oct 2026); the Login (browser) and Dashboard rows were
re-verified on the UI-04 branch at `0f8b3fe` on 21 Oct 2026. Re-check each blocked row against the current board
before the demo.

| Step | Runnable today? | Evidence / blocking task |
|---|---|---|
| Login (API) | Yes | Section 5 |
| Login (browser) | Yes, once PR #22 (UI-02/UI-03, Abdulrahman Ehab) is merged | Real login through `lib/session.ts` and `/api/auth/me` comes from PR #22. Verified live in a browser as `demo@nourfashion.example` on commit `0f8b3fe` (branch `feature/UI-04-dashboard-kpis-campaign-table`, 21 Oct 2026), which is stacked on PR #22. Until PR #22 merges, `main` still has the mock login |
| Data source / demo data | Yes (API, by tests) | `POST /api/connectors/setup` and CSV upload are exercised by `apps/backend/tests/test_connectors_api.py` (passing); not run live during QA-00. Seeded 90-day Nour dataset from migration 0009 (verified live) |
| Dashboard | Yes, once PR #22 and UI-04 are merged | KPI cards and the campaign table render live API-02 data; verified against SQL on the seeded Nour dataset on commit `0f8b3fe` (branch `feature/UI-04-dashboard-kpis-campaign-table`, 21 Oct 2026). See [UI-04](../ui/UI-04-dashboard-kpis-and-campaign-table.md) §14. The anomaly and recommendation panels on the dashboard are still sample data |
| Analysis refresh queued | Yes (API) | Section 5.3; Worker-to-AI execution needs WORK-04 (El-Farouk Omar) |
| Anomaly / forecast | No | AI-02 (PR #19, open), AI-06 persistence (Hussein Elhaddad), API-05 (Ahmed Ibrahem) |
| Recommendation | No | AI-06 (Hussein Elhaddad), API-05 (Ahmed Ibrahem) |
| Simulation | No | AI-05 (Hussein Elhaddad) |
| Human decision | No | API-06 (El-Farouk Omar) |
| Export | No | API-08 (Ahmed Ibrahem) |

## 7. Known issues to state during the demo

- `forecasts.value` is optional in the AI output but `NOT NULL` in the database
  (`breaking-mismatch` in `known-deviations.json`); forecast persistence (AI-06) must handle it.
- `job_status_enum` includes `ERROR` in the database and Backend but not in `canonical.json` or the
  UI type (`contract-stale`); INT-01 decision pending.
- passlib logs `(trapped) error reading bcrypt version` on first hash; hashing works. Dependency
  pinning is a recorded follow-up.

## 8. Sign-off

| Role | Name | Date | Release SHA | Result |
|---|---|---|---|---|
| System QA | | | | |
| Project lead | | | | |
| Presenter | | | | |
