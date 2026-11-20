'use client'

import Link from 'next/link'
import { Suspense, useState } from 'react'
import { ArrowDown, ArrowUp } from 'lucide-react'
import { PerformanceBadge, PlatformBadge, StatusBadge } from '@/features/dashboard/components/Badges'
import { DataThrough, EmptyState, ErrorState, LoadingState, NoDataInWindow } from '@/features/dashboard/components/DataState'
import { FilterBar } from '@/features/dashboard/components/FilterBar'
import { formatInteger, formatMoney, formatPercent, formatRoas } from '@/features/dashboard/format'
import { DEFAULT_SORT, initialDirection, sortPerformance, type SortKey, type SortState } from '@/features/dashboard/sort'
import { useCampaignPerformance } from '@/features/dashboard/useCampaignPerformance'
import { useDashboardFilters } from '@/features/dashboard/useDashboardFilters'

const COLUMNS: ReadonlyArray<{ key: SortKey; label: string; numeric?: boolean }> = [
  { key: 'name', label: 'Campaign' },
  { key: 'platform', label: 'Platform' },
  { key: 'status', label: 'Status' },
  { key: 'spend', label: 'Spend', numeric: true },
  { key: 'clicks', label: 'Clicks', numeric: true },
  { key: 'conversions', label: 'Conv.', numeric: true },
  { key: 'ctr', label: 'CTR', numeric: true },
  { key: 'cpc', label: 'CPC', numeric: true },
  { key: 'cpa', label: 'CPA', numeric: true },
  { key: 'roas', label: 'ROAS', numeric: true },
  { key: 'performance', label: 'Performance' },
]

export default function CampaignsPage() {
  return (
    <Suspense fallback={<div className="card"><LoadingState label="Loading campaigns…" /></div>}>
      <CampaignsContent />
    </Suspense>
  )
}

function CampaignsContent() {
  const [filters, setFilters] = useDashboardFilters()
  const view = useCampaignPerformance(filters)
  const [sort, setSort] = useState<SortState>(DEFAULT_SORT)

  function toggleSort(key: SortKey) {
    setSort((current) =>
      current.key === key
        ? { key, direction: current.direction === 'asc' ? 'desc' : 'asc' }
        : { key, direction: initialDirection(key) },
    )
  }

  return (
    <div className="card">
      <div className="campaigns-header">
        <h2>All Campaigns</h2>
      </div>
      <FilterBar filters={filters} onChange={setFilters} />

      {view.status === 'loading' && <LoadingState label="Loading campaigns…" />}
      {view.status === 'error' && <ErrorState error={view.error} onRetry={view.retry} />}
      {view.status === 'empty' && <EmptyState />}
      {view.status === 'no-data' && <NoDataInWindow fetchRange={view.fetchRange} />}

      {view.status === 'ready' && (
        <>
          <DataThrough latest={view.latest} range={view.range} isRefreshing={view.isRefreshing} />
          <div className="table-wrapper">
            <table className="table">
              <thead>
                <tr style={{ background: 'var(--color-surface-raised)' }}>
                  {COLUMNS.map((column) => {
                    const active = sort.key === column.key
                    return (
                      <th
                        key={column.key}
                        style={{ whiteSpace: 'nowrap' }}
                        aria-sort={active ? (sort.direction === 'asc' ? 'ascending' : 'descending') : 'none'}
                      >
                        <button type="button" className="sort-button" onClick={() => toggleSort(column.key)}>
                          {column.label}
                          {active && (sort.direction === 'asc' ? <ArrowUp aria-hidden="true" /> : <ArrowDown aria-hidden="true" />)}
                        </button>
                      </th>
                    )
                  })}
                </tr>
              </thead>
              <tbody>
                {view.rows.length === 0 && (
                  <tr>
                    <td colSpan={COLUMNS.length} className="table-empty">No campaigns match these filters.</td>
                  </tr>
                )}
                {sortPerformance(view.rows, sort).map(({ campaign, totals, flag, reason }) => (
                  <tr key={campaign.id} className={flag === 'weak' ? 'row-weak' : undefined}>
                    <td style={{ whiteSpace: 'nowrap', fontWeight: 'var(--font-weight-bold)' }}>
                      <Link href={`/campaigns/${campaign.id}`} style={{ color: 'inherit' }}>
                        {campaign.name}
                      </Link>
                    </td>
                    <td><PlatformBadge platform={campaign.platform} /></td>
                    <td><StatusBadge status={campaign.status} /></td>
                    <td>{formatMoney(totals.spend)}</td>
                    <td>{formatInteger(totals.clicks)}</td>
                    <td>{formatInteger(totals.conversions)}</td>
                    <td title={totals.ctr === null ? 'No impressions in this range' : undefined}>{formatPercent(totals.ctr)}</td>
                    <td title={totals.cpc === null ? 'No clicks in this range' : undefined}>{formatMoney(totals.cpc)}</td>
                    <td title={totals.cpa === null ? 'No conversions in this range' : undefined}>{formatMoney(totals.cpa)}</td>
                    <td title={totals.roas === null ? 'No spend in this range' : undefined}>{formatRoas(totals.roas)}</td>
                    <td><PerformanceBadge flag={flag} reason={reason} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="perf-legend">
            <strong>Performance</strong> compares each campaign with your organization&apos;s totals for the
            selected dates, across all platforms and statuses. <strong>Weak</strong>: ROAS below 1.0×, CPA more
            than 25% above the organization CPA, or spend with no conversions. <strong>Strong</strong>: ROAS and CPA
            at least as good as the organization&apos;s. <strong>No data</strong>: no spend in this range. This is a
            display rule, not an AI assessment. Amounts are shown without a currency because the data carries none.
          </p>

          <div className="table-footer">
            <span>Showing {view.rows.length} of {view.totalCampaigns} campaigns</span>
          </div>
        </>
      )}
    </div>
  )
}
