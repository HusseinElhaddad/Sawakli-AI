import type { LucideIcon } from 'lucide-react'
import { MousePointerClick, Percent, ShoppingCart, Target, TrendingDown, TrendingUp, Wallet, Coins } from 'lucide-react'
import { percentChange } from '../aggregate'
import { formatChange, formatInteger, formatMoney, formatPercent, formatRoas, roundChange } from '../format'
import type { KpiSummary } from '../types'

/** Which direction is good for a KPI. More spend is neither good nor bad. */
type Direction = 'up-good' | 'up-bad' | 'neutral'

type KpiDefinition = {
  key: 'spend' | 'clicks' | 'conversions' | 'ctr' | 'cpa' | 'roas'
  label: string
  icon: LucideIcon
  direction: Direction
  format: (summary: KpiSummary) => string
  /** Shown as a tooltip when the ratio has a zero denominator. */
  emptyHint?: string
}

// The six PROD-01 §2.1 dashboard KPIs. CPC is a supporting field shown only in the table.
const KPIS: readonly KpiDefinition[] = [
  { key: 'spend', label: 'Spend', icon: Wallet, direction: 'neutral', format: (s) => formatMoney(s.spend) },
  { key: 'clicks', label: 'Clicks', icon: MousePointerClick, direction: 'up-good', format: (s) => formatInteger(s.clicks) },
  { key: 'conversions', label: 'Conversions', icon: ShoppingCart, direction: 'up-good', format: (s) => formatInteger(s.conversions) },
  { key: 'ctr', label: 'CTR', icon: Percent, direction: 'up-good', format: (s) => formatPercent(s.ctr), emptyHint: 'No impressions in this range' },
  { key: 'cpa', label: 'CPA', icon: Target, direction: 'up-bad', format: (s) => formatMoney(s.cpa), emptyHint: 'No conversions in this range' },
  { key: 'roas', label: 'ROAS', icon: Coins, direction: 'up-good', format: (s) => formatRoas(s.roas), emptyHint: 'No spend in this range' },
]

function deltaColor(change: number, direction: Direction): string {
  if (direction === 'neutral' || change === 0) return 'var(--color-text-muted)'
  const good = direction === 'up-good' ? change > 0 : change < 0
  return good ? 'var(--color-success)' : 'var(--color-error)'
}

type Props = {
  current: KpiSummary
  previous: KpiSummary | null
  periodDays: number
}

export function KpiCards({ current, previous, periodDays }: Props) {
  return (
    <>
      <div className="kpi-grid kpi-grid-6">
        {KPIS.map((kpi) => {
          const value = current[kpi.key]
          const raw = previous ? percentChange(value, previous[kpi.key]) : null
          const change = raw === null ? null : roundChange(raw)
          return (
            <div key={kpi.key} className="kpi-card" data-testid={`kpi-${kpi.key}`}>
              <div className="kpi-label">
                <kpi.icon aria-hidden="true" className="kpi-icon" />
                {kpi.label}
              </div>
              <div className="kpi-value" title={value === null ? kpi.emptyHint : undefined}>
                {kpi.format(current)}
              </div>
              {change !== null && (
                <div className="kpi-change kpi-delta" style={{ color: deltaColor(change, kpi.direction) }}>
                  {change > 0 ? <TrendingUp aria-hidden="true" /> : change < 0 ? <TrendingDown aria-hidden="true" /> : null}
                  {formatChange(change)} vs previous {periodDays} days
                </div>
              )}
            </div>
          )
        })}
      </div>
      {previous === null && (
        <p className="muted-line">No earlier data to compare with for this range.</p>
      )}
    </>
  )
}
