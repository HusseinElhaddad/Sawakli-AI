'use client'

import Link from 'next/link'
import { Lightbulb } from 'lucide-react'
import { useRecommendations } from '@/hooks/useRecommendations'
import { getSession } from '@/lib/session'
import type { Recommendation } from '@/types'

function statusBadge(status: string) {
  const map: Record<string, { bg: string; color: string; label: string }> = {
    pending: { bg: 'var(--color-badge-pending-bg)', color: 'var(--color-badge-pending-text)', label: 'Pending' },
    approved: { bg: 'var(--color-success-light)', color: 'var(--color-success)', label: 'Approved' },
    rejected: { bg: 'var(--color-error-light)', color: 'var(--color-error)', label: 'Rejected' },
    marked_done: { bg: 'var(--color-success-light)', color: 'var(--color-success)', label: 'Done' },
    needs_review: { bg: 'var(--color-warning-light)', color: 'var(--color-warning)', label: 'Review' },
  }
  const s = map[status] ?? map.pending
  return (
    <span className="badge" style={{ background: s.bg, color: s.color }}>
      {s.label}
    </span>
  )
}

function riskBadge(risk: string) {
  const map: Record<string, { bg: string; color: string }> = {
    high: { bg: 'var(--color-error-light)', color: 'var(--color-error)' },
    medium: { bg: 'var(--color-warning-light)', color: 'var(--color-warning)' },
    low: { bg: 'var(--color-success-light)', color: 'var(--color-success)' },
  }
  const r = map[risk] ?? map.medium
  return (
    <span className="badge" style={{ ...r, textTransform: 'capitalize' }}>
      {risk}
    </span>
  )
}

export default function RecommendationsPage() {
  const session = getSession()
  const { data: recommendations, isLoading } = useRecommendations(session?.organization.id ?? '')

  return (
    <>
      <div className="card-header" style={{ marginBottom: 20 }}>
        <Lightbulb />
        All Recommendations
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {isLoading && (
          <p style={{ padding: '32px 0', textAlign: 'center', fontSize: 13, color: 'var(--color-text-muted)' }}>
            Loading recommendations...
          </p>
        )}
        {recommendations?.map((r: Recommendation) => (
          <Link
            key={r.id}
            href={`/recommendations/${r.id}`}
            style={{
              display: 'block',
              borderRadius: 'var(--radius-lg)',
              border: '1px solid var(--color-border)',
              padding: 24,
              background: 'var(--color-surface)',
              boxShadow: 'var(--shadow-sm)',
              color: 'inherit',
              transition: 'border-color var(--transition), box-shadow var(--transition)',
            }}
          >
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 14 }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, fontWeight: 'var(--font-weight-medium)', color: 'var(--color-text-secondary)' }}>
                {r.campaign_name}
                {statusBadge(r.status)}
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span className="badge" style={{ background: 'var(--color-accent-light)', color: 'var(--color-accent)' }}>
                  {Math.round(r.confidence_score * 100)}% confidence
                </span>
                {riskBadge(r.risk_rating)}
              </div>
            </div>
            <div style={{ fontSize: 15, fontWeight: 'var(--font-weight-bold)', lineHeight: 1.35, letterSpacing: '-0.01em', marginBottom: 8 }}>
              {r.problem}
            </div>
            <div style={{ fontSize: 13, lineHeight: 1.7, color: 'var(--color-text-muted)' }}>
              {r.suggested_action}
            </div>
          </Link>
        ))}
      </div>
    </>
  )
}
