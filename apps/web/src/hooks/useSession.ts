import { useEffect, useSyncExternalStore } from 'react'
import { redirectToLogin } from '@/lib/auth-redirect'
import { getSession, type Session } from '@/lib/session'

function subscribe(onChange: () => void): () => void {
  window.addEventListener('storage', onChange)
  return () => window.removeEventListener('storage', onChange)
}

/** The stored browser session; null during server rendering and hydration. */
export function useSession(): Session | null {
  return useSyncExternalStore(subscribe, getSession, () => null)
}

/** Like useSession, but sends the user to /login when no session is stored (ARCH-06 §4). */
export function useRequireSession(): Session | null {
  const session = useSession()

  useEffect(() => {
    if (getSession() === null) redirectToLogin()
  }, [])

  return session
}
