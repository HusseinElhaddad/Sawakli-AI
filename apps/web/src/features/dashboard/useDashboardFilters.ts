import { useCallback, useMemo } from 'react'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import { hrefWithFilters, parseFilters } from './filters'
import type { DashboardFilters } from './types'

/** Filters live in the URL so they survive navigation between the dashboard and the table. */
export function useDashboardFilters(): [DashboardFilters, (next: DashboardFilters) => void] {
  const searchParams = useSearchParams()
  const pathname = usePathname()
  const router = useRouter()
  const filters = useMemo(() => parseFilters(searchParams), [searchParams])

  const setFilters = useCallback(
    (next: DashboardFilters) => router.replace(hrefWithFilters(pathname, next), { scroll: false }),
    [pathname, router],
  )

  return [filters, setFilters]
}
