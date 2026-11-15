# Sawakli AI

Explainable marketing analytics and decision support for startups and small businesses.

Sawakli AI aims to turn campaign data into a clear view of performance, unusual changes,
short-term forecasts, recommendations, and bounded action simulations. The core product keeps
campaign changes under human control; live external writes are outside the core MVP.

This is a graduation project under active development. The repository contains working modules
and development infrastructure, but the complete CSV-to-AI-to-dashboard flow is still being
integrated.

## Start here

- [Current implementation](#current-implementation)
- [Architecture and repository layout](#architecture-and-repository-layout)
- [Run with Docker Compose](#run-with-docker-compose)
- [Local development](#local-development)
- [Testing and CI](#testing-and-ci)
- [Technical documentation](#technical-documentation)
- [Contributing](#contributing)
- [Team](#team)

## Current implementation

Reviewed on **15 November 2026** against `main` at
[`8c7dd67`](https://github.com/HusseinElhaddad/Sawakli-AI/commit/8c7dd678c808f0760285c39eed364887faed960c).
Implemented modules are distinguished from remaining product integration.

| Area | Implemented | Remaining integration |
|---|---|---|
| Web | Next.js layout, session/API client, API proxy, campaign/dashboard data path | Anomaly, recommendation and simulation services still contain mocks; full output serving remains API-05/UI work |
| API | Auth, campaign/dashboard, CSV setup/upload, refresh enqueue and job polling | Stored AI-output APIs and complete product flow |
| Connector/Data | CSV parsing and atomic raw-to-canonical ingestion, entity normalization, OAuth utilities | Live provider adapters and runtime-role rollout |
| AI-01 through AI-05 | Features, ensemble anomalies, forecasts, explanation rules and proportional simulations | API/UI consumption of stored analytical outputs |
| AI-06 | Real pipeline, structured evidence, baseline preparation, atomic PostgreSQL publication and exact replay | Production Worker dispatch and timeout/cancellation control wiring (WORK-04) |
| Worker | Claim/lifecycle/retry/timeout/polling and heartbeat | Executor still proposes simulated outcomes; it does not dispatch the real AI pipeline |
| Database | Versioned migrations, AI execution metadata, constraints/indexes and demo facts | Least-privilege runtime logins/RLS acceptance remains deferred under ADR 0001 |

AI-06 is merged through [PR #35](https://github.com/HusseinElhaddad/Sawakli-AI/pull/35).
Use the [documentation index](docs/README.md) and current source for implementation state.
The [TRK-06 register](docs/testing/TRK-06-integrated-baseline-register.md) is dated historical
evidence; its old open-PR and CI-gap descriptions are not the current baseline.

## Architecture and repository layout

Sawakli AI uses a **modular monolith**. The product has four runtime services: Next.js Web,
FastAPI API, Python Worker, and PostgreSQL. AI, Connector, and Data are internal Python modules,
not independently deployed services. API and Worker use the same backend Dockerfile with
different entry commands. Compose also provides a separate PostgreSQL service for tests.

```mermaid
flowchart TD
    Web["Next.js Web"] --> API["FastAPI API"]
    API --> DB["PostgreSQL: facts and jobs"]
    Worker["Python Worker"] --> DB
    Worker -. "Planned execution handoffs" .-> Modules["Internal AI, Connector, and Data modules"]
    Modules -->|"AI-06 publishes AI outputs; Data writes canonical facts"| DB
```

The diagram distinguishes the still-planned Worker dispatch from the implemented internal
modules. Web combines real API paths with explicitly mocked AI-output services. AI-06 can
publish outputs, but Worker dispatch does not yet call it.

| Path | Purpose |
|---|---|
| `apps/web/` | Active Next.js frontend; React, TypeScript, React Query, Vitest |
| `apps/backend/src/sawakli/api/` | FastAPI application and HTTP routes |
| `apps/backend/src/sawakli/worker/` | PostgreSQL job processing and scheduling |
| `apps/backend/src/sawakli/ai/` | Features, anomalies, forecasts, recommendations, simulation and pipeline persistence |
| `apps/backend/src/sawakli/connectors/` | CSV parsing, OAuth utilities, provider adapters |
| `apps/backend/src/sawakli/data/` | Staging, validation, normalization, and canonical-data writes |
| `apps/backend/src/sawakli/db/`, `apps/backend/src/sawakli/shared/` | Database access, models, shared enums/types and contract scaffolds |
| `apps/backend/alembic/` | Versioned PostgreSQL migrations |
| `apps/backend/tests/`, `apps/web/tests/` | Backend and frontend tests |
| `tests/contracts/`, `tests/e2e/` | Contract validators and E2E scaffolding |
| `docs/` | Maintained technical documentation and evidence |
| `.github/` | CI, documentation governance, contribution templates, and CODEOWNERS |
| `docker-compose.yml` | Active local stack and test database |

The obsolete root runtime trees were removed by DEV-02. Build and run from `apps/`;
there is no root Makefile or separate database HTTP service. The
[layout and cleanup inventory](docs/architecture/repository-layout.md) records retained
future-task/package markers and every removed path. PostgreSQL schema remains owned
by the active Alembic history, not the removed prototype SQL.

## Run with Docker Compose

### Requirements

- Git
- Docker Engine or Docker Desktop with Docker Compose v2 (`--wait` support)
- Available host ports: **3000** (Web), **8000** (API), **5433** (development DB from `.env.example`)

Run these commands from the repository root:

```bash
git clone https://github.com/HusseinElhaddad/Sawakli-AI.git
cd Sawakli-AI
cp .env.example .env
```

Review `.env`, replace the development password and JWT secret, then build, migrate, and start:

```bash
docker compose build
docker compose up -d --wait postgres
docker compose run --rm api alembic upgrade head
docker compose up -d --wait api worker web
docker compose ps
```

Migrations must run before the Worker begins querying the database. They include demo data;
they do not create a login user for the seeded organization.

| Endpoint | Use |
|---|---|
| [localhost:3000](http://localhost:3000) | Frontend; redirects through the UI login flow |
| [localhost:8000/health](http://localhost:8000/health) | API process health |
| [localhost:8000/docs](http://localhost:8000/docs) | FastAPI interactive API documentation |

Use the real registration/login flow for API-backed paths. The demo workspace is a
separate UI entry; do not confuse it with an authenticated seeded API user. For a
repeatable Nour demo API login, follow `apps/backend/tests/fixtures/seed.py` and supply
SAWAKLI_DEMO_PASSWORD locally. Container health is an infrastructure smoke check,
not proof of full CSV-to-AI-to-dashboard integration.

```bash
docker compose logs --tail=100 api worker web
docker compose down
```

### Configuration

Use [`.env.example`](.env.example) as the starting point; keep real `.env` files out of Git.

| Variable | Current behavior |
|---|---|
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Compose PostgreSQL settings; also used to construct API/Worker connection URLs |
| `POSTGRES_PORT` | Host port for the development DB; example is `5433`, container port is `5432` |
| `DATABASE_URL` | Host Python/Alembic connection; Compose overrides it with the internal `postgres:5432` address |
| `JWT_SECRET`, `JWT_EXPIRE_MINUTES` | API authentication settings; forwarded to API and Worker by Compose |
| `API_PORT`, `WEB_PORT` | Host ports, defaulting to `8000` and `3000`; `WEB_PORT` is a Compose option absent from the example file |
| `NEXT_PUBLIC_API_URL` | API base configuration; the Next.js proxy also reads API_INTERNAL_URL; some AI-output services remain mocked |
| `CONNECTOR_TOKEN_ENCRYPTION_KEY` | Required when using OAuth token utilities; example placeholder is deliberately invalid |
| `APP_ENV`, `APP_NAME`, `API_HOST`, `POSTGRES_HOST` | Listed in the example; the current Compose commands/configuration do not consume all of them |

Compose currently forwards neither `CONNECTOR_TOKEN_ENCRYPTION_KEY` nor a general `.env` file
into the backend container. OAuth integration needs explicit key injection. The Web Dockerfile
builds Next.js before Compose runtime variables are applied, so do not assume that a changed
`NEXT_PUBLIC_API_URL` is embedded in the browser bundle. These are configuration limitations to
resolve with the relevant integration work.

## Local development

Use **Python 3.12** (`>=3.12,<3.13` in the backend manifest) and **Node.js 24** (see `.nvmrc`).

### Backend

From the repository root, start the database, then install the backend:

```bash
docker compose up -d --wait postgres
cd apps/backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
alembic upgrade head
uvicorn sawakli.api.main:app --reload --host 0.0.0.0 --port 8000
```

On Windows, create the environment with `py -3.12 -m venv .venv` and activate it using
`.venv\Scripts\Activate.ps1`. Keep `DATABASE_URL` pointed at the host DB port in `.env`.
Run `python -m sawakli.worker` in a separate terminal with the same environment when needed.

For schema changes, create a new revision from `apps/backend` and review the generated migration:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

Do not rewrite historical applied migrations. For a running Docker stack, execute upgrades from
the repository root with `docker compose exec api alembic upgrade head`.

### Frontend

In another terminal, from the repository root:

```bash
cd apps/web
npm ci
npm run dev
```

## Testing and CI

Use the dedicated test database: backend fixtures migrate it and delete test rows. Do not point
the suite at a development database containing data you want to keep.

Start the test DB from the repository root:

```bash
docker compose up -d --wait postgres-test
```

In the activated backend environment, prepare two disposable databases on the test
server using the guarded harness (the example test password is synthetic):

```bash
export DATABASE_URL='postgresql+psycopg://postgres:change-me@localhost:5434/sawakli_regression_test'
export TEST_DATABASE_URL='postgresql+psycopg://postgres:change-me@localhost:5434/sawakli_integration_test'
python scripts/integration_harness.py fresh-db DATABASE_URL TEST_DATABASE_URL
cd apps/backend
ruff check .
ruff format --check .
mypy src
pytest -rs --junitxml=/tmp/sawakli-pytest-results.xml
```

Recreate the regression database before repeating the full suite: existing client
fixtures delete seeded organizations. The harness refuses non-disposable database
names and verifies the connected database. TEST_DATABASE_URL is needed for the full
PostgreSQL suite; CI rejects skipped tests. Never use development data for this setup.

Frontend checks, from `apps/web`:

```bash
npm ci
npm run lint
npm run type-check
npm run build
npm test
```

[GitHub Actions](.github/workflows/ci.yml) runs backend, frontend, and Compose integration jobs on
pushes to `main`/`develop` and on pull requests. PRs also run documentation governance unless
exempted by the repository workflow. The integration job migrates PostgreSQL and checks container
health plus API connectivity; it is not the complete product E2E acceptance test.

CI also runs `node scripts/run-contracts.mjs`, including deliberate negative cases,
prepares TEST_DATABASE_URL, rejects skipped backend tests and runs the full migration
round-trip. Locally, run the root contract command with the backend Python environment
on PATH. The round-trip harness requires ROUNDTRIP_DATABASE_URL on a **separate disposable
PostgreSQL server**: historical downgrade drops cluster-wide roles. See
[scripts/integration_harness.py](scripts/integration_harness.py) for its safeguards.
Backend dependencies retain bounded ranges without a lockfile; dependency policy and
security updates are outside this structural cleanup.

## Technical documentation

- [Repository layout and cleanup inventory](docs/architecture/repository-layout.md)
- [DEV-02 technical documentation](docs/architecture/DEV-02-repository-structure-cleanup.md)
- [Documentation index](docs/README.md)
- [Documentation standard](docs/DOCUMENTATION_STANDARD.md)
- [AI-01 data access and features](docs/ai/AI-01-feature-pipeline.md)
- [AI-03 forecasting](docs/ai/AI-03-forecasting.md)
- [AI-04 recommendations](docs/ai/AI-04-recommendation-engine.md)
- [API-04 analysis refresh and job status](docs/api/API-04-analysis-refresh-and-job-status.md)
- [TRK-06 integrated baseline and evidence](docs/testing/TRK-06-integrated-baseline-register.md)

Notion tracks ownership, scope, dependencies, dates, and final evidence links. Repository `/docs`
holds permanent technical documentation. Start from the
[revised execution plan](https://app.notion.com/p/3e47de83a91b812dbddfd803ef42dee7) for the current
core roadmap; older Month-One/August windows in historical task material are not current deadlines.
Canonical contracts and accepted ADRs take precedence over historical reports; this README is an
overview, not a replacement for those sources.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md), [AGENTS.md](AGENTS.md), and the
[documentation standard](docs/DOCUMENTATION_STANDARD.md), plus applicable nested `AGENTS.md` files.

- Create a focused `feat/`, `fix/`, `chore/`, or `docs/` branch from `main`.
- Submit changes through a pull request with actual verification evidence and human review.
- Update relevant task documentation and shared contracts in the same PR as behavioral changes.
- Preserve organization scope, module ownership, migration history, and secret handling.
- Record checks as `PASS`, `FAIL`, or `NOT RUN — <reason>`; do not equate generated code with verified work.

## Team

Graduation project at **Helwan University, Faculty of Engineering**.

| Current track | Team member |
|---|---|
| Project lead / AI | Hussein Mohamed Elhaddad |
| Frontend | Abdulrahman Ehab |
| Backend | Ahmed Ibrahim |
| Connector and Data | Youssef Halawa |
| Worker | El-Farouk Omar |
| System QA | Mohamed Hassan |
| Supervisor | Prof. Samar A. Said |

Track ownership follows the revised execution plan. Original implementation and PR authors remain
credited in Git history and task evidence.

## License

Proprietary — all rights reserved to the Sawakli AI Team. See [LICENSE](LICENSE) for the terms.
