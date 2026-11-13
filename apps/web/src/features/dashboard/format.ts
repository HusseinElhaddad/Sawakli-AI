const integer = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })
const money = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const percent = new Intl.NumberFormat('en-US', { style: 'percent', minimumFractionDigits: 2, maximumFractionDigits: 2 })
const signedPercent = new Intl.NumberFormat('en-US', {
  style: 'percent',
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
  signDisplay: 'exceptZero',
})

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** Placeholder for a ratio whose denominator is 0. */
export const NO_VALUE = '—'

export function formatInteger(value: number): string {
  return integer.format(value)
}

/** Money with 2 decimals and no currency label: API-02 carries no currency (UI-04 gap G5). */
export function formatMoney(value: number | null): string {
  return value === null ? NO_VALUE : money.format(value)
}

/** CTR is a fraction from the API (0.023 = 2.30%). */
export function formatPercent(value: number | null): string {
  return value === null ? NO_VALUE : percent.format(value)
}

export function formatRoas(value: number | null): string {
  return value === null ? NO_VALUE : `${money.format(value)}×`
}

/** Rounds a relative change to the displayed precision (0.1%), so "0.0%" counts as no change. */
export function roundChange(value: number): number {
  const rounded = Math.round(value * 1000) / 1000
  return rounded === 0 ? 0 : rounded
}

export function formatChange(value: number): string {
  return signedPercent.format(value)
}

/** `2026-08-20` → `20 Aug 2026`, without going through a timezone. */
export function formatDate(date: string): string {
  const [year, month, day] = date.split('-').map(Number)
  return `${day} ${MONTHS[month - 1]} ${year}`
}
