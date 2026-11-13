import { clearSession } from '@/lib/session'

/**
 * ARCH-06 §4 expired-session rule: clear the stored session and fully navigate to /login. A full
 * navigation also discards every cached query, so no organization data outlives the session.
 */
export function redirectToLogin(): void {
  clearSession()
  window.location.replace('/login')
}
