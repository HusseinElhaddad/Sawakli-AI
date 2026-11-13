import { fireEvent, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import CampaignsPage from '@/app/(app)/campaigns/page'
import { getSession } from '@/lib/session'
import { getCampaignMetrics, getCampaigns } from '@/services/campaigns.service'
import { ALPHA, BETA, METRICS, SESSION, campaign, metric } from './helpers/dashboard-fixtures'
import { renderWithClient } from './helpers/render'

const nav = vi.hoisted(() => ({ search: '', replace: vi.fn() }))

vi.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams(nav.search),
  usePathname: () => '/campaigns',
  useRouter: () => ({ replace: nav.replace, push: vi.fn() }),
}))
vi.mock('@/lib/session', () => ({ getSession: vi.fn(), clearSession: vi.fn() }))
vi.mock('@/lib/auth-redirect', () => ({ redirectToLogin: vi.fn() }))
vi.mock('@/services/campaigns.service', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/services/campaigns.service')>()),
  getCampaigns: vi.fn(),
  getCampaignMetrics: vi.fn(),
}))

function bodyRows() {
  const [, body] = screen.getAllByRole('rowgroup')
  return within(body).getAllByRole('row')
}

function names() {
  return bodyRows().map((row) => within(row).getAllByRole('cell')[0].textContent)
}

describe('Campaigns page (UI-04)', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date(2026, 9, 21, 12, 0))
    nav.search = ''
    vi.mocked(getSession).mockReturnValue(SESSION)
    vi.mocked(getCampaigns).mockResolvedValue([BETA, ALPHA])
    vi.mocked(getCampaignMetrics).mockImplementation(async (_org, id) => METRICS[id] ?? [])
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('renders every column from live totals', async () => {
    renderWithClient(<CampaignsPage />)
    const alpha = (await screen.findByRole('link', { name: 'Alpha Push' })).closest('tr')
    if (!alpha) throw new Error('row missing')
    const cells = within(alpha).getAllByRole('cell').map((c) => c.textContent)
    // Alpha (last 90 days): spend 300, clicks 100, conv 10, CTR 2.00%, CPC 3.00, CPA 30.00, ROAS 2.00×.
    expect(cells).toEqual(['Alpha Push', 'Meta', 'Active', '300.00', '100', '10', '2.00%', '3.00', '30.00', '2.00×', 'Weak: CPA more than 25% above the organization CPA'])
  })

  it('highlights weak campaigns with a text badge and sorts them first by default', async () => {
    renderWithClient(<CampaignsPage />)
    await screen.findByRole('link', { name: 'Alpha Push' })
    expect(names()).toEqual(['Alpha Push', 'Beta Search'])
    const [weakRow, strongRow] = bodyRows()
    expect(weakRow).toHaveClass('row-weak')
    expect(within(weakRow).getByText('Weak')).toHaveAttribute('title', 'CPA more than 25% above the organization CPA')
    expect(strongRow).not.toHaveClass('row-weak')
    expect(within(strongRow).getByText('Strong')).toBeInTheDocument()
  })

  it('explains the performance rule under the table and counts rows', async () => {
    renderWithClient(<CampaignsPage />)
    await screen.findByRole('link', { name: 'Alpha Push' })
    expect(screen.getByText(/This is a\s+display rule, not an AI assessment/)).toBeInTheDocument()
    expect(screen.getByText('Showing 2 of 2 campaigns')).toBeInTheDocument()
  })

  it('filters by platform without changing the flag of the remaining campaign', async () => {
    nav.search = 'platform=google'
    renderWithClient(<CampaignsPage />)
    await screen.findByRole('link', { name: 'Beta Search' })
    expect(names()).toEqual(['Beta Search'])
    expect(within(bodyRows()[0]).getByText('Strong')).toBeInTheDocument()
    expect(screen.getByText('Showing 1 of 2 campaigns')).toBeInTheDocument()
  })

  it('sorts by a column when its header is clicked', async () => {
    renderWithClient(<CampaignsPage />)
    await screen.findByRole('link', { name: 'Alpha Push' })
    fireEvent.click(screen.getByRole('button', { name: 'Spend' }))
    expect(names()).toEqual(['Beta Search', 'Alpha Push'])
    fireEvent.click(screen.getByRole('button', { name: /Spend/ }))
    expect(names()).toEqual(['Alpha Push', 'Beta Search'])
  })

  it('shows Unknown for a null status and dashes for ratios without a denominator', async () => {
    vi.mocked(getCampaigns).mockResolvedValue([ALPHA, BETA, campaign('c3', 'Gamma Idle', 'meta', null)])
    vi.mocked(getCampaignMetrics).mockImplementation(async (_org, id) =>
      id === 'c3' ? [metric('2026-08-20', 0, 0, 0, 0, 0)] : METRICS[id] ?? [])
    renderWithClient(<CampaignsPage />)
    const gamma = (await screen.findByRole('link', { name: 'Gamma Idle' })).closest('tr')
    if (!gamma) throw new Error('row missing')
    const cells = within(gamma).getAllByRole('cell').map((c) => c.textContent)
    expect(cells).toEqual(['Gamma Idle', 'Meta', 'Unknown', '0.00', '0', '0', '—', '—', '—', '—', 'No data'])
    expect(names()[2]).toBe('Gamma Idle')
  })
})
