import { describe, expect, it } from 'vitest'
import { DEFAULT_FILTERS, filtersToQuery, hrefWithFilters, parseFilters } from '@/features/dashboard/filters'

describe('dashboard URL filters', () => {
  it('defaults to the last 90 days of data, all platforms and all statuses', () => {
    expect(parseFilters(new URLSearchParams())).toEqual({ range: '90d', platform: 'all', status: 'all' })
    expect(DEFAULT_FILTERS).toEqual({ range: '90d', platform: 'all', status: 'all' })
  })

  it('round-trips non-default filters through the query string', () => {
    const filters = { range: '30d', platform: 'meta', status: 'paused' } as const
    expect(filtersToQuery(filters)).toBe('range=30d&platform=meta&status=paused')
    expect(parseFilters(new URLSearchParams(filtersToQuery(filters)))).toEqual(filters)
  })

  it('leaves defaults out of the URL', () => {
    expect(filtersToQuery(DEFAULT_FILTERS)).toBe('')
    expect(hrefWithFilters('/campaigns', DEFAULT_FILTERS)).toBe('/campaigns')
    expect(hrefWithFilters('/campaigns', { ...DEFAULT_FILTERS, platform: 'google' })).toBe('/campaigns?platform=google')
  })

  it('falls back to defaults for unknown values', () => {
    expect(parseFilters(new URLSearchParams('range=365d&platform=tiktok&status=deleted'))).toEqual(DEFAULT_FILTERS)
  })
})
