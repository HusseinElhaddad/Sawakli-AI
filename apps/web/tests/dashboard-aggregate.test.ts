import { describe, expect, it } from 'vitest'
import {
  PERFORMANCE_RULE,
  addDays,
  buildPerformance,
  classifyPerformance,
  combineSummaries,
  daysInRange,
  fetchWindow,
  filterPerformance,
  latestDataDate,
  localToday,
  percentChange,
  previousPeriod,
  resolvePreset,
  rowsInRange,
  summarize,
} from '@/features/dashboard/aggregate'
import type { Campaign, DailyMetric } from '@/types'

type Facts = Partial<Pick<DailyMetric, 'spend' | 'revenue' | 'clicks' | 'impressions' | 'conversions'>>

const ratio = (a: number, b: number) => (b === 0 ? null : a / b)

/** A daily row as API-02 returns it, with that day's own ratios filled in. */
function row(date: string, facts: Facts = {}): DailyMetric {
  const spend = facts.spend ?? 0
  const revenue = facts.revenue ?? 0
  const clicks = facts.clicks ?? 0
  const impressions = facts.impressions ?? 0
  const conversions = facts.conversions ?? 0
  return {
    date, spend, revenue, clicks, impressions, conversions,
    ctr: ratio(clicks, impressions), cpc: ratio(spend, clicks), cpa: ratio(spend, conversions), roas: ratio(revenue, spend),
  }
}

function campaign(id: string, platform: Campaign['platform'], status: Campaign['status'] = 'active'): Campaign {
  return { id, name: `Campaign ${id}`, platform, status, objective: null, budget: null, start_date: null, end_date: null }
}

const WINDOW = { from: '2025-10-21', to: '2026-10-21' }

describe('date helpers (YYYY-MM-DD, no timezone shifts)', () => {
  it('adds days across month, leap-year and year boundaries', () => {
    expect(addDays('2026-08-20', -29)).toBe('2026-07-22')
    expect(addDays('2026-03-01', -1)).toBe('2026-02-28')
    expect(addDays('2024-03-01', -1)).toBe('2024-02-29')
    expect(addDays('2026-12-31', 1)).toBe('2027-01-01')
  })

  it('counts an inclusive range', () => {
    expect(daysInRange({ from: '2026-07-22', to: '2026-08-20' })).toBe(30)
    expect(daysInRange({ from: '2026-08-20', to: '2026-08-20' })).toBe(1)
  })

  it('takes today from the local calendar date, not from UTC', () => {
    expect(localToday(new Date(2026, 9, 22, 0, 30))).toBe('2026-10-22')
    expect(localToday(new Date(2026, 9, 21, 23, 59))).toBe('2026-10-21')
  })

  it('fetches the last 365 days, today included', () => {
    expect(fetchWindow('2026-10-21')).toEqual({ from: '2025-10-22', to: '2026-10-21' })
  })
})

describe('summarize: sum the raw facts first, then divide', () => {
  it('computes CTR from summed clicks and impressions, not by averaging daily CTRs', () => {
    // Daily CTRs are 10% and 1% (average 5.5%); the true CTR is 19 / 1000 = 1.9%.
    const s = summarize([
      row('2026-08-01', { impressions: 100, clicks: 10 }),
      row('2026-08-02', { impressions: 900, clicks: 9 }),
    ])
    expect(s.ctr).toBeCloseTo(0.019, 12)
    expect(s.ctr).not.toBeCloseTo(0.055, 3)
  })

  it('computes CPA, CPC and ROAS from the sums', () => {
    // Daily CPAs are 10 and 45 (average 27.5); the true CPA is 100 / 3 = 33.33.
    const s = summarize([
      row('2026-08-01', { spend: 10, conversions: 1, clicks: 4, revenue: 30 }),
      row('2026-08-02', { spend: 90, conversions: 2, clicks: 16, revenue: 70 }),
    ])
    expect(s.spend).toBe(100)
    expect(s.conversions).toBe(3)
    expect(s.cpa).toBeCloseTo(100 / 3, 12)
    expect(s.cpc).toBeCloseTo(5, 12)
    expect(s.roas).toBeCloseTo(1, 12)
    expect(s.days).toBe(2)
  })

  it('returns null ratios for zero denominators, never 0 or Infinity', () => {
    const s = summarize([row('2026-08-01', { revenue: 0 })])
    expect(s).toMatchObject({ ctr: null, cpc: null, cpa: null, roas: null })
  })

  it('summarizes no rows as zero facts with null ratios', () => {
    expect(summarize([])).toEqual({
      spend: 0, revenue: 0, clicks: 0, impressions: 0, conversions: 0,
      ctr: null, cpc: null, cpa: null, roas: null, days: 0,
    })
  })

  it('combines campaign summaries by summing facts, matching a summary of all rows', () => {
    const a = [row('2026-08-01', { spend: 10, conversions: 1, impressions: 100, clicks: 10, revenue: 5 })]
    const b = [row('2026-08-01', { spend: 90, conversions: 2, impressions: 900, clicks: 9, revenue: 300 })]
    expect(combineSummaries([summarize(a), summarize(b)])).toEqual(summarize([...a, ...b]))
    expect(combineSummaries([])).toEqual(summarize([]))
  })
})

describe('date ranges', () => {
  it('keeps rows on both inclusive boundary days and drops the days outside', () => {
    const rows = ['2026-07-21', '2026-07-22', '2026-08-20', '2026-08-21'].map((d) => row(d))
    expect(rowsInRange(rows, { from: '2026-07-22', to: '2026-08-20' }).map((r) => r.date))
      .toEqual(['2026-07-22', '2026-08-20'])
  })

  it('finds the latest date that has data across campaigns', () => {
    expect(latestDataDate({ a: [row('2026-08-19')], b: [row('2026-08-20'), row('2026-08-01')], c: [] }))
      .toBe('2026-08-20')
    expect(latestDataDate({ a: [], b: [] })).toBeNull()
    expect(latestDataDate({})).toBeNull()
  })

  it('anchors presets to the latest data date', () => {
    expect(resolvePreset('7d', '2026-08-20', WINDOW)).toEqual({ from: '2026-08-14', to: '2026-08-20' })
    expect(resolvePreset('30d', '2026-08-20', WINDOW)).toEqual({ from: '2026-07-22', to: '2026-08-20' })
    expect(resolvePreset('90d', '2026-08-20', WINDOW)).toEqual({ from: '2026-05-23', to: '2026-08-20' })
    expect(resolvePreset('all', '2026-08-20', WINDOW)).toEqual({ from: '2025-10-21', to: '2026-08-20' })
    expect(resolvePreset('7d', '2026-03-03', WINDOW)).toEqual({ from: '2026-02-25', to: '2026-03-03' })
  })

  it('returns the previous period of equal length that ends the day before', () => {
    expect(previousPeriod({ from: '2026-07-22', to: '2026-08-20' })).toEqual({ from: '2026-06-22', to: '2026-07-21' })
    expect(previousPeriod({ from: '2026-08-14', to: '2026-08-20' })).toEqual({ from: '2026-08-07', to: '2026-08-13' })
  })
})

describe('classifyPerformance (UI-04 display rule)', () => {
  // Organization baseline: spend 1000, revenue 3000, 50 conversions -> CPA 20, ROAS 3.
  const baseline = () => summarize([row('2026-08-01', { spend: 1000, revenue: 3000, conversions: 50 })])
  const one = (facts: Facts) => summarize([row('2026-08-01', facts)])

  it('uses the documented thresholds', () => {
    expect(PERFORMANCE_RULE).toEqual({ weakRoasBelow: 1.0, weakCpaRatio: 1.25 })
  })

  it('flags weak when ROAS is below 1.0', () => {
    const r = classifyPerformance(one({ spend: 100, revenue: 90, conversions: 10 }), baseline())
    expect(r.flag).toBe('weak')
    expect(r.reason).toMatch(/ROAS below 1/)
  })

  it('flags weak when CPA is more than 1.25 x the organization CPA', () => {
    const r = classifyPerformance(one({ spend: 260, revenue: 1000, conversions: 10 }), baseline()) // CPA 26 > 25
    expect(r.flag).toBe('weak')
    expect(r.reason).toMatch(/CPA/)
  })

  it('does not flag weak at exactly 1.25 x the organization CPA', () => {
    const r = classifyPerformance(one({ spend: 250, revenue: 1000, conversions: 10 }), baseline()) // CPA 25, ROAS 4
    expect(r.flag).toBe('average')
  })

  it('flags weak when there is spend but no conversions', () => {
    const r = classifyPerformance(one({ spend: 50, revenue: 100, conversions: 0 }), baseline())
    expect(r.flag).toBe('weak')
    expect(r.reason).toMatch(/no conversions/i)
  })

  it('flags strong when ROAS and CPA are at least as good as the organization', () => {
    expect(classifyPerformance(one({ spend: 100, revenue: 400, conversions: 10 }), baseline()).flag).toBe('strong')
    expect(classifyPerformance(one({ spend: 100, revenue: 300, conversions: 5 }), baseline()).flag).toBe('strong')
  })

  it('flags average otherwise', () => {
    const r = classifyPerformance(one({ spend: 180, revenue: 450, conversions: 10 }), baseline()) // ROAS 2.5, CPA 18
    expect(r).toEqual({ flag: 'average', reason: null })
  })

  it('reports no data when the campaign has no spend in the range', () => {
    expect(classifyPerformance(one({ clicks: 5, impressions: 100 }), baseline()).flag).toBe('no_data')
    expect(classifyPerformance(summarize([]), baseline()).flag).toBe('no_data')
  })

  it('still flags spend without conversions when the organization CPA is null', () => {
    const noConversions = summarize([row('2026-08-01', { spend: 100, revenue: 150 })])
    expect(noConversions.cpa).toBeNull()
    expect(classifyPerformance(one({ spend: 100, revenue: 150 }), noConversions).flag).toBe('weak')
  })
})

describe('buildPerformance and filterPerformance', () => {
  // A (meta): CPA 30, ROAS 2. B (google): CPA 14, ROAS 4. Org: CPA 1000/60 = 16.67, so 1.25 x = 20.83.
  const A = campaign('a', 'meta')
  const B = campaign('b', 'google', 'paused')
  const C = campaign('c', 'meta', null)
  const metrics = {
    a: [row('2026-08-01', { spend: 300, revenue: 600, conversions: 10 }), row('2026-06-01', { spend: 999, conversions: 1 })],
    b: [row('2026-08-01', { spend: 700, revenue: 2800, conversions: 50 })],
    c: [row('2026-08-01', { clicks: 5, impressions: 100 })],
  }
  const range = { from: '2026-07-22', to: '2026-08-20' }

  it('only counts rows inside the range and keeps the API campaign order', () => {
    const perf = buildPerformance([A, B, C], metrics, range)
    expect(perf.map((p) => p.campaign.id)).toEqual(['a', 'b', 'c'])
    expect(perf[0].totals.spend).toBe(300)
  })

  it('flags against the whole organization and excludes no-data campaigns from the baseline', () => {
    const perf = buildPerformance([A, B, C], metrics, range)
    expect(perf.map((p) => p.flag)).toEqual(['weak', 'strong', 'no_data'])
  })

  it('keeps flags unchanged when platform or status filters are applied', () => {
    const meta = filterPerformance(buildPerformance([A, B, C], metrics, range), 'meta', 'all')
    expect(meta.map((p) => [p.campaign.id, p.flag])).toEqual([['a', 'weak'], ['c', 'no_data']])
    // Classifying A against meta campaigns only would wrongly make it strong.
    expect(buildPerformance([A, C], metrics, range)[0].flag).toBe('strong')
  })

  it('filters by status, treating a null status as unknown', () => {
    const perf = buildPerformance([A, B, C], metrics, range)
    expect(filterPerformance(perf, 'all', 'paused').map((p) => p.campaign.id)).toEqual(['b'])
    expect(filterPerformance(perf, 'all', 'unknown').map((p) => p.campaign.id)).toEqual(['c'])
    expect(filterPerformance(perf, 'all', 'all')).toHaveLength(3)
  })

  it('handles an organization with no campaigns', () => {
    expect(buildPerformance([], {}, range)).toEqual([])
  })

  it('treats a campaign with no metric rows at all as no data', () => {
    const perf = buildPerformance([A, campaign('d', 'google')], { a: metrics.a }, range)
    expect(perf[1].flag).toBe('no_data')
    expect(perf[1].totals.days).toBe(0)
  })
})

describe('percentChange', () => {
  it('returns the relative change only when both values exist and the previous is not 0', () => {
    expect(percentChange(110, 100)).toBeCloseTo(0.1, 12)
    expect(percentChange(90, 100)).toBeCloseTo(-0.1, 12)
    expect(percentChange(5, 0)).toBeNull()
    expect(percentChange(null, 5)).toBeNull()
    expect(percentChange(5, null)).toBeNull()
  })
})
