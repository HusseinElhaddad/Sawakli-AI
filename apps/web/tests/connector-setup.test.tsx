import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ConnectorSetupPage from '@/app/(auth)/setup/connector/page'
import { getSession } from '@/lib/session'
import { createCsvConnector, uploadCsv } from '@/services/connectors.service'

const push = vi.fn()

vi.mock('next/navigation', () => ({ useRouter: () => ({ push }) }))
vi.mock('@/lib/session', () => ({ getSession: vi.fn() }))
vi.mock('@/services/connectors.service', () => ({
  createCsvConnector: vi.fn(),
  uploadCsv: vi.fn(),
}))

describe('ConnectorSetupPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getSession).mockReturnValue({
      access_token: 'test-token',
      user: { id: 'user-1', name: 'Test User', email: 'test@example.com' },
      organization: { id: 'org-1', name: 'Test workspace' },
    })
  })

  it('uploads a CSV through API-03 and shows the successful import state', async () => {
    vi.mocked(createCsvConnector).mockResolvedValue({
      data_source_id: 'source-1', provider: 'csv_demo', status: 'disconnected', sync_status: 'pending', last_synced_at: null,
    })
    vi.mocked(uploadCsv).mockResolvedValue({
      data_source_id: 'source-1', row_count: 4, parsed_rows: [], parse_warnings: [], sync_status: 'success', last_synced_at: '2026-10-01T12:00:00Z',
    })
    render(<ConnectorSetupPage />)

    const file = new File(['date,spend\n2026-01-01,10'], 'campaigns.csv', { type: 'text/csv' })
    fireEvent.change(screen.getByLabelText('CSV file'), { target: { files: [file] } })
    fireEvent.click(screen.getByRole('button', { name: 'Upload and import CSV' }))

    await waitFor(() => expect(uploadCsv).toHaveBeenCalledWith('test-token', 'source-1', file))
    expect(createCsvConnector).toHaveBeenCalledWith('test-token')
    expect(screen.getByText('CSV imported')).toBeInTheDocument()
    expect(screen.getByText(/sync status: success/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Continue to demo dashboard' })).toBeEnabled()
  })

  it('rejects a non-CSV file before an API request', () => {
    render(<ConnectorSetupPage />)
    fireEvent.change(screen.getByLabelText('CSV file'), {
      target: { files: [new File(['not csv'], 'notes.txt', { type: 'text/plain' })] },
    })

    expect(screen.getByRole('alert')).toHaveTextContent('Choose a CSV file to continue.')
    expect(createCsvConnector).not.toHaveBeenCalled()
  })

  it('lets a user skip optional import and provides the approved sample CSV', () => {
    render(<ConnectorSetupPage />)

    const sample = screen.getByRole('link', { name: 'Download sample CSV' })
    expect(sample).toHaveAttribute('href', '/samples/sawakli-campaign-data.csv')
    expect(sample).toHaveAttribute('download')

    fireEvent.click(screen.getByRole('button', { name: 'Skip for now' }))
    expect(push).toHaveBeenCalledWith('/dashboard')
    expect(createCsvConnector).not.toHaveBeenCalled()
  })
})
