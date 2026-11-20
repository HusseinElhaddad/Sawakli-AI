import { afterEach, describe, expect, it, vi } from 'vitest'
import { redirectToLogin } from '@/lib/auth-redirect'
import { clearSession } from '@/lib/session'

vi.mock('@/lib/session', () => ({ clearSession: vi.fn() }))

describe('redirectToLogin', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('clears the stored session before a full navigation to /login', () => {
    const replace = vi.fn()
    vi.stubGlobal('location', { replace })
    redirectToLogin()
    expect(clearSession).toHaveBeenCalled()
    expect(replace).toHaveBeenCalledWith('/login')
  })
})
