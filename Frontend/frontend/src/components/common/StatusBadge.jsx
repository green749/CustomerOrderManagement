import { Badge } from './Badge'

const statusClass = (status = '') => {
  const value = status.toLowerCase()
  if (value.includes('deliver') || value.includes('release') || value.includes('pass')) return 'green'
  if (value.includes('transit')) return 'blue'
  if (value.includes('risk') || value.includes('cancel') || value.includes('hold') || value.includes('scrap')) return 'red'
  if (value.includes('process') || value.includes('production') || value.includes('open') || value.includes('approv') || value.includes('pending')) return 'amber'
  return 'neutral'
}

export function StatusBadge({ children }) {
  return <Badge tone={statusClass(String(children ?? ''))}>{children || 'Unavailable'}</Badge>
}

export function RiskBadge({ risk }) {
  const rawValue = String(risk ?? 'Unavailable')
  const value = ['high', 'medium', 'low', 'critical'].includes(rawValue.toLowerCase())
    ? `${rawValue.charAt(0).toUpperCase()}${rawValue.slice(1).toLowerCase()}`
    : rawValue
  const className = value === 'Critical'
    ? 'risk-badge risk-critical'
    : value === 'High'
    ? 'risk-badge risk-high'
    : value === 'Medium'
      ? 'risk-badge risk-medium'
      : value === 'Low'
        ? 'risk-badge risk-low'
        : 'risk-badge risk-unavailable'
  return <span className={className}><span />{value}</span>
}
