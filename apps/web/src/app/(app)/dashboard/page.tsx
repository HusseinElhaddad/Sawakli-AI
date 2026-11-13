'use client'

import { Suspense } from 'react'
import {
  LineChart,
  ArrowRight,
  AlertTriangle,
  Lightbulb,
} from 'lucide-react'
import Link from 'next/link'
import { useAnomalies } from '@/hooks/useAnomalies'
import { useRecommendations } from '@/hooks/useRecommendations'
import { useSession } from '@/hooks/useSession'
import { daysInRange } from '@/features/dashboard/aggregate'
import { DataThrough, EmptyState, ErrorState, LoadingState, NoDataInWindow } from '@/features/dashboard/components/DataState'
import { FilterBar } from '@/features/dashboard/components/FilterBar'
import { KpiCards } from '@/features/dashboard/components/KpiCards'
import { NeedsAttention } from '@/features/dashboard/components/NeedsAttention'
import { useCampaignPerformance } from '@/features/dashboard/useCampaignPerformance'
import { useDashboardFilters } from '@/features/dashboard/useDashboardFilters'

export default function DashboardPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <DashboardContent />
    </Suspense>
  )
}

function LivePerformance() {
  const [filters, setFilters] = useDashboardFilters()
  const view = useCampaignPerformance(filters)

  return (
    <section aria-label="Campaign performance">
      <FilterBar filters={filters} onChange={setFilters} />
      {view.status === 'loading' && <LoadingState />}
      {view.status === 'error' && <ErrorState error={view.error} onRetry={view.retry} />}
      {view.status === 'empty' && <EmptyState />}
      {view.status === 'no-data' && <NoDataInWindow fetchRange={view.fetchRange} />}
      {view.status === 'ready' && (
        <>
          <DataThrough latest={view.latest} range={view.range} isRefreshing={view.isRefreshing} />
          {view.rows.length === 0 ? (
            <p className="muted-line">No campaigns match these filters.</p>
          ) : view.current.days === 0 ? (
            <p className="muted-line">The selected campaigns have no data in this range.</p>
          ) : (
            <KpiCards current={view.current} previous={view.previous} periodDays={daysInRange(view.range)} />
          )}
          <NeedsAttention rows={view.rows} filters={filters} />
        </>
      )}
    </section>
  )
}

function DashboardContent() {
  const session = useSession()
  const orgId = session?.organization.id ?? ''
  const { data: anomalies } = useAnomalies()
  const { data: recommendations } = useRecommendations(orgId)

  const pendingRecs = recommendations?.filter((r) => r.status === 'pending') ?? []

  return (
    <>
      <div className="demo-notice" role="status">
        <strong>Live KPIs, sample AI panels</strong>
        <span>KPI cards and the campaign table use your workspace&apos;s imported data. Active Anomalies and Pending Recommendations below are sample data until the AI output endpoints are available.</span>
      </div>

      <LivePerformance />

      {/* Performance Overview Chart Placeholder */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 16 }}>
          <div className="card-header" style={{ marginBottom: 0 }}>
            <LineChart />
            Performance Overview
          </div>
          <Link
            href="/campaigns"
            style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12, fontWeight: 'var(--font-weight-semibold)', color: 'var(--color-accent)' }}
          >
            View Campaigns <ArrowRight style={{ width: 12, height: 12 }} />
          </Link>
        </div>
        <div className="chart-placeholder">
          <LineChart />
          Recharts area chart — spend, clicks, conversions over 30 days
        </div>
      </div>

      {/* Two-column: Anomalies + Recommendations */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 20 }}>
        {/* Active Anomalies */}
        <div className="card" style={{ marginBottom: 0 }}>
          <div className="card-header">
            <AlertTriangle />
            Active Anomalies
            <span className="badge sample-badge">Sample data</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {anomalies?.map((a) => (
              <div
                key={a.id}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 12,
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--color-border)',
                  padding: 12,
                  background: a.severity === 'high' ? 'var(--color-error-light)' : 'var(--color-warning-light)',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    width: 32,
                    height: 32,
                    flexShrink: 0,
                    alignItems: 'center',
                    justifyContent: 'center',
                    borderRadius: 8,
                    background: a.severity === 'high' ? 'rgba(217,54,68,0.12)' : 'rgba(200,138,4,0.12)',
                    color: a.severity === 'high' ? 'var(--color-error)' : 'var(--color-warning)',
                  }}
                >
                  <AlertTriangle style={{ width: 16, height: 16 }} />
                </div>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 'var(--font-weight-semibold)', marginBottom: 2 }}>
                    {a.metric_name} anomaly ({a.direction})
                  </div>
                  <div style={{ fontSize: 12, lineHeight: 1.4, color: 'var(--color-text-muted)' }}>
                    Score: {a.anomaly_score.toFixed(2)} &middot; Severity: {a.severity}
                  </div>
                  <div style={{ marginTop: 4, fontSize: 11, color: 'var(--color-text-faint)' }}>
                    {a.detected_at}
                  </div>
                </div>
              </div>
            ))}
            {(!anomalies || anomalies.length === 0) && (
              <p style={{ padding: '16px 0', textAlign: 'center', fontSize: 12, color: 'var(--color-text-muted)' }}>
                No active anomalies detected.
              </p>
            )}
          </div>
        </div>

        {/* Pending Recommendations */}
        <div className="card" style={{ marginBottom: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 16 }}>
            <div className="card-header" style={{ marginBottom: 0 }}>
              <Lightbulb />
              Pending Recommendations
              <span className="badge sample-badge">Sample data</span>
            </div>
            <Link
              href="/recommendations"
              style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12, fontWeight: 'var(--font-weight-semibold)', color: 'var(--color-accent)' }}
            >
              View All <ArrowRight style={{ width: 12, height: 12 }} />
            </Link>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {pendingRecs.map((r) => (
              <Link
                key={r.id}
                href={`/recommendations/${r.id}`}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 12,
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--color-border)',
                  padding: 12,
                  color: 'inherit',
                  transition: 'border-color var(--transition)',
                }}
              >
                <span
                  style={{
                    marginTop: 5,
                    display: 'block',
                    width: 8,
                    height: 8,
                    flexShrink: 0,
                    borderRadius: '50%',
                    background:
                      r.risk_rating === 'high'
                        ? 'var(--color-error)'
                        : r.risk_rating === 'medium'
                          ? 'var(--color-warning)'
                          : 'var(--color-success)',
                  }}
                />
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 'var(--font-weight-semibold)' }}>{r.problem}</div>
                  <div style={{ marginTop: 2, fontSize: 12, color: 'var(--color-text-muted)' }}>
                    {r.campaign_name} · {Math.round(r.confidence_score * 100)}% confidence
                  </div>
                </div>
              </Link>
            ))}
            {pendingRecs.length === 0 && (
              <p style={{ padding: '16px 0', textAlign: 'center', fontSize: 12, color: 'var(--color-text-muted)' }}>
                No pending recommendations.
              </p>
            )}
          </div>
        </div>
      </div>
    </>
  )
}
