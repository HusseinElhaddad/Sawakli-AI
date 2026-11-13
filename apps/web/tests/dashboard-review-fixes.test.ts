import { describe, expect, it } from 'vitest'
import {
  classifyPerformance,
  coveredPreviousPeriod,
  daysInRange,
  earliestDataDate,
  fetchWindow,
  resolvePreset,
  summarize,
} from '@/features/dashboard/aggregate'
import { roundChange } from '@/features/dashboard/format'
import { metric } from './helpers/dashboard-fixtures'

// Regression tests for the UI-04 independent review findings.
describe('ranges never reach outside the fetched window', () => {
  const window = { from: '2025-10-22', to: '2026-10-21' }

  it('fetches exactly 365 days including today', () => {
    expect(fetchWindow('2026-10-21')).toEqual(window)
    expect(daysInRange(fetchWindow('2026-10-21'))).toBe(365)
  })

  it('clamps a preset that would start before the fetched window', () => {
    // Latest data 2025-11-30: 90 days back is 2025-09-02, but only 2025-10-22 onward was fetched.
    expect(resolvePreset('90d', '2025-11-30', window)).toEqual({ from: '2025-10-22', to: '2025-11-30' })
  })
})

describe('deltas are only compared against a fully covered previous period', () => {
  const window = { from: '2025-10-22', to: '2026-10-21' }

  it('finds the earliest date with data', () => {
    expect(earliestDataDate({ a: [metric('2026-05-23', 1, 1, 1, 1, 1)], b: [metric('2026-05-01', 1, 1, 1, 1, 1)], c: [] }))
      .toBe('2026-05-01')
    expect(earliestDataDate({})).toBeNull()
  })

  it('returns the previous period when data covers all of it', () => {
    expect(coveredPreviousPeriod({ from: '2026-07-22', to: '2026-08-20' }, window, '2026-05-23'))
      .toEqual({ from: '2026-06-22', to: '2026-07-21' })
  })

  it('returns null when data starts inside the previous period', () => {
    // Data starts 40 days before 2026-08-20, so the previous 30 days hold only 10 days of data.
    expect(coveredPreviousPeriod({ from: '2026-07-22', to: '2026-08-20' }, window, '2026-07-12')).toBeNull()
  })

  it('returns null when the previous period starts before the fetched window', () => {
    expect(coveredPreviousPeriod({ from: '2025-11-01', to: '2025-11-30' }, window, '2020-01-01')).toBeNull()
  })

  it('returns null without any data', () => {
    expect(coveredPreviousPeriod({ from: '2026-07-22', to: '2026-08-20' }, window, null)).toBeNull()
  })
})

describe('float accumulation does not flip a flag at an exact threshold', () => {
  it('treats CPA exactly at 1.25 x the organization CPA as not weak despite 0.1 + 0.2', () => {
    // 0.1 + 0.2 = 0.30000000000000004 in binary floating point; 1.25 x 0.24 = 0.3 exactly in decimal.
    const campaign = summarize([metric('2026-08-01', 0.1, 0.3, 1, 10, 0), metric('2026-08-02', 0.2, 0.3, 1, 10, 1)])
    const baseline = summarize([metric('2026-08-01', 0.24, 2.4, 1, 10, 1)])
    expect(campaign.cpa).toBeGreaterThan(0.3)
    expect(classifyPerformance(campaign, baseline).flag).toBe('average')
  })
})

describe('delta rounding', () => {
  it('treats a change that displays as 0.0% as no change', () => {
    expect(roundChange(0.00001)).toBe(0)
    expect(roundChange(-0.00049)).toBe(0)
    expect(roundChange(0.1339)).toBe(0.134)
  })
})
