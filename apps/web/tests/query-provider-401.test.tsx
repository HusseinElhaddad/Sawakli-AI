import { useQuery } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { QueryProvider, isUnauthorized, shouldRetry } from '@/components/providers/query-provider'
import { ApiError } from '@/lib/api-client'
import { redirectToLogin } from '@/lib/auth-redirect'

vi.mock('@/lib/auth-redirect', () => ({ redirectToLogin: vi.fn() }))

function Probe({ error }: { error: Error }) {
  const { isError } = useQuery({ queryKey: ['probe', error.message], queryFn: () => Promise.reject(error) })
  return <p>{isError ? 'failed' : 'loading'}</p>
}

describe('central session-expiry handling (ARCH-06 §4)', () => {
  afterEach(() => vi.clearAllMocks())

  it('redirects to login once any query returns 401', async () => {
    render(<QueryProvider><Probe error={new ApiError('Your session has expired. Please sign in again.', 401)} /></QueryProvider>)
    await waitFor(() => expect(redirectToLogin).toHaveBeenCalledTimes(1))
  })

  it('does not redirect for other client errors', async () => {
    render(<QueryProvider><Probe error={new ApiError('The requested resource could not be found.', 404)} /></QueryProvider>)
    expect(await screen.findByText('failed')).toBeInTheDocument()
    expect(redirectToLogin).not.toHaveBeenCalled()
  })

  it('retries server and network failures once but never client errors', () => {
    expect(isUnauthorized(new ApiError('x', 401))).toBe(true)
    expect(isUnauthorized(new ApiError('x', 403))).toBe(false)
    expect(shouldRetry(0, new ApiError('x', 401))).toBe(false)
    expect(shouldRetry(0, new ApiError('x', 404))).toBe(false)
    expect(shouldRetry(0, new ApiError('x', 503))).toBe(true)
    expect(shouldRetry(1, new ApiError('x', 503))).toBe(false)
    expect(shouldRetry(0, new TypeError('Failed to fetch'))).toBe(true)
  })
})
