"""AI-02 interpretable anomaly detection."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import cast
from uuid import UUID

import numpy as np
from numpy.typing import NDArray
from sklearn.ensemble import IsolationForest  # type: ignore[import-untyped]

from sawakli.ai.contracts import MetricEvidence, MetricName
from sawakli.ai.features import FeatureRecord

# Features produced by AI-01 that AI-02 will inspect.
DEFAULT_FEATURES = (
    "spend",
    "ctr",
    "cpc",
    "cpa",
    "roas",
    "spend_trend",
    "conversion_trend",
    "roas_trend",
    "rolling_ctr_7d",
    "rolling_ctr_14d",
    "rolling_cpc_7d",
    "rolling_cpc_14d",
)

# Avoid interpreting quantization and near-constant rolling values as unlimited
# statistical evidence. These are minimum dispersion scales, not alert cutoffs.
MIN_RELATIVE_DISPERSION = 0.05
MIN_TREND_DISPERSION = 0.05
MIN_NUMERIC_DISPERSION = 1e-12
STATISTICAL_EVIDENCE_FEATURES = 2


@dataclass(frozen=True, slots=True)
class AnomalyResult:
    """Final AI-02 anomaly result for one campaign-day."""

    organization_id: UUID
    campaign_id: UUID
    campaign_name: str
    date: date

    score: Decimal
    severity: str
    direction: str

    robust_z_score: Decimal
    iqr_score: Decimal
    isolation_score: Decimal

    reasons: tuple[str, ...]
    metric_evidence: tuple[MetricEvidence, ...] = ()


def detect_anomalies(
    records: Iterable[FeatureRecord],
    *,
    contamination: float = 0.05,
    random_state: int = 42,
) -> tuple[AnomalyResult, ...]:
    """Detect campaign anomalies using a Z-score/IQR/Isolation Forest ensemble.

    The input must already be AI-01 FeatureRecords.
    """

    records = tuple(records)

    if not records:
        return ()

    # Each tenant/campaign history has its own baselines and forest.
    grouped: dict[tuple[UUID, UUID], list[FeatureRecord]] = {}

    for record in records:
        key = (record.organization_id, record.campaign_id)
        grouped.setdefault(key, []).append(record)

    results: list[AnomalyResult] = []

    for campaign_records in grouped.values():
        results.extend(
            _detect_campaign_anomalies(
                sorted(campaign_records, key=lambda record: record.date),
                contamination=contamination,
                random_state=random_state,
            )
        )

    return tuple(
        sorted(
            results,
            key=lambda result: (
                result.organization_id.int,
                result.campaign_id.int,
                result.date,
            ),
        )
    )


def _detect_campaign_anomalies(
    records: list[FeatureRecord],
    *,
    contamination: float,
    random_state: int,
) -> list[AnomalyResult]:
    """Detect anomalies inside one campaign's history."""

    if not records:
        return []

    # We need enough history to establish a useful baseline.
    if len(records) < 5:
        return [_normal_result(record) for record in records]

    feature_values = _build_feature_matrix(records)

    # ---------------------------------------------------------
    # 1. Isolation Forest
    # ---------------------------------------------------------
    model = IsolationForest(
        contamination=contamination,
        random_state=random_state,
        n_estimators=200,
    )

    model.fit(feature_values)

    isolation_raw = -model.decision_function(feature_values)

    isolation_scores = _normalize_scores(isolation_raw)

    results: list[AnomalyResult] = []

    for index, record in enumerate(records):
        statistics = _feature_statistics(records, record)
        z_score, z_direction, z_reasons = _robust_z_score(
            records,
            record,
            statistics=statistics,
        )

        iqr_score, iqr_direction, iqr_reasons = _iqr_score(
            records,
            record,
            statistics=statistics,
        )

        isolation_score = Decimal(str(round(float(isolation_scores[index]), 6)))

        # -----------------------------------------------------
        # 2. Ensemble
        # -----------------------------------------------------
        final_score = (
            Decimal("0.40") * z_score
            + Decimal("0.20") * iqr_score
            + Decimal("0.40") * isolation_score
        )

        final_score = min(max(final_score, Decimal("0")), Decimal("1"))

        severity = _severity(final_score)

        direction = _overall_direction(
            record,
            records,
        )

        reasons = tuple(dict.fromkeys([*z_reasons, *iqr_reasons]))

        results.append(
            AnomalyResult(
                organization_id=record.organization_id,
                campaign_id=record.campaign_id,
                campaign_name=record.campaign_name,
                date=record.date,
                score=final_score,
                severity=severity,
                direction=direction,
                robust_z_score=z_score,
                iqr_score=iqr_score,
                isolation_score=isolation_score,
                reasons=reasons,
                metric_evidence=_metric_evidence(record, statistics),
            )
        )

    return results


def _build_feature_matrix(
    records: list[FeatureRecord],
) -> NDArray[np.float64]:
    """Build the Isolation Forest input matrix.

    Missing AI-01 features are replaced with that feature's campaign median
    only for the machine-learning matrix. Entirely unavailable columns are
    omitted; missing values are never treated as measured zero.
    """

    matrix: list[list[float]] = []

    medians: dict[str, float] = {}

    for feature_name in DEFAULT_FEATURES:
        values = [
            float(value)
            for record in records
            if (value := getattr(record, feature_name)) is not None
        ]

        if values:
            medians[feature_name] = float(np.median(values))

    for record in records:
        row: list[float] = []

        for feature_name in medians:
            value = getattr(record, feature_name)

            if value is None:
                row.append(medians[feature_name])
            else:
                row.append(float(value))

        matrix.append(row)

    return np.asarray(matrix, dtype=float)


@dataclass(frozen=True, slots=True)
class _FeatureStatistic:
    name: str
    median: float
    current: float
    count: int
    z: Decimal
    iqr: Decimal


def _feature_statistics(
    records: list[FeatureRecord], record: FeatureRecord
) -> tuple[_FeatureStatistic, ...]:
    """Single calculation used by both detector branches and structured evidence."""
    history = [item for item in records if item.date < record.date]
    if len(history) < 5:
        return ()
    result: list[_FeatureStatistic] = []
    for name in DEFAULT_FEATURES:
        current = getattr(record, name)
        if current is None:
            continue
        values = [float(value) for item in history if (value := getattr(item, name)) is not None]
        if len(values) < 5:
            continue
        median = float(np.median(values))
        mad = float(np.median([abs(value - median) for value in values]))
        current_value = float(current)
        scale = max(1.4826 * mad, _minimum_dispersion(name, median))
        robust_z = abs(current_value - median) / scale
        z = Decimal(str(round(min(robust_z / 6.0, 1.0), 6)))
        q1, q3 = np.percentile(sorted(values), [25, 75])
        width = max(float(q3 - q1), _minimum_dispersion(name, median))
        lower, upper = q1 - 1.5 * width, q3 + 1.5 * width
        distance = (
            (lower - current_value) / width
            if current_value < lower
            else ((current_value - upper) / width if current_value > upper else 0.0)
        )
        iqr = Decimal(str(round(min(distance / 3.0, 1.0), 6)))
        result.append(_FeatureStatistic(name, median, current_value, len(values), z, iqr))
    return tuple(result)


def _metric_evidence(
    record: FeatureRecord, statistics: tuple[_FeatureStatistic, ...]
) -> tuple[MetricEvidence, ...]:
    return tuple(
        MetricEvidence(
            organization_id=record.organization_id,
            campaign_id=record.campaign_id,
            observed_on=record.date,
            metric_name=cast(MetricName, item.name),
            current_value=getattr(record, item.name),
            baseline_median=Decimal(str(item.median)),
            historical_count=item.count,
            z_contribution=item.z,
            iqr_contribution=item.iqr,
        )
        for item in statistics
        if item.name in {"spend", "ctr", "cpc", "cpa", "roas"} and (item.z > 0 or item.iqr > 0)
    )


def _robust_z_score(
    records: list[FeatureRecord],
    record: FeatureRecord,
    *,
    statistics: tuple[_FeatureStatistic, ...] | None = None,
) -> tuple[Decimal, str, list[str]]:
    stats = _feature_statistics(records, record) if statistics is None else statistics
    strongest = max(stats, key=lambda item: item.z, default=None)
    if strongest is None or strongest.z == 0:
        return (
            Decimal("0")
            if sum(item.date < record.date for item in records) < 5
            else _corroborated_score([]),
            "normal",
            [],
        )
    direction = "up" if strongest.current > strongest.median else "down"
    return (
        _corroborated_score([item.z for item in stats]),
        direction,
        [f"{strongest.name} is unusually {direction}"],
    )


def _iqr_score(
    records: list[FeatureRecord],
    record: FeatureRecord,
    *,
    statistics: tuple[_FeatureStatistic, ...] | None = None,
) -> tuple[Decimal, str, list[str]]:
    stats = _feature_statistics(records, record) if statistics is None else statistics
    strongest = max(stats, key=lambda item: item.iqr, default=None)
    if strongest is None or strongest.iqr == 0:
        return (
            Decimal("0")
            if sum(item.date < record.date for item in records) < 5
            else _corroborated_score([]),
            "normal",
            [],
        )
    direction = "up" if strongest.current > strongest.median else "down"
    return (
        _corroborated_score([item.iqr for item in stats]),
        direction,
        [f"{strongest.name} is outside the normal IQR range"],
    )


def _corroborated_score(contributions: list[Decimal]) -> Decimal:
    """Average the two strongest feature contributions, padding absent evidence with zero.

    One unstable feature cannot independently saturate both statistical branches.
    Features are corroborating measurements, not statistically independent votes.
    """
    strongest = sorted(contributions, reverse=True)[:STATISTICAL_EVIDENCE_FEATURES]
    return (sum(strongest, Decimal(0)) / STATISTICAL_EVIDENCE_FEATURES).quantize(
        Decimal("0.000001")
    )


def _minimum_dispersion(feature_name: str, median_value: float) -> float:
    """Five percent of a level, or five percentage points for relative trends."""
    if feature_name.endswith("_trend"):
        return MIN_TREND_DISPERSION
    return max(abs(median_value) * MIN_RELATIVE_DISPERSION, MIN_NUMERIC_DISPERSION)


def _normalize_scores(scores: NDArray[np.float64]) -> NDArray[np.float64]:
    """Normalize Isolation Forest anomaly scores into [0, 1]."""

    minimum = float(scores.min())
    maximum = float(scores.max())

    if maximum == minimum:
        return np.zeros_like(scores)

    return (scores - minimum) / (maximum - minimum)


def _severity(score: Decimal) -> str:
    """Convert the ensemble score into a human-readable severity."""

    if score >= Decimal("0.80"):
        return "critical"

    if score >= Decimal("0.60"):
        return "high"

    if score >= Decimal("0.40"):
        return "medium"

    if score >= Decimal("0.20"):
        return "low"

    return "normal"


def _combine_direction(
    z_direction: str,
    iqr_direction: str,
) -> str:
    """Combine directional evidence from the interpretable detectors."""

    if z_direction == "normal" and iqr_direction == "normal":
        return "normal"

    if z_direction == iqr_direction:
        return z_direction

    if z_direction == "normal":
        return iqr_direction

    if iqr_direction == "normal":
        return z_direction

    return "mixed"


def _normal_result(record: FeatureRecord) -> AnomalyResult:
    """Return a safe result when there is insufficient campaign history."""

    return AnomalyResult(
        organization_id=record.organization_id,
        campaign_id=record.campaign_id,
        campaign_name=record.campaign_name,
        date=record.date,
        score=Decimal("0"),
        severity="normal",
        direction="normal",
        robust_z_score=Decimal("0"),
        iqr_score=Decimal("0"),
        isolation_score=Decimal("0"),
        reasons=("insufficient campaign history",),
    )


def _overall_direction(
    record: FeatureRecord,
    records: list[FeatureRecord],
) -> str:
    """Determine overall campaign direction from abnormal feature movements."""

    history = [item for item in records if item.date < record.date]

    if len(history) < 5:
        return "normal"

    up_score = 0.0
    down_score = 0.0

    # Higher value = better business performance.
    positive_features = {
        "ctr",
        "conversions",
        "roas",
        "conversion_trend",
        "roas_trend",
    }

    # Higher value = worse business performance.
    negative_features = {
        "cpc",
        "cpa",
        "spend_trend",
    }

    for feature_name in DEFAULT_FEATURES:
        current = getattr(record, feature_name)

        if current is None:
            continue

        values = [
            float(value) for item in history if (value := getattr(item, feature_name)) is not None
        ]

        if len(values) < 5:
            continue

        baseline = float(np.median(values))
        current_value = float(current)

        if current_value == baseline:
            continue

        movement = abs(current_value - baseline)

        if feature_name in positive_features:
            if current_value > baseline:
                up_score += movement
            else:
                down_score += movement

        elif feature_name in negative_features:
            if current_value < baseline:
                up_score += movement
            else:
                down_score += movement

    if up_score == 0 and down_score == 0:
        return "normal"

    if up_score > down_score:
        return "up"

    if down_score > up_score:
        return "down"

    return "mixed"
