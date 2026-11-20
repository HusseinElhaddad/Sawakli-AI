import { QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { createQueryClient } from '@/components/providers/query-provider'

/** Renders with the app's real QueryClient (including the central 401 rule) but without retries. */
export function renderWithClient(ui: ReactElement) {
  const client = createQueryClient()
  client.setDefaultOptions({ queries: { ...client.getDefaultOptions().queries, retry: false } })
  return { client, ...render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>) }
}
