import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'

export function Modal({ open, onClose, title, children, labelledBy = 'modal-title' }) {
  useEffect(() => {
    if (!open) return undefined
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [open, onClose])

  if (!open) return null
  return createPortal(
    <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
      <section className="modal-panel" role="dialog" aria-modal="true" aria-labelledby={labelledBy}>
        <header className="modal-header"><h2 id={labelledBy}>{title}</h2><button className="icon-button" onClick={onClose} aria-label="Close dialog"><X size={17} /></button></header>
        <div className="modal-body">{children}</div>
      </section>
    </div>,
    document.body,
  )
}
