import Link from 'next/link'
import { AlertTriangle, ArrowRight } from 'lucide-react'
import { hrefWithFilters } from '../filters'
import type { CampaignPerformance, DashboardFilters } from '../types'

type Props = {
  rows: readonly CampaignPerformance[]
  filters: DashboardFilters
}

/** Lists weak campaigns; the link opens the table with the same filters, where weak rows sort first. */
export function NeedsAttention({ rows, filters }: Props) {
  const weak = rows.filter((row) => row.flag === 'weak')
  if (weak.length === 0) return null
  return (
    <div className="attention-strip" role="region" aria-label="Campaigns that need attention">
      <div className="attention-title">
        <AlertTriangle aria-hidden="true" />
        Needs attention ({weak.length})
      </div>
      <ul>
        {weak.map((row) => (
          <li key={row.campaign.id}>
            <strong>{row.campaign.name}</strong>
            <span>{row.reason}</span>
          </li>
        ))}
      </ul>
      <Link href={hrefWithFilters('/campaigns', filters)} className="attention-link">
        Review in campaign table <ArrowRight aria-hidden="true" />
      </Link>
    </div>
  )
}
