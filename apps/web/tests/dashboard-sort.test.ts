import { describe, expect, it } from 'vitest'
import { summarize } from '@/features/dashboard/aggregate'
import { DEFAULT_SORT, sortPerformance } from '@/features/dashboard/sort'
import type { CampaignPerformance, PerformanceFlag } from '@/features/dashboard/types'
import { campaign, metric } from './helpers/dashboard-fixtures'

function perf(id: string, flag: PerformanceFlag, spend: number, conversions: number): CampaignPerformance {
  return {
    campaign: campaign(id, `Campaign ${id}`, 'meta', 'active'),
    totals: summarize(spend > 0 ? [metric('2026-08-20', spend, spend, 10, 100, conversions)] : []),
    flag,
    reason: null,
  }
}

describe('campaign table sorting', () => {
  const rows = [
    perf('strong', 'strong', 900, 10),
    perf('none', 'no_data', 0, 0),
    perf('weak-small', 'weak', 100, 0),
    perf('average', 'average', 500, 5),
    perf('weak-big', 'weak', 800, 2),
  ]

  it('puts weak first, then average, strong and no data, with higher spend first inside a group', () => {
    expect(sortPerformance(rows, DEFAULT_SORT).map((r) => r.campaign.id))
      .toEqual(['weak-big', 'weak-small', 'average', 'strong', 'none'])
  })

  it('sorts a numeric column and keeps null ratios last in both directions', () => {
    // CPA: weak-big 400, average 100, strong 90; weak-small and none have no conversions (null).
    expect(sortPerformance(rows, { key: 'cpa', direction: 'desc' }).map((r) => r.campaign.id))
      .toEqual(['weak-big', 'average', 'strong', 'weak-small', 'none'])
    expect(sortPerformance(rows, { key: 'cpa', direction: 'asc' }).map((r) => r.campaign.id))
      .toEqual(['strong', 'average', 'weak-big', 'weak-small', 'none'])
  })

  it('does not mutate the input', () => {
    const copy = [...rows]
    sortPerformance(rows, { key: 'spend', direction: 'asc' })
    expect(rows).toEqual(copy)
  })
})
