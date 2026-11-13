'use client'

import { QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { ApiError } from '@/lib/api-client'
import { redirectToLogin } from '@/lib/auth-redirect'

export function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401
}

/** Client errors (4xx) are not retried; other failures are retried once. */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError && error.status < 500) return false
  return failureCount < 1
}

/**
 * One central rule for an expired or missing session on any protected query (ARCH-06 §4). Mutations
 * are not covered: POST /api/auth/login answers 401 for wrong credentials, which is not an expiry.
 */
function handleError(error: unknown): void {
  if (isUnauthorized(error)) redirectToLogin()
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    queryCache: new QueryCache({ onError: handleError }),
    defaultOptions: {
      queries: {
        staleTime: 60 * 1000,
        retry: shouldRetry,
      },
    },
  })
}

export function QueryProvider({ children }: { children: ReactNode }) {
  const [queryClient] = useState(createQueryClient)

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}
