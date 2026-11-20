import { useState } from 'react'
import { useCampaignMetrics, useCampaigns } from '@/hooks/useCampaigns'
import { useRequireSession } from '@/hooks/useSession'
import type { Campaign, DailyMetric } from '@/types'
import {
  buildPerformance,
  combineSummaries,
  coveredPreviousPeriod,
  earliestDataDate,
  fetchWindow,
  filterPerformance,
  latestDataDate,
  localToday,
  resolvePreset,
  rowsInRange,
  summarize,
} from './aggregate'
import type { CampaignPerformance, DashboardFilters, DateRange, KpiSummary } from './types'

export type PerformanceReady = {
  status: 'ready'
  /** Latest date with data for the organization (filters ignored). */
  latest: string
  range: DateRange
  /** Totals for the campaigns that match the filters. */
  current: KpiSummary
  /** Previous equal-length period, or null when it is not fully covered by data (or the range is "all"). */
  previous: KpiSummary | null
  /** Campaigns matching the filters, in API order, flagged against the whole organization. */
  rows: CampaignPerformance[]
  totalCampaigns: number
}

export type PerformanceView = (
  | { status: 'loading' }
  | { status: 'error'; error: unknown }
  | { status: 'empty' }
  | { status: 'no-data'; fetchRange: DateRange }
  | PerformanceReady
) & { isRefreshing: boolean; retry: () => void }

/**
 * Loads the campaign list and each campaign's daily metrics (1 + N requests), then aggregates them
 * for the selected filters. A partially loaded organization is never aggregated.
 */
export function useCampaignPerformance(filters: DashboardFilters): PerformanceView {
  const session = useRequireSession()
  const orgId = session?.organization.id
  const token = session?.access_token
  const [fetchRange] = useState(() => fetchWindow(localToday()))

  const campaignsQuery = useCampaigns(orgId, token)
  const campaigns: Campaign[] = campaignsQuery.data ?? []
  const metricQueries = useCampaignMetrics(orgId, token, campaigns.map((c) => c.id), fetchRange)

  const isRefreshing =
    (campaignsQuery.isFetching && !campaignsQuery.isPending) ||
    metricQueries.some((q) => q.isFetching && !q.isPending)

  const retry = () => {
    void campaignsQuery.refetch()
    for (const query of metricQueries) {
      if (query.isError) void query.refetch()
    }
  }

  const base = { isRefreshing, retry }

  if (campaignsQuery.isError) return { ...base, status: 'error', error: campaignsQuery.error }
  if (!session || campaignsQuery.isPending) return { ...base, status: 'loading' }
  if (campaigns.length === 0) return { ...base, status: 'empty' }

  const failed = metricQueries.find((q) => q.isError)
  if (failed) return { ...base, status: 'error', error: failed.error }
  if (metricQueries.some((q) => q.isPending)) return { ...base, status: 'loading' }

  const metrics: Record<string, DailyMetric[]> = {}
  campaigns.forEach((campaign, i) => {
    metrics[campaign.id] = metricQueries[i]?.data ?? []
  })

  const latest = latestDataDate(metrics)
  if (latest === null) return { ...base, status: 'no-data', fetchRange }

  const range = resolvePreset(filters.range, latest, fetchRange)
  const rows = filterPerformance(buildPerformance(campaigns, metrics, range), filters.platform, filters.status)
  const current = combineSummaries(rows.map((row) => row.totals))

  let previous: KpiSummary | null = null
  if (filters.range !== 'all') {
    const filteredMetrics = Object.fromEntries(rows.map((row) => [row.campaign.id, metrics[row.campaign.id] ?? []]))
    const prevRange = coveredPreviousPeriod(range, fetchRange, earliestDataDate(filteredMetrics))
    if (prevRange) {
      const prevSummary = summarize(rows.flatMap((row) => rowsInRange(metrics[row.campaign.id] ?? [], prevRange)))
      previous = prevSummary.days > 0 ? prevSummary : null
    }
  }

  return { ...base, status: 'ready', latest, range, current, previous, rows, totalCampaigns: campaigns.length }
}
