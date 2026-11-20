import type { Organization, User } from '@/types'

export type Session = {
  user: User
  organization: Organization
  access_token: string
}

const STORAGE_KEY = 'sawakli-session'
const COOKIE_NAME = 'sawakli-auth'

function setCookie(name: string, value: string) {
  document.cookie = `${name}=${value};path=/;samesite=lax`
}

function deleteCookie(name: string) {
  document.cookie = `${name}=;path=/;expires=Thu, 01 Jan 1970 00:00:00 GMT`
}

let cachedRaw: string | null = null
let cachedSession: Session | null = null

export function getSession(): Session | null {
  if (typeof window === 'undefined') return null
  const raw = localStorage.getItem(STORAGE_KEY)
  if (raw === cachedRaw) return cachedSession
  cachedRaw = raw
  if (!raw) {
    cachedSession = null
    return null
  }
  try {
    cachedSession = JSON.parse(raw) as Session
    return cachedSession
  } catch {
    cachedSession = null
    return null
  }
}

export function setSession(session: Session): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
  setCookie(COOKIE_NAME, '1')
}

export function clearSession(): void {
  localStorage.removeItem(STORAGE_KEY)
  deleteCookie(COOKIE_NAME)
}
