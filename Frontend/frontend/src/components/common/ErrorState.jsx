import { AlertCircle, RotateCcw } from 'lucide-react'

export function ErrorState({ title = 'Something went wrong', message, onRetry }) {
  return (
    <div className="error-state" role="alert">
      <span className="error-icon"><AlertCircle size={20} /></span>
      <strong>{title}</strong>
      <p>{message}</p>
      {onRetry && <button className="button button-secondary" onClick={onRetry}><RotateCcw size={14} /> Try again</button>}
    </div>
  )
}
