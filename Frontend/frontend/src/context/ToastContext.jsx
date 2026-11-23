import { createContext, useContext, useState, useCallback, useEffect } from 'react'
import { CheckCircle2, AlertCircle, AlertTriangle, Info, X } from 'lucide-react'

const ToastContext = createContext(null)

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const addToast = useCallback(({ type = 'info', title, message, duration = 4500 }) => {
    const id = Date.now() + Math.random().toString(36).substring(2, 9)
    const newToast = { id, type, title, message, duration }
    setToasts((prev) => [...prev, newToast])

    if (duration > 0) {
      setTimeout(() => {
        removeToast(id)
      }, duration)
    }
    return id
  }, [removeToast])

  const toast = {
    success: (message, options = {}) =>
      addToast({ type: 'success', message, title: options.title || 'Success', duration: options.duration ?? 4500 }),
    error: (message, options = {}) =>
      addToast({ type: 'error', message, title: options.title || 'Error', duration: options.duration ?? 5500 }),
    warning: (message, options = {}) =>
      addToast({ type: 'warning', message, title: options.title || 'Warning', duration: options.duration ?? 4500 }),
    info: (message, options = {}) =>
      addToast({ type: 'info', message, title: options.title || 'Notification', duration: options.duration ?? 4000 }),
    dismiss: removeToast,
  }

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <ToastContainer toasts={toasts} onDismiss={removeToast} />
    </ToastContext.Provider>
  )
}

export function useToast() {
  const context = useContext(ToastContext)
  if (!context) {
    // Graceful fallback if invoked outside provider
    return {
      toast: {
        success: (msg) => console.log('[Toast Success]', msg),
        error: (msg) => console.error('[Toast Error]', msg),
        warning: (msg) => console.warn('[Toast Warning]', msg),
        info: (msg) => console.info('[Toast Info]', msg),
        dismiss: () => {},
      },
    }
  }
  return context
}

function ToastContainer({ toasts, onDismiss }) {
  if (toasts.length === 0) return null

  return (
    <aside
      aria-label="Notifications"
      style={{
        position: 'fixed',
        top: 24,
        right: 24,
        zIndex: 999999,
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        maxWidth: 420,
        width: 'calc(100vw - 48px)',
        pointerEvents: 'none',
      }}
    >
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onDismiss={() => onDismiss(t.id)} />
      ))}
    </aside>
  )
}

function ToastItem({ toast, onDismiss }) {
  const [closing, setClosing] = useState(false)

  const handleClose = () => {
    setClosing(true)
    setTimeout(() => {
      onDismiss()
    }, 200)
  }

  const config = {
    success: {
      icon: CheckCircle2,
      iconColor: '#22C55E',
      borderColor: 'rgba(34, 197, 94, 0.4)',
      glowColor: 'rgba(34, 197, 94, 0.15)',
      badgeBg: 'rgba(34, 197, 94, 0.12)',
      badgeColor: '#16A34A',
    },
    error: {
      icon: AlertCircle,
      iconColor: '#EF4444',
      borderColor: 'rgba(239, 68, 68, 0.4)',
      glowColor: 'rgba(239, 68, 68, 0.15)',
      badgeBg: 'rgba(239, 68, 68, 0.12)',
      badgeColor: '#DC2626',
    },
    warning: {
      icon: AlertTriangle,
      iconColor: '#F59E0B',
      borderColor: 'rgba(245, 158, 11, 0.4)',
      glowColor: 'rgba(245, 158, 11, 0.15)',
      badgeBg: 'rgba(245, 158, 11, 0.12)',
      badgeColor: '#D97706',
    },
    info: {
      icon: Info,
      iconColor: 'var(--brand-purple)',
      borderColor: 'rgba(111, 61, 186, 0.4)',
      glowColor: 'rgba(111, 61, 186, 0.15)',
      badgeBg: 'rgba(111, 61, 186, 0.12)',
      badgeColor: 'var(--brand-purple)',
    },
  }[toast.type] || {
    icon: Info,
    iconColor: 'var(--brand-purple)',
    borderColor: 'var(--mfg-border-default)',
    glowColor: 'transparent',
    badgeBg: 'var(--mfg-bg-surface)',
    badgeColor: 'var(--mfg-text-primary)',
  }

  const IconComponent = config.icon

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        pointerEvents: 'auto',
        display: 'flex',
        alignItems: 'flex-start',
        gap: 12,
        padding: '14px 16px',
        borderRadius: 12,
        background: 'var(--mfg-bg-card)',
        color: 'var(--mfg-text-primary)',
        border: `1px solid ${config.borderColor}`,
        boxShadow: `0 10px 25px -5px rgba(0,0,0,0.25), 0 0 15px ${config.glowColor}`,
        backdropFilter: 'blur(8px)',
        transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
        opacity: closing ? 0 : 1,
        transform: closing ? 'translateY(-10px) scale(0.96)' : 'translateY(0) scale(1)',
        animation: 'toastSlideIn 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
      }}
    >
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: config.badgeBg,
          flexShrink: 0,
          marginTop: 2,
        }}
      >
        <IconComponent size={18} color={config.iconColor} />
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        {toast.title && (
          <div
            style={{
              fontSize: 14,
              fontWeight: 700,
              color: 'var(--mfg-text-primary)',
              marginBottom: 2,
              lineHeight: 1.3,
            }}
          >
            {toast.title}
          </div>
        )}
        <div
          style={{
            fontSize: 12.5,
            color: 'var(--mfg-text-secondary)',
            lineHeight: 1.45,
            wordBreak: 'break-word',
          }}
        >
          {toast.message}
        </div>
      </div>

      <button
        type="button"
        onClick={handleClose}
        aria-label="Close notification"
        style={{
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
          padding: 4,
          borderRadius: 6,
          color: 'var(--mfg-text-muted)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          transition: 'color 0.15s ease',
        }}
        onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--mfg-text-primary)')}
        onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--mfg-text-muted)')}
      >
        <X size={15} />
      </button>
    </div>
  )
}
