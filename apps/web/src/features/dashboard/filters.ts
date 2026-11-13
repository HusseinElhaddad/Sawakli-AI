import type { DashboardFilters, DatePreset, PlatformFilter, StatusFilter } from './types'

export const DEFAULT_FILTERS: DashboardFilters = { range: '90d', platform: 'all', status: 'all' }

export const RANGE_OPTIONS: ReadonlyArray<{ value: DatePreset; label: string }> = [
  { value: '7d', label: 'Last 7 days of data' },
  { value: '30d', label: 'Last 30 days of data' },
  { value: '90d', label: 'Last 90 days of data' },
  { value: 'all', label: 'All loaded data (last 365 days)' },
]

export const PLATFORM_OPTIONS: ReadonlyArray<{ value: PlatformFilter; label: string }> = [
  { value: 'all', label: 'All platforms' },
  { value: 'meta', label: 'Meta' },
  { value: 'google', label: 'Google' },
]

export const STATUS_OPTIONS: ReadonlyArray<{ value: StatusFilter; label: string }> = [
  { value: 'all', label: 'All statuses' },
  { value: 'active', label: 'Active' },
  { value: 'paused', label: 'Paused' },
  { value: 'removed', label: 'Removed' },
  { value: 'unknown', label: 'Unknown' },
]

type ParamReader = { get(name: string): string | null }

function pick<T extends string>(value: string | null, options: ReadonlyArray<{ value: T }>, fallback: T): T {
  return options.find((option) => option.value === value)?.value ?? fallback
}

/** Reads filters from the URL; unknown or missing values fall back to the defaults. */
export function parseFilters(params: ParamReader): DashboardFilters {
  return {
    range: pick(params.get('range'), RANGE_OPTIONS, DEFAULT_FILTERS.range),
    platform: pick(params.get('platform'), PLATFORM_OPTIONS, DEFAULT_FILTERS.platform),
    status: pick(params.get('status'), STATUS_OPTIONS, DEFAULT_FILTERS.status),
  }
}

/** Query string without the leading `?`; default values are left out. */
export function filtersToQuery(filters: DashboardFilters): string {
  const params = new URLSearchParams()
  if (filters.range !== DEFAULT_FILTERS.range) params.set('range', filters.range)
  if (filters.platform !== DEFAULT_FILTERS.platform) params.set('platform', filters.platform)
  if (filters.status !== DEFAULT_FILTERS.status) params.set('status', filters.status)
  return params.toString()
}

export function hrefWithFilters(pathname: string, filters: DashboardFilters): string {
  const query = filtersToQuery(filters)
  return query ? `${pathname}?${query}` : pathname
}

export function rangeLabel(range: DatePreset): string {
  return RANGE_OPTIONS.find((option) => option.value === range)?.label ?? range
}
