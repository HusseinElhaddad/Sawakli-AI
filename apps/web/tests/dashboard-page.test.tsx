import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import DashboardPage from '@/app/(app)/dashboard/page'
import { ApiError } from '@/lib/api-client'
import { redirectToLogin } from '@/lib/auth-redirect'
import { getSession } from '@/lib/session'
import { getCampaignMetrics, getCampaigns } from '@/services/campaigns.service'
import { ALPHA, BETA, METRICS, SESSION } from './helpers/dashboard-fixtures'
import { renderWithClient } from './helpers/render'

const nav = vi.hoisted(() => ({ search: '', replace: vi.fn() }))

vi.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams(nav.search),
  usePathname: () => '/dashboard',
  useRouter: () => ({ replace: nav.replace, push: vi.fn() }),
}))
vi.mock('@/lib/session', () => ({ getSession: vi.fn(), clearSession: vi.fn() }))
vi.mock('@/lib/auth-redirect', () => ({ redirectToLogin: vi.fn() }))
vi.mock('@/services/campaigns.service', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/services/campaigns.service')>()),
  getCampaigns: vi.fn(),
  getCampaignMetrics: vi.fn(),
}))

function kpi(key: string) {
  return within(screen.getByTestId(`kpi-${key}`))
}

describe('Dashboard page (UI-04)', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date(2026, 9, 21, 12, 0))
    nav.search = ''
    vi.mocked(getSession).mockReturnValue(SESSION)
    vi.mocked(getCampaigns).mockResolvedValue([ALPHA, BETA])
    vi.mocked(getCampaignMetrics).mockImplementation(async (_org, id) => METRICS[id] ?? [])
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('loads campaigns and metrics for the session organization over the 365-day window', async () => {
    renderWithClient(<DashboardPage />)
    await screen.findByTestId('kpi-spend')
    expect(getCampaigns).toHaveBeenCalledWith('org-1', 'test-token')
    expect(getCampaignMetrics).toHaveBeenCalledWith('org-1', 'c1', { from: '2025-10-22', to: '2026-10-21' }, 'test-token')
    expect(getCampaignMetrics).toHaveBeenCalledWith('org-1', 'c2', { from: '2025-10-22', to: '2026-10-21' }, 'test-token')
  })

  it('renders the six KPIs from summed facts for the default last 90 days of data', async () => {
    renderWithClient(<DashboardPage />)
    await screen.findByTestId('kpi-spend')
    expect(kpi('spend').getByText('1,500.00')).toBeInTheDocument()
    expect(kpi('clicks').getByText('750')).toBeInTheDocument()
    expect(kpi('conversions').getByText('85')).toBeInTheDocument()
    expect(kpi('ctr').getByText('2.50%')).toBeInTheDocument()
    expect(kpi('cpa').getByText('17.65')).toBeInTheDocument()
    expect(kpi('roas').getByText('2.93×')).toBeInTheDocument()
    expect(screen.queryByTestId('kpi-cpc')).not.toBeInTheDocument()
    expect(screen.getByText('Data through 20 Aug 2026')).toBeInTheDocument()
    expect(screen.getByText('No earlier data to compare with for this range.')).toBeInTheDocument()
    expect(screen.queryByText(/vs previous/)).not.toBeInTheDocument()
  })

  it('shows deltas against the previous period when it has data', async () => {
    nav.search = 'range=30d'
    renderWithClient(<DashboardPage />)
    await screen.findByTestId('kpi-spend')
    expect(kpi('spend').getByText('1,000.00')).toBeInTheDocument()
    expect(kpi('spend').getByText('+100.0% vs previous 30 days')).toBeInTheDocument()
    const cpaDelta = kpi('cpa').getByText('-16.7% vs previous 30 days')
    expect(cpaDelta).toHaveStyle({ color: 'var(--color-success)' })
    expect(kpi('roas').getByText('+70.0% vs previous 30 days')).toHaveStyle({ color: 'var(--color-success)' })
    expect(screen.queryByText('No earlier data to compare with for this range.')).not.toBeInTheDocument()
  })

  it('shows no deltas when data starts inside the previous period', async () => {
    nav.search = 'range=30d'
    vi.mocked(getCampaignMetrics).mockImplementation(async (_org, id) =>
      id === 'c2' ? [{ ...METRICS.c2[0], date: '2026-07-10' }, METRICS.c2[1]] : METRICS[id] ?? [])
    renderWithClient(<DashboardPage />)
    await screen.findByTestId('kpi-spend')
    expect(screen.queryByText(/vs previous/)).not.toBeInTheDocument()
    expect(screen.getByText('No earlier data to compare with for this range.')).toBeInTheDocument()
  })

  it('lists weak campaigns and links to the table with the same filters', async () => {
    nav.search = 'range=30d&platform=meta'
    renderWithClient(<DashboardPage />)
    const strip = await screen.findByRole('region', { name: 'Campaigns that need attention' })
    expect(within(strip).getByText('Alpha Push')).toBeInTheDocument()
    expect(within(strip).queryByText('Beta Search')).not.toBeInTheDocument()
    expect(within(strip).getByRole('link')).toHaveAttribute('href', '/campaigns?range=30d&platform=meta')
  })

  it('writes filter changes to the URL', async () => {
    renderWithClient(<DashboardPage />)
    await screen.findByTestId('kpi-spend')
    fireEvent.change(screen.getByLabelText('Platform'), { target: { value: 'google' } })
    expect(nav.replace).toHaveBeenCalledWith('/dashboard?platform=google', { scroll: false })
  })

  it('shows a loading state instead of zero values while data loads', () => {
    vi.mocked(getCampaigns).mockReturnValue(new Promise(() => {}))
    renderWithClient(<DashboardPage />)
    expect(screen.getByText('Loading campaign data…')).toBeInTheDocument()
    expect(screen.queryByTestId('kpi-spend')).not.toBeInTheDocument()
  })

  it('shows the empty state with a data-source action when the organization has no campaigns', async () => {
    vi.mocked(getCampaigns).mockResolvedValue([])
    renderWithClient(<DashboardPage />)
    expect(await screen.findByText('No marketing data is available yet.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Add a data source' })).toHaveAttribute('href', '/setup/connector')
    expect(screen.queryByTestId('kpi-spend')).not.toBeInTheDocument()
  })

  it('explains when campaigns exist but have no metrics in the fetched window', async () => {
    vi.mocked(getCampaignMetrics).mockResolvedValue([])
    renderWithClient(<DashboardPage />)
    expect(await screen.findByText('No campaign performance data in the last 12 months.')).toBeInTheDocument()
  })

  it('shows an error with a working retry', async () => {
    vi.mocked(getCampaigns)
      .mockRejectedValueOnce(new ApiError('The Sawakli service is unavailable. Please try again.', 503, { retryable: true }))
      .mockResolvedValue([ALPHA, BETA])
    renderWithClient(<DashboardPage />)
    expect(await screen.findByRole('alert')).toHaveTextContent('The Sawakli service is unavailable')
    fireEvent.click(screen.getByRole('button', { name: /retry/i }))
    await screen.findByTestId('kpi-spend')
    expect(kpi('spend').getByText('1,500.00')).toBeInTheDocument()
    expect(getCampaigns).toHaveBeenCalledTimes(2)
  })

  it('never aggregates a partially loaded organization', async () => {
    vi.mocked(getCampaignMetrics).mockImplementation(async (_org, id) => {
      if (id === 'c2') throw new ApiError('The request could not be completed. Please try again.', 500)
      return METRICS[id] ?? []
    })
    renderWithClient(<DashboardPage />)
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.queryByTestId('kpi-spend')).not.toBeInTheDocument()
  })

  it('clears the session and redirects to login on 401', async () => {
    vi.mocked(getCampaigns).mockRejectedValue(new ApiError('Your session has expired. Please sign in again.', 401))
    renderWithClient(<DashboardPage />)
    await waitFor(() => expect(redirectToLogin).toHaveBeenCalled())
  })

  it('redirects to login without calling the API when no session is stored', async () => {
    vi.mocked(getSession).mockReturnValue(null)
    renderWithClient(<DashboardPage />)
    await waitFor(() => expect(redirectToLogin).toHaveBeenCalled())
    expect(getCampaigns).not.toHaveBeenCalled()
  })

  it('labels the AI panels as sample data', async () => {
    renderWithClient(<DashboardPage />)
    await screen.findByTestId('kpi-spend')
    expect(screen.getAllByText('Sample data')).toHaveLength(2)
    expect(screen.getByText('Live KPIs, sample AI panels')).toBeInTheDocument()
  })
})
