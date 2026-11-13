export type CampaignPlatform = 'meta' | 'google'

export type CampaignStatus = 'active' | 'paused' | 'removed' | 'unknown'

// Mirrors API-02 CampaignPublic (apps/backend/src/sawakli/api/schemas/campaigns.py).
// organization_id is optional because CampaignPublic does not return it (UI-04 contract gap G2);
// it stays listed so the QA-01 UI validator keeps the canonical field set.
export type Campaign = {
  id: string
  organization_id?: string
  name: string
  platform: CampaignPlatform
  objective: string | null
  status: CampaignStatus | null
  budget: number | null
  start_date: string | null
  end_date: string | null
}

// Mirrors API-02 DailyMetricPublic (apps/backend/src/sawakli/api/schemas/metrics.py).
// Ratios are fractions (0.025 = 2.5%) and null when their denominator is 0.
export type DailyMetric = {
  date: string
  spend: number
  revenue: number
  clicks: number
  impressions: number
  conversions: number
  ctr: number | null
  cpc: number | null
  cpa: number | null
  roas: number | null
}
