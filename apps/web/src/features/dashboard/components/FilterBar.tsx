import { PLATFORM_OPTIONS, RANGE_OPTIONS, STATUS_OPTIONS } from '../filters'
import type { DashboardFilters, DatePreset, PlatformFilter, StatusFilter } from '../types'

type Props = {
  filters: DashboardFilters
  onChange: (next: DashboardFilters) => void
}

export function FilterBar({ filters, onChange }: Props) {
  return (
    <div className="filter-bar" role="group" aria-label="Dashboard filters">
      <label className="filter-field">
        <span>Date range</span>
        <select
          className="form-input"
          value={filters.range}
          onChange={(event) => {
            const option = RANGE_OPTIONS.find((o) => o.value === event.target.value)
            if (option) onChange({ ...filters, range: option.value satisfies DatePreset })
          }}
        >
          {RANGE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </label>
      <label className="filter-field">
        <span>Platform</span>
        <select
          className="form-input"
          value={filters.platform}
          onChange={(event) => {
            const option = PLATFORM_OPTIONS.find((o) => o.value === event.target.value)
            if (option) onChange({ ...filters, platform: option.value satisfies PlatformFilter })
          }}
        >
          {PLATFORM_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </label>
      <label className="filter-field">
        <span>Status</span>
        <select
          className="form-input"
          value={filters.status}
          onChange={(event) => {
            const option = STATUS_OPTIONS.find((o) => o.value === event.target.value)
            if (option) onChange({ ...filters, status: option.value satisfies StatusFilter })
          }}
        >
          {STATUS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </label>
    </div>
  )
}
