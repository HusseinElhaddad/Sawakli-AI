import type { Campaign, DailyMetric } from '@/types'
import type {
  CampaignPerformance,
  DatePreset,
  DateRange,
  KpiSummary,
  MetricFacts,
  PerformanceFlag,
  PlatformFilter,
  StatusFilter,
} from './types'

/**
 * Pure aggregation for the UI-04 dashboard. API-02 returns daily rows per campaign; there is no
 * KPI endpoint, so totals are built here. Raw facts are summed first and every ratio is computed
 * from the sums (PROD-01 §2, API-02 doc §15); daily ratios are never averaged.
 */

/**
 * UI-04 performance flag thresholds (frontend display rule, not the AI-computed health_status).
 * Weak: ROAS below 1.0 (revenue does not cover spend), CPA above 1.25 times the organization CPA,
 * or spend with no conversions. KPI formulas follow PROD-01 §2.1.
 */
export const PERFORMANCE_RULE = { weakRoasBelow: 1.0, weakCpaRatio: 1.25 } as const

/** Days fetched from API-02 (inclusive of today) so presets can be anchored to the latest data. */
const FETCH_WINDOW_DAYS = 365

/**
 * Money arrives as binary floats, so sums can land a hair above an exact decimal threshold
 * (0.1 + 0.2 > 0.3). Threshold comparisons allow this relative tolerance.
 */
const TOLERANCE = 1e-9

const PRESET_DAYS: Record<Exclude<DatePreset, 'all'>, number> = { '7d': 7, '30d': 30, '90d': 90 }

const MS_PER_DAY = 86_400_000

function toUtcMs(date: string): number {
  const [year, month, day] = date.split('-').map(Number)
  return Date.UTC(year, month - 1, day)
}

function fromUtcMs(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10)
}

export function addDays(date: string, days: number): string {
  return fromUtcMs(toUtcMs(date) + days * MS_PER_DAY)
}

/** Number of calendar days in an inclusive range. */
export function daysInRange(range: DateRange): number {
  return Math.round((toUtcMs(range.to) - toUtcMs(range.from)) / MS_PER_DAY) + 1
}

/** Today's date in the browser's own calendar (toISOString would give the UTC date). */
export function localToday(now: Date = new Date()): string {
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

export function fetchWindow(today: string): DateRange {
  return { from: addDays(today, -(FETCH_WINDOW_DAYS - 1)), to: today }
}

export function sumFacts(rows: readonly DailyMetric[]): MetricFacts {
  const facts: MetricFacts = { spend: 0, revenue: 0, clicks: 0, impressions: 0, conversions: 0 }
  for (const row of rows) {
    facts.spend += row.spend
    facts.revenue += row.revenue
    facts.clicks += row.clicks
    facts.impressions += row.impressions
    facts.conversions += row.conversions
  }
  return facts
}

function safeDivide(numerator: number, denominator: number): number | null {
  return denominator === 0 ? null : numerator / denominator
}

export function deriveRatios(facts: MetricFacts): Pick<KpiSummary, 'ctr' | 'cpc' | 'cpa' | 'roas'> {
  return {
    ctr: safeDivide(facts.clicks, facts.impressions),
    cpc: safeDivide(facts.spend, facts.clicks),
    cpa: safeDivide(facts.spend, facts.conversions),
    roas: safeDivide(facts.revenue, facts.spend),
  }
}

function toSummary(facts: MetricFacts, days: number): KpiSummary {
  return { ...facts, ...deriveRatios(facts), days }
}

export function summarize(rows: readonly DailyMetric[]): KpiSummary {
  return toSummary(sumFacts(rows), rows.length)
}

export function combineSummaries(summaries: readonly KpiSummary[]): KpiSummary {
  const facts: MetricFacts = { spend: 0, revenue: 0, clicks: 0, impressions: 0, conversions: 0 }
  let days = 0
  for (const s of summaries) {
    facts.spend += s.spend
    facts.revenue += s.revenue
    facts.clicks += s.clicks
    facts.impressions += s.impressions
    facts.conversions += s.conversions
    days += s.days
  }
  return toSummary(facts, days)
}

/** Rows whose date is inside the inclusive range (ISO dates compare correctly as strings). */
export function rowsInRange(rows: readonly DailyMetric[], range: DateRange): DailyMetric[] {
  return rows.filter((row) => row.date >= range.from && row.date <= range.to)
}

export function earliestDataDate(metrics: Readonly<Record<string, readonly DailyMetric[]>>): string | null {
  let earliest: string | null = null
  for (const rows of Object.values(metrics)) {
    for (const row of rows) {
      if (earliest === null || row.date < earliest) earliest = row.date
    }
  }
  return earliest
}

export function latestDataDate(metrics: Readonly<Record<string, readonly DailyMetric[]>>): string | null {
  let latest: string | null = null
  for (const rows of Object.values(metrics)) {
    for (const row of rows) {
      if (latest === null || row.date > latest) latest = row.date
    }
  }
  return latest
}

/**
 * Presets end on the latest date that has data; "all" covers the whole fetched window. A range never
 * starts before the fetched window, because days outside it were never requested.
 */
export function resolvePreset(preset: DatePreset, latest: string, window: DateRange): DateRange {
  if (preset === 'all') return { from: window.from, to: latest }
  const from = addDays(latest, -(PRESET_DAYS[preset] - 1))
  return { from: from < window.from ? window.from : from, to: latest }
}

/** The equal-length period that ends the day before `range` starts. */
export function previousPeriod(range: DateRange): DateRange {
  const length = daysInRange(range)
  return { from: addDays(range.from, -length), to: addDays(range.from, -1) }
}

/**
 * The previous period, only when it is fully covered: it starts inside the fetched window and on or
 * after the first date with data. Otherwise a delta would compare against a partly empty period.
 */
export function coveredPreviousPeriod(range: DateRange, window: DateRange, earliest: string | null): DateRange | null {
  if (earliest === null) return null
  const previous = previousPeriod(range)
  return previous.from >= window.from && previous.from >= earliest ? previous : null
}

export function classifyPerformance(
  totals: KpiSummary,
  baseline: KpiSummary,
): { flag: PerformanceFlag; reason: string | null } {
  if (totals.spend <= 0) return { flag: 'no_data', reason: null }

  if (totals.roas !== null && totals.roas < PERFORMANCE_RULE.weakRoasBelow * (1 - TOLERANCE)) {
    return { flag: 'weak', reason: 'ROAS below 1.0× — revenue does not cover spend' }
  }
  if (totals.conversions === 0) {
    return { flag: 'weak', reason: 'Spend with no conversions' }
  }
  if (
    totals.cpa !== null &&
    baseline.cpa !== null &&
    totals.cpa > PERFORMANCE_RULE.weakCpaRatio * baseline.cpa * (1 + TOLERANCE)
  ) {
    return { flag: 'weak', reason: 'CPA more than 25% above the organization CPA' }
  }

  const strong =
    totals.roas !== null &&
    totals.cpa !== null &&
    baseline.roas !== null &&
    baseline.cpa !== null &&
    totals.roas >= baseline.roas * (1 - TOLERANCE) &&
    totals.cpa <= baseline.cpa * (1 + TOLERANCE)
  return { flag: strong ? 'strong' : 'average', reason: null }
}

/**
 * Totals and flags for every campaign in `range`. The baseline is the whole organization (all
 * platforms and statuses, campaigns with no spend excluded), so filters never change a flag.
 */
export function buildPerformance(
  campaigns: readonly Campaign[],
  metrics: Readonly<Record<string, readonly DailyMetric[]>>,
  range: DateRange,
): CampaignPerformance[] {
  const totals = campaigns.map((campaign) => summarize(rowsInRange(metrics[campaign.id] ?? [], range)))
  const baseline = combineSummaries(totals.filter((t) => t.spend > 0))
  return campaigns.map((campaign, i) => ({
    campaign,
    totals: totals[i],
    ...classifyPerformance(totals[i], baseline),
  }))
}

export function filterPerformance(
  rows: readonly CampaignPerformance[],
  platform: PlatformFilter,
  status: StatusFilter,
): CampaignPerformance[] {
  return rows.filter(({ campaign }) =>
    (platform === 'all' || campaign.platform === platform) &&
    (status === 'all' || (campaign.status ?? 'unknown') === status),
  )
}

export function percentChange(current: number | null, previous: number | null): number | null {
  if (current === null || previous === null || previous === 0) return null
  return (current - previous) / previous
}
