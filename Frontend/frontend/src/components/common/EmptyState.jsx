import { Inbox } from 'lucide-react'

export function EmptyState({ title = 'Nothing here yet', description }) {
  return (
    <div className="empty-state">
      <span className="empty-icon"><Inbox size={20} /></span>
      <strong>{title}</strong>
      {description && <p>{description}</p>}
    </div>
  )
}
