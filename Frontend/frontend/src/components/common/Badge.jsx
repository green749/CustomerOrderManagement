export function Badge({ tone = 'neutral', children, className = '' }) {
  return <span className={`status-badge status-${tone}${className ? ` ${className}` : ''}`}>{children}</span>
}
