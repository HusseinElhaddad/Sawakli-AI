import Link from 'next/link'
import { AlertCircle, Database, RefreshCw } from 'lucide-react'
import { ApiError } from '@/lib/api-client'
import { formatDate } from '../format'
import type { DateRange } from '../types'

export function LoadingState({ label = 'Loading campaign data…' }: { label?: string }) {
  return (
    <div className="data-state" role="status" aria-live="polite">
      <div className="skeleton-row" aria-hidden="true">
        {Array.from({ length: 6 }, (_, i) => <span key={i} className="skeleton" />)}
      </div>
      <p>{label}</p>
    </div>
  )
}

export function EmptyState() {
  return (
    <div className="data-state">
      <Database aria-hidden="true" />
      <strong>No marketing data is available yet.</strong>
      <p>Upload a CSV or connect a provider to begin.</p>
      <Link className="btn btn-primary" href="/setup/connector">Add a data source</Link>
    </div>
  )
}

export function NoDataInWindow({ fetchRange }: { fetchRange: DateRange }) {
  return (
    <div className="data-state">
      <Database aria-hidden="true" />
      <strong>No campaign performance data in the last 12 months.</strong>
      <p>
        Your campaigns have no daily metrics between {formatDate(fetchRange.from)} and {formatDate(fetchRange.to)}.
        Upload newer data to see KPIs here.
      </p>
      <Link className="btn btn-secondary" href="/setup/connector">Upload a CSV</Link>
    </div>
  )
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const message = error instanceof ApiError
    ? error.message
    : 'Sawakli cannot reach the service. Please check your connection and try again.'
  return (
    <div className="data-state data-state-error" role="alert">
      <AlertCircle aria-hidden="true" />
      <strong>Campaign data could not be loaded.</strong>
      <p>{message}</p>
      <button type="button" className="btn btn-secondary" onClick={onRetry}>
        <RefreshCw /> Retry
      </button>
    </div>
  )
}

export function DataThrough({ latest, range, isRefreshing }: { latest: string; range: DateRange; isRefreshing: boolean }) {
  return (
    <p className="data-through">
      <strong>Data through {formatDate(latest)}</strong>
      <span> · Showing {formatDate(range.from)} – {formatDate(range.to)}</span>
      {isRefreshing && <span className="refreshing" role="status"> · Updating data…</span>}
    </p>
  )
}
