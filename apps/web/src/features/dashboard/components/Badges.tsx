import type { CampaignPlatform, CampaignStatus } from '@/types'
import type { PerformanceFlag } from '../types'

type Tone = { background: string; color: string; boxShadow?: string }

const PLATFORM: Record<CampaignPlatform, { label: string } & Tone> = {
  google: { label: 'Google', background: 'var(--color-badge-google-bg)', color: 'var(--color-badge-google-text)' },
  meta: { label: 'Meta', background: 'var(--color-accent-light)', color: 'var(--color-accent)' },
}

const STATUS: Record<CampaignStatus, { label: string } & Tone> = {
  active: { label: 'Active', background: 'var(--color-success-light)', color: 'var(--color-success)' },
  paused: { label: 'Paused', background: 'var(--color-warning-light)', color: 'var(--color-warning)' },
  removed: { label: 'Removed', background: 'var(--color-surface-raised)', color: 'var(--color-text-muted)' },
  unknown: { label: 'Unknown', background: 'var(--color-surface-raised)', color: 'var(--color-text-faint)' },
}

const PERFORMANCE: Record<PerformanceFlag, { label: string } & Tone> = {
  weak: { label: 'Weak', background: 'var(--color-surface)', color: 'var(--color-error)', boxShadow: 'inset 0 0 0 1px var(--color-error-border)' },
  average: { label: 'Average', background: 'var(--color-warning-light)', color: 'var(--color-warning)' },
  strong: { label: 'Strong', background: 'var(--color-success-light)', color: 'var(--color-success)' },
  no_data: { label: 'No data', background: 'var(--color-surface-raised)', color: 'var(--color-text-muted)' },
}

export function PlatformBadge({ platform }: { platform: CampaignPlatform }) {
  const { label, ...tone } = PLATFORM[platform]
  return <span className="badge" style={tone}>{label}</span>
}

/** A null API status is shown as Unknown. */
export function StatusBadge({ status }: { status: CampaignStatus | null }) {
  const { label, ...tone } = STATUS[status ?? 'unknown']
  return <span className="badge" style={tone}>{label}</span>
}

/** The text label carries the meaning, so the flag never depends on colour alone. */
export function PerformanceBadge({ flag, reason }: { flag: PerformanceFlag; reason?: string | null }) {
  const { label, ...tone } = PERFORMANCE[flag]
  return (
    <>
      <span className="badge" style={tone} title={reason ?? undefined}>
        {label}
      </span>
      {reason && <span className="sr-only">: {reason}</span>}
    </>
  )
}
