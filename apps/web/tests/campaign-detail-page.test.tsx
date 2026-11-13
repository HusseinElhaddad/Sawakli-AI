import { screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import CampaignDetailPage from '@/app/(app)/campaigns/[id]/page'
import { ApiError } from '@/lib/api-client'
import { getSession } from '@/lib/session'
import { getCampaign, getCampaigns } from '@/services/campaigns.service'
import { ALPHA, SESSION } from './helpers/dashboard-fixtures'
import { renderWithClient } from './helpers/render'

const nav = vi.hoisted(() => ({ id: 'c1' }))

vi.mock('next/navigation', () => ({ useParams: () => ({ id: nav.id }), useRouter: () => ({ replace: vi.fn() }) }))
vi.mock('@/lib/session', () => ({ getSession: vi.fn(), clearSession: vi.fn() }))
vi.mock('@/lib/auth-redirect', () => ({ redirectToLogin: vi.fn() }))
vi.mock('@/services/campaigns.service', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/services/campaigns.service')>()),
  getCampaign: vi.fn(),
  getCampaigns: vi.fn(),
}))

describe('Campaign detail page (UI-04 minimal fix)', () => {
  beforeEach(() => {
    nav.id = 'c1'
    vi.mocked(getSession).mockReturnValue(SESSION)
  })

  afterEach(() => vi.clearAllMocks())

  it('shows the real campaign header from API-02 and labels the rest as sample content', async () => {
    vi.mocked(getCampaign).mockResolvedValue(ALPHA)
    renderWithClient(<CampaignDetailPage />)
    expect(await screen.findByRole('heading', { name: 'Alpha Push' })).toBeInTheDocument()
    expect(getCampaign).toHaveBeenCalledWith('org-1', 'c1', 'test-token')
    expect(screen.getByText('Sales')).toBeInTheDocument()
    expect(screen.getByText('1 May 2026')).toBeInTheDocument()
    expect(screen.getByText('Sample content')).toBeInTheDocument()
  })

  it.each([
    ['missing or foreign campaign', 404],
    ['malformed id', 422],
  ])('shows not found for a %s and never another campaign', async (_case, status) => {
    nav.id = 'not-a-real-id'
    vi.mocked(getCampaign).mockRejectedValue(new ApiError('The requested resource could not be found.', status))
    renderWithClient(<CampaignDetailPage />)
    expect(await screen.findByText('Campaign not found.')).toBeInTheDocument()
    expect(screen.queryByText('Alpha Push')).not.toBeInTheDocument()
    expect(getCampaigns).not.toHaveBeenCalled()
  })
})
