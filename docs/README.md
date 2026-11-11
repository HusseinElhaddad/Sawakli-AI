# Sawakli AI Technical Documentation

This directory is the permanent technical source of truth for Sawakli AI. Start with the
[`Documentation Standard`](DOCUMENTATION_STANDARD.md) before implementing or reviewing a task.

## Documentation Model

- **Notion** tracks scope, ownership, deadlines, dependencies, progress, and final evidence links.
- **GitHub `/docs`** explains architecture, contracts, technical behavior, decisions, and testing.
- **Source code** contains the implementation and only the comments needed to clarify non-obvious
  behavior.

Important technical information must be maintained here, not only in Notion or attached files.

## Start Here

- [Documentation standard](DOCUMENTATION_STANDARD.md)
- [Technical task template](templates/TASK_DOCUMENTATION_TEMPLATE.md)
- [AI-01 feature pipeline](ai/AI-01-feature-pipeline.md)
- [AI-02 anomaly detection](ai/AI-02-anomaly-detection.md)
- [AI-02 seeded reference benchmark](testing/AI-02-seeded-benchmark.md)
- [AI-05 action simulator](ai/AI-05-action-simulator.md)
- [AI-05 execution plan](ai/plans/action-simulator-execution.md)
- [AI-05 implementation and learning guide](ai/guides/action-simulator-walkthrough.md)
- [Action simulation calculation contract](contracts/action-simulation.md)
- [ARCH-03 AI integration decision and evidence](architecture/ARCH-03-ai-pipeline-and-persistence-interfaces.md)
- [AI pipeline and persistence contract v1](contracts/ai-pipeline-and-persistence.md)
- [ADR 0002 - AI pipeline and persistence boundaries (prepared for review)](adr/0002-ai-pipeline-and-persistence-boundaries.md)
- [ADR 0001 — Runtime boundaries and database roles](adr/0001-runtime-boundaries-and-database-roles.md)
- [ARCH-01 runtime boundaries and database roles](architecture/ARCH-01-runtime-boundaries-and-database-roles.md)
- [QA-00 contract validators and integration harness](testing/QA-00-contract-validators-and-integration-harness.md)
- [CONN-01 connector package and CSV/demo parser](connectors/CONN-01-csv-demo-parser.md)
- [CONN-02 OAuth token security and connection health](connectors/CONN-02-oauth-token-security.md)
- [Release and demo checklist](testing/release-checklist.md)

## Categories

| Directory | Purpose |
|---|---|
| `architecture/` | System boundaries, major flows, and cross-cutting design |
| `contracts/` | Canonical definitions shared across layers |
| `adr/` | Accepted, superseded, and rejected architecture decisions |
| `ai/` | AI task and layer documentation |
| `api/` | API task and layer documentation |
| `data/` | Ingestion, normalization, persistence, and data task documentation |
| `connectors/` | External provider and connector task documentation |
| `worker/` | Background job and Worker task documentation |
| `ui/` | User interface task and layer documentation |
| `testing/` | Cross-cutting testing strategy and acceptance guidance |
| `demo/` | Maintained demonstration procedures |
| `templates/` | Approved documentation templates |

Directories are created when maintained content exists. Some categories may therefore be absent.
Existing historical directories remain valid until their content is deliberately reconciled with
the standard.
