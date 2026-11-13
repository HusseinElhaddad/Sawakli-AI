import { apiRequest } from '@/lib/api-client'
import type { Anomaly, Campaign, DailyMetric } from '@/types'
import { mockAnomalies } from '@/lib/mock-data/anomalies'

/** API-02 endpoints. The organization in the path is checked against the token by FastAPI. */
function campaignsPath(orgId: string): string {
  return `/api/orgs/${encodeURIComponent(orgId)}/campaigns`
}

export function getCampaigns(orgId: string, accessToken: string): Promise<Campaign[]> {
  return apiRequest<Campaign[]>(campaignsPath(orgId), { method: 'GET', accessToken })
}

export function getCampaign(orgId: string, campaignId: string, accessToken: string): Promise<Campaign> {
  return apiRequest<Campaign>(`${campaignsPath(orgId)}/${encodeURIComponent(campaignId)}`, {
    method: 'GET',
    accessToken,
  })
}

/** Daily rows for an inclusive `from`–`to` range (`YYYY-MM-DD`), ordered by date. */
export function getCampaignMetrics(
  orgId: string,
  campaignId: string,
  range: { from: string; to: string },
  accessToken: string,
): Promise<DailyMetric[]> {
  const query = new URLSearchParams({ from: range.from, to: range.to })
  return apiRequest<DailyMetric[]>(
    `${campaignsPath(orgId)}/${encodeURIComponent(campaignId)}/metrics?${query.toString()}`,
    { method: 'GET', accessToken },
  )
}

/** Sample data: anomalies stay mocked until the API-05 AI output endpoints exist. */
export async function getAnomalies(): Promise<Anomaly[]> {
  return mockAnomalies
}
