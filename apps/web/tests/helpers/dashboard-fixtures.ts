import type { Session } from '@/lib/session'
import type { Campaign, DailyMetric } from '@/types'

/** Synthetic, schema-shaped API-02 fixtures (CampaignPublic / DailyMetricPublic). Not real data. */

export const SESSION: Session = {
  access_token: 'test-token',
  user: { id: 'user-1', name: 'Test User', email: 'test@example.com' },
  organization: { id: 'org-1', name: 'Test workspace' },
}

export function campaign(id: string, name: string, platform: Campaign['platform'], status: Campaign['status']): Campaign {
  return { id, name, platform, status, objective: 'Sales', budget: 1500, start_date: '2026-05-01', end_date: null }
}

export function metric(date: string, spend: number, revenue: number, clicks: number, impressions: number, conversions: number): DailyMetric {
  const div = (a: number, b: number) => (b === 0 ? null : a / b)
  return {
    date, spend, revenue, clicks, impressions, conversions,
    ctr: div(clicks, impressions), cpc: div(spend, clicks), cpa: div(spend, conversions), roas: div(revenue, spend),
  }
}

export const ALPHA = campaign('c1', 'Alpha Push', 'meta', 'active')
export const BETA = campaign('c2', 'Beta Search', 'google', 'paused')

/**
 * Hand-calculated expectations:
 * - Last 90 days of data (05-23 → 08-20): spend 1,500, clicks 750, conversions 85, impressions 30,000,
 *   revenue 4,400 → CTR 2.50%, CPA 17.65, ROAS 2.93×; no earlier data.
 *   Alpha CPA 30 > 1.25 × 17.65 = 22.06 → Weak. Beta ROAS 3.17 ≥ 2.93 and CPA 16 ≤ 17.65 → Strong.
 * - Last 30 days of data (07-22 → 08-20): spend 1,000, CPA 16.67, ROAS 3.40×; previous 30 days
 *   (06-22 → 07-21, fully covered: data starts 06-22): spend 500, CPA 20, ROAS 2.00× → spend +100.0%,
 *   CPA −16.7%, ROAS +70.0%.
 */
export const METRICS: Record<string, DailyMetric[]> = {
  c1: [metric('2026-08-20', 300, 600, 100, 5000, 10)],
  c2: [metric('2026-06-22', 500, 1000, 250, 10000, 25), metric('2026-08-20', 700, 2800, 400, 15000, 50)],
}
