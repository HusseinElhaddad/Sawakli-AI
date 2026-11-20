'use client'

import { useParams } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, LineChart, AlertTriangle } from 'lucide-react'
import { useCampaign } from '@/hooks/useCampaigns'
import { useAnomalies } from '@/hooks/useAnomalies'
import { useRequireSession } from '@/hooks/useSession'
import { ApiError } from '@/lib/api-client'
import { PlatformBadge, StatusBadge } from '@/features/dashboard/components/Badges'
import { ErrorState, LoadingState } from '@/features/dashboard/components/DataState'
import { formatDate, formatMoney, NO_VALUE } from '@/features/dashboard/format'

function isNotFound(error: unknown): boolean {
  // 404: missing or another organization's campaign; 422: the id is not a valid UUID.
  return error instanceof ApiError && (error.status === 404 || error.status === 422)
}

export default function CampaignDetailPage() {
  const params = useParams()
  const id = typeof params.id === 'string' ? params.id : ''
  const session = useRequireSession()
  const { data: campaign, isPending, isError, error, refetch } = useCampaign(session?.organization.id, session?.access_token, id)
  const { data: allAnomalies } = useAnomalies()
  // Sample anomalies are keyed by mock ids, so they only match once API-05 provides real ones.
  const anomalies = allAnomalies?.filter((a) => a.campaign_id === id) ?? []

  if (isError && isNotFound(error)) {
    return (
      <div className="data-state">
        <strong>Campaign not found.</strong>
        <p>It may have been removed, or it belongs to another workspace.</p>
        <Link className="btn btn-secondary" href="/campaigns"><ArrowLeft /> Back to campaigns</Link>
      </div>
    )
  }

  if (isError) return <ErrorState error={error} onRetry={() => void refetch()} />

  if (isPending || !campaign) return <LoadingState label="Loading campaign details…" />

  const details = [
    { label: 'Objective', value: campaign.objective ?? NO_VALUE },
    { label: 'Budget', value: formatMoney(campaign.budget) },
    { label: 'Start date', value: campaign.start_date ? formatDate(campaign.start_date) : NO_VALUE },
    { label: 'End date', value: campaign.end_date ? formatDate(campaign.end_date) : NO_VALUE },
  ]

  return (
    <>
      {/* Breadcrumb */}
      <div className="breadcrumb">
        <Link href="/campaigns">
          <ArrowLeft />
          Campaigns
        </Link>
        <span>/</span>
        <span>{campaign.name}</span>
      </div>

      {/* Campaign header from API-02 */}
      <div className="card">
        <div className="campaign-heading">
          <h2>{campaign.name}</h2>
          <PlatformBadge platform={campaign.platform} />
          <StatusBadge status={campaign.status} />
        </div>
        <dl className="campaign-facts">
          {details.map((d) => (
            <div key={d.label}>
              <dt>{d.label}</dt>
              <dd>{d.value}</dd>
            </div>
          ))}
        </dl>
        <p className="muted-line">
          Spend, clicks, conversions and ratios for this campaign are in the{' '}
          <Link href="/campaigns">campaign table</Link>.
        </p>
      </div>

      <div className="demo-notice" role="status">
        <strong>Sample content</strong>
        <span>The campaign performance view below arrives with UI-05.</span>
      </div>

      {/* Performance chart placeholder */}
      <div className="card">
        <div className="card-header">
          <LineChart />
          Performance Trend
        </div>
        <div className="chart-placeholder">
          <LineChart />
          Recharts line chart — CPA, ROAS, CTR over time
        </div>
      </div>

      {/* Anomalies for this campaign */}
      {anomalies.length > 0 && (
        <div className="card">
          <div className="card-header">
            <AlertTriangle />
            Anomalies
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {anomalies.map((a) => (
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
                <div>
                  <div style={{ fontSize: 13, fontWeight: 'var(--font-weight-semibold)' }}>
                    {a.metric_name} anomaly ({a.direction})
                  </div>
                  <div style={{ marginTop: 2, fontSize: 12, lineHeight: 1.4, color: 'var(--color-text-muted)' }}>
                    Score: {a.anomaly_score.toFixed(2)} &middot; Severity: {a.severity}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  )
}
