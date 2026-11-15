# Repository layout and DEV-02 decision inventory

Audit base: 8c7dd678c808f0760285c39eed364887faed960c, 15 November 2026.

## Active entry points

| Path | Purpose / consumer |
|---|---|
| apps/backend/src/sawakli/api/main.py | uvicorn sawakli.api.main:app; real REST routes |
| apps/backend/src/sawakli/worker/__main__.py | python -m sawakli.worker; polling and heartbeat |
| apps/backend/src/sawakli/ai/pipeline.py | AI-owned execution and persistence; WORK-04 dispatch still pending |
| apps/backend/src/sawakli/data/ | Canonical ingestion; no separate Data HTTP service |
| apps/backend/src/sawakli/connectors/ | Provider parsing, token utilities and adapters, in process |
| apps/backend/alembic/ | Immutable applied schema history and successor migrations |
| apps/backend/src/sawakli/db/tables.py | Query-only metadata, separate from migration metadata |
| apps/web/src/app/ | Next.js routes and API proxy; npm scripts build/start apps/web |
| scripts/ | Contract runner, integration harness and real AI evidence procedures |
| tests/contracts/ | Active canonical definitions, validators and injected negative cases |
| .github/workflows/ci.yml | Backend/frontend/contracts/Compose and PR documentation gates |

## Removal evidence and ownership

The six root runtimes (52 files) are prototypes: health-only FastAPI applications,
a default Next.js starter and a prototype lowercase/payload jobs schema. None is a
Compose build context, CI entry point, active import, npm alias or script target.
The prototype DB SQL is not Alembic migration history and contradicts the active schema;
its removal preserves the canonical migrations. No unique product implementation was found.
Backend duplicate files are empty and have no import/route/CLI consumers; real deps.py
and worker/__main__.py remain. Empty Makefile and infrastructure markers implement no
commands. Redundant .gitkeep files share directories with tracked actual content.
Two removed tests contain only assert True; all substantive suites remain. Expected
collection delta is exactly minus two (487 to 485), not a relaxed gate.

Hussein implements DEV-02 by explicit task assignment. API/frontend/Worker/QA owners
remain affected reviewers; no review is claimed. ADR 0001 FU-11's historical proposed
owner remains unchanged. Every deletion is reversible with git restore --source=<base>
for the selected path; restore commits rather than force-rewriting shared history.
Historical references in ADRs/reports are retained as historical evidence. Governance's
legacy path patterns remain deliberately conservative; no gate is weakened.

## Retained intentional markers

| Paths | Decision and rationale |
|---|---|
| Python __init__.py throughout active packages/tests | Keep package discovery/import boundaries; empty does not mean obsolete |
| apps/backend/src/sawakli/py.typed | Keep PEP 561 type-distribution marker |
| ai/evaluation, db/repositories, shared/contracts | Keep named future/internal extension packages; no downstream feature implemented here |
| tests/e2e/.gitkeep | Keep explicit future E2E home; contract tests elsewhere are active |
| apps/web/src/features/*/.gitkeep | Keep reserved feature homes; real dashboard code remains |
| apps/web/src/components/ui/.gitkeep | Keep intentionally reserved UI component home |
| apps/web/public/.gitkeep and docs/database/.gitkeep, docs/demo/.gitkeep | Keep empty intended content homes |

No active code/package moves were necessary. Dependency manifests/active lockfile,
Docker/CI runtime paths, migrations, shared contracts and analytical algorithms remain
unchanged. No external unsubmitted branch consumer is proven absent by this audit;
recheck collaboration state at review time.

## Exact removed-path manifest

- `Makefile`
- `agent/.dockerignore`
- `agent/.gitkeep`
- `agent/Dockerfile`
- `agent/app/__init__.py`
- `agent/app/main.py`
- `agent/requirements.txt`
- `api/.dockerignore`
- `api/.gitkeep`
- `api/Dockerfile`
- `api/app/__init__.py`
- `api/app/main.py`
- `api/requirements.txt`
- `apps/backend/alembic/versions/.gitkeep`
- `apps/backend/src/sawakli/api/dependencies.py`
- `apps/backend/src/sawakli/api/v1/__init__.py`
- `apps/backend/src/sawakli/worker/main.py`
- `apps/backend/tests/integration/test_placeholder.py`
- `apps/backend/tests/unit/test_placeholder.py`
- `apps/web/src/hooks/.gitkeep`
- `apps/web/src/lib/.gitkeep`
- `apps/web/src/services/.gitkeep`
- `apps/web/src/types/.gitkeep`
- `apps/web/tests/.gitkeep`
- `connector/.dockerignore`
- `connector/.gitkeep`
- `connector/Dockerfile`
- `connector/app/__init__.py`
- `connector/app/main.py`
- `connector/requirements.txt`
- `database/app/.dockerignore`
- `database/app/Dockerfile`
- `database/app/requirements.txt`
- `database/app/src/__init__.py`
- `database/app/src/db.py`
- `database/app/src/main.py`
- `database/db/.dockerignore`
- `database/db/Dockerfile`
- `database/db/init/001_initial_schema.sql`
- `docs/adr/.gitkeep`
- `docs/api/.gitkeep`
- `docs/architecture/.gitkeep`
- `infrastructure/docker/.gitkeep`
- `infrastructure/scripts/.gitkeep`
- `ui/.dockerignore`
- `ui/.gitignore`
- `ui/Dockerfile`
- `ui/README.md`
- `ui/eslint.config.mjs`
- `ui/next.config.ts`
- `ui/package-lock.json`
- `ui/package.json`
- `ui/postcss.config.mjs`
- `ui/public/file.svg`
- `ui/public/globe.svg`
- `ui/public/next.svg`
- `ui/public/vercel.svg`
- `ui/public/window.svg`
- `ui/src/app/favicon.ico`
- `ui/src/app/globals.css`
- `ui/src/app/layout.tsx`
- `ui/src/app/page.tsx`
- `ui/tsconfig.json`
- `worker/.dockerignore`
- `worker/.gitkeep`
- `worker/Dockerfile`
- `worker/app/__init__.py`
- `worker/app/main.py`
- `worker/requirements.txt`
