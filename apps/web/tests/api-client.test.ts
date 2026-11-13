import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, apiRequest } from '@/lib/api-client'
import { uploadCsv } from '@/services/connectors.service'

describe('apiRequest', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('forwards the bearer token and returns JSON data', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ access_token: 'test-token' }), { status: 200 }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiRequest<{ access_token: string }>('/api/auth/login', {
      method: 'POST',
      accessToken: 'test-token',
    })).resolves.toEqual({ access_token: 'test-token' })

    expect(fetchMock).toHaveBeenCalledWith('/api/auth/login', expect.objectContaining({
      headers: expect.any(Headers),
    }))
    const [, init] = fetchMock.mock.calls[0]
    expect((init.headers as Headers).get('Authorization')).toBe('Bearer test-token')
  })

  it('turns a safe API error into an ApiError', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: { code: 'invalid_csv', message: 'Choose a valid CSV file.', retryable: false },
    }), { status: 422 })))

    await expect(apiRequest('/api/connectors/csv/source/upload')).rejects.toMatchObject({
      name: ApiError.name,
      status: 422,
      code: 'invalid_csv',
      retryable: false,
      message: 'Choose a valid CSV file.',
    })
  })

  it('uses the API-03 CSV upload path and multipart field name', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      data_source_id: 'source-1',
      row_count: 1,
      parsed_rows: [],
      parse_warnings: [],
      sync_status: 'success',
      last_synced_at: '2026-10-01T12:00:00Z',
    }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await uploadCsv('test-token', 'source-1', new File(['date,spend'], 'campaigns.csv', { type: 'text/csv' }))

    expect(fetchMock).toHaveBeenCalledWith('/api/connectors/csv/source-1/upload', expect.objectContaining({
      method: 'POST',
    }))
    const [, init] = fetchMock.mock.calls[0]
    expect((init.body as FormData).get('file')).toBeInstanceOf(File)
  })
})
