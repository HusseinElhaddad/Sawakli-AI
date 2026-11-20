import type { CampaignPerformance, PerformanceFlag } from './types'

export type SortKey =
  | 'performance' | 'name' | 'platform' | 'status'
  | 'spend' | 'clicks' | 'conversions' | 'ctr' | 'cpc' | 'cpa' | 'roas'

export type SortState = { key: SortKey; direction: 'asc' | 'desc' }

/** Default: weak campaigns first, then average, strong and no data; ties by spend, highest first. */
export const DEFAULT_SORT: SortState = { key: 'performance', direction: 'asc' }

const FLAG_ORDER: Record<PerformanceFlag, number> = { weak: 0, average: 1, strong: 2, no_data: 3 }

const TEXT_KEYS: ReadonlySet<SortKey> = new Set(['performance', 'name', 'platform', 'status'])

/** Direction used when a column is first selected: text columns ascending, numbers descending. */
export function initialDirection(key: SortKey): SortState['direction'] {
  return TEXT_KEYS.has(key) ? 'asc' : 'desc'
}

function value(row: CampaignPerformance, key: SortKey): string | number | null {
  switch (key) {
    case 'performance': return FLAG_ORDER[row.flag]
    case 'name': return row.campaign.name.toLowerCase()
    case 'platform': return row.campaign.platform
    case 'status': return row.campaign.status ?? 'unknown'
    default: return row.totals[key]
  }
}

function compareValues(a: string | number, b: string | number): number {
  if (typeof a === 'number' && typeof b === 'number') return a - b
  return String(a).localeCompare(String(b))
}

/** Sorts a copy; null values (ratios with a zero denominator) always go last. */
export function sortPerformance(rows: readonly CampaignPerformance[], sort: SortState): CampaignPerformance[] {
  const sign = sort.direction === 'asc' ? 1 : -1
  return [...rows].sort((left, right) => {
    const a = value(left, sort.key)
    const b = value(right, sort.key)
    if (a === null && b !== null) return 1
    if (b === null && a !== null) return -1
    const primary = a === null || b === null ? 0 : sign * compareValues(a, b)
    if (primary !== 0) return primary
    if (left.totals.spend !== right.totals.spend) return right.totals.spend - left.totals.spend
    return left.campaign.name.localeCompare(right.campaign.name)
  })
}
