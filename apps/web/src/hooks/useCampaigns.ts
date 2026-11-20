import { useQueries, useQuery } from '@tanstack/react-query'
import { getCampaign, getCampaignMetrics, getCampaigns } from '@/services/campaigns.service'
import type { Campaign, DailyMetric } from '@/types'

// Every key includes the organization id so cached data never crosses organizations.

export function useCampaigns(orgId: string | undefined, accessToken: string | undefined) {
  return useQuery<Campaign[]>({
    queryKey: ['campaigns', orgId],
    queryFn: () => getCampaigns(orgId ?? '', accessToken ?? ''),
    enabled: !!orgId && !!accessToken,
  })
}

export function useCampaign(orgId: string | undefined, accessToken: string | undefined, campaignId: string) {
  return useQuery<Campaign>({
    queryKey: ['campaign', orgId, campaignId],
    queryFn: () => getCampaign(orgId ?? '', campaignId, accessToken ?? ''),
    enabled: !!orgId && !!accessToken && !!campaignId,
  })
}

export function useCampaignMetrics(
  orgId: string | undefined,
  accessToken: string | undefined,
  campaignIds: readonly string[],
  fetchRange: { from: string; to: string },
) {
  return useQueries({
    queries: campaignIds.map((campaignId) => ({
      queryKey: ['campaign-metrics', orgId, campaignId, fetchRange.from, fetchRange.to],
      queryFn: (): Promise<DailyMetric[]> => getCampaignMetrics(orgId ?? '', campaignId, fetchRange, accessToken ?? ''),
      enabled: !!orgId && !!accessToken,
    })),
  })
}
