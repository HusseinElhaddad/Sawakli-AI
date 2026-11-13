import { afterEach, describe, expect, it, vi } from 'vitest'
import { getCampaign, getCampaignMetrics, getCampaigns } from '@/services/campaigns.service'

function stubFetch(body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 200 }))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function authHeader(fetchMock: ReturnType<typeof vi.fn>) {
  const [, init] = fetchMock.mock.calls[0]
  return new Headers(init.headers).get('Authorization')
}

describe('campaigns service (API-02)', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('lists campaigns for the organization with the bearer token', async () => {
    const fetchMock = stubFetch([])
    await expect(getCampaigns('org-1', 'test-token')).resolves.toEqual([])
    expect(fetchMock).toHaveBeenCalledWith('/api/orgs/org-1/campaigns', expect.objectContaining({ method: 'GET' }))
    expect(authHeader(fetchMock)).toBe('Bearer test-token')
  })

  it('reads one campaign', async () => {
    const fetchMock = stubFetch({ id: 'c1' })
    await getCampaign('org-1', 'c1', 'test-token')
    expect(fetchMock.mock.calls[0][0]).toBe('/api/orgs/org-1/campaigns/c1')
  })

  it('reads daily metrics with the required inclusive from/to dates', async () => {
    const fetchMock = stubFetch([])
    await getCampaignMetrics('org-1', 'c1', { from: '2025-10-21', to: '2026-10-21' }, 'test-token')
    expect(fetchMock.mock.calls[0][0]).toBe('/api/orgs/org-1/campaigns/c1/metrics?from=2025-10-21&to=2026-10-21')
    expect(authHeader(fetchMock)).toBe('Bearer test-token')
  })

  it('encodes path segments', async () => {
    const fetchMock = stubFetch({})
    await getCampaign('org/1', '../x', 'test-token')
    expect(fetchMock.mock.calls[0][0]).toBe('/api/orgs/org%2F1/campaigns/..%2Fx')
  })
})
