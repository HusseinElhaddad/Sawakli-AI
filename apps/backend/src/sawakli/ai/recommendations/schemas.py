"""Typed input and output contracts for the AI-04 recommendation engine.

``AnomalySignal`` is AI-04's own typed view of the ``anomalies`` table (see
``alembic/versions/0004_ai_layer_tables.py`` and INT-01 Section 1.3). That table already exists
with a locked schema; AI-02 must write to that exact shape without a new approved migration (see
``apps/backend/AGENTS.md``, "Treat applied Alembic migrations as immutable history"). This
dataclass is therefore not a guess at a future contract — it is a narrow, typed subset of a
contract that already exists, scoped to only the fields the recommendation engine actually
consumes.

Forecasts are different: AI-03 is complete and merged (PR #14), so AI-04 imports its real,
public ``ForecastRecord`` / ``ModelUsed`` directly from ``sawakli.ai.forecasting`` — the same way
it imports AI-01's real ``FeatureRecord`` — rather than maintaining a parallel stand-in. A
previous revision of this module defined its own ``ForecastPoint`` stand-in before AI-03 existed;
that has been removed now that the real contract is available (see
``docs/ai/AI-04-recommendation-engine.md`` Section 3).

AI-02 is now merged, but its campaign-day diagnostic is not this per-metric shape.
ARCH-03's ``sawakli.ai.integration.to_anomaly_signal`` requires explicit MetricEvidence
and maps critical campaign diagnostics to this existing shape. AI-06 must extract real
metric evidence and wire the adapter; see docs/contracts/ai-pipeline-and-persistence.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal
from uuid import UUID

AnomalyDirection = Literal["above", "below"]
AnomalySeverity = Literal["low", "medium", "high"]
RiskRating = Literal["low", "medium", "high"]


class RecommendationDataError(ValueError):
    """Raised when recommendation inputs cannot safely be combined or scored."""


@dataclass(frozen=True, slots=True)
class AnomalySignal:
    """AI-04's typed view of one ``anomalies`` row (INT-01 Section 1.3).

    Only the columns the recommendation engine reads are represented here.
    ``detected_at`` and ``detectors_triggered`` exist on the real table but are not needed to
    generate a recommendation, so they are intentionally omitted from this narrow view.
    """

    organization_id: UUID
    campaign_id: UUID
    metric_name: str
    direction: AnomalyDirection
    severity: AnomalySeverity
    anomaly_score: Decimal
    id: UUID | None = None


@dataclass(frozen=True, slots=True)
class Recommendation:
    """One AI-04 output. Field names and types match the real ``recommendations`` table exactly.

    This is a pure in-memory result, mirroring how AI-01's ``FeatureRecord`` is never persisted by
    AI-01 itself. Writing rows to ``recommendations`` (including minting ``id``, ``model_run_id``,
    and the default ``status``) is Pipeline Orchestrator (AI-06) work, not AI-04's — see
    ``docs/ai/AI-04-recommendation-engine.md`` Section 2 for the scope boundary.

    ``rule_id`` is not a column on the real table. It is included here for traceability and
    testing; whoever persists this object should drop it or fold it into ``evidence``.

    No ``id`` field: none is minted until persistence (AI-06). Downstream consumers within the
    same ``generate_recommendations()`` call — most immediately AI-05, whose ``action_simulations``
    rows have a ``NOT NULL`` foreign key back to a recommendation — should correlate using the
    ``(campaign_id, rule_id)`` pair instead. That pair is guaranteed unique within a single call:
    each rule in ``rules.RULES`` runs at most once per campaign (it only ever evaluates that
    campaign's single latest-dated record), so no two ``Recommendation`` objects returned from one
    call can share both fields. See ``test_recommendation_campaign_and_rule_id_pairs_are_unique``.
    """

    organization_id: UUID
    campaign_id: UUID
    source_anomaly_id: UUID | None
    problem: str
    evidence: tuple[str, ...]
    suggested_action: str
    confidence_score: Decimal
    risk_rating: RiskRating
    severity: int
    rule_id: str
