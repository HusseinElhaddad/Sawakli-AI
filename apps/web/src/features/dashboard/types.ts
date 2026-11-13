import type { Campaign, CampaignPlatform, CampaignStatus } from '@/types'

/** Date presets are anchored to the latest date that has data, not to today. */
export type DatePreset = '7d' | '30d' | '90d' | 'all'

/** Inclusive calendar range of `YYYY-MM-DD` strings. */
export type DateRange = {
  from: string
  to: string
}

export type PlatformFilter = 'all' | CampaignPlatform
export type StatusFilter = 'all' | CampaignStatus

export type DashboardFilters = {
  range: DatePreset
  platform: PlatformFilter
  status: StatusFilter
}

/** The five raw facts stored in daily_metrics (PROD-01 §2). */
export type MetricFacts = {
  spend: number
  revenue: number
  clicks: number
  impressions: number
  conversions: number
}

/** Summed facts plus ratios computed from the sums; `days` counts the daily rows included. */
export type KpiSummary = MetricFacts & {
  ctr: number | null
  cpc: number | null
  cpa: number | null
  roas: number | null
  days: number
}

/** UI-04 frontend display rule, not the AI-computed canonical health_status. */
export type PerformanceFlag = 'weak' | 'average' | 'strong' | 'no_data'

export type CampaignPerformance = {
  campaign: Campaign
  totals: KpiSummary
  flag: PerformanceFlag
  /** Plain-language reason for a weak flag, otherwise null. */
  reason: string | null
}
