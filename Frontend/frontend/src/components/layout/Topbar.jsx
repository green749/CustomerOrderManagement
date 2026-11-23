import { useEffect, useState } from 'react'
import { Menu, Sun, Moon } from 'lucide-react'
import { useLocation } from 'react-router-dom'

const pageTitles = {
  '/': 'Overview',
  '/orders': 'Orders',
  '/assessments': 'Assessments · Agent 2',
  '/my-work': 'My Work Queue',
  '/monitoring': 'Monitoring · Agent 3',
  '/monitoring/orders': 'Monitoring · Monitored Orders',
  '/monitoring/outbox': 'Notification Outbox',
  '/architecture': 'System Architecture',
  '/framework': 'System Framework & Flow',
  '/architecture-diagram': 'System Architecture',
  '/assistant': 'AI Assistant · Agent 1',
  '/reports': 'Reports & Analytics',
  '/settings': 'Settings & Team',
  // Backward compatibility aliases
  '/alerts': 'Monitoring · Agent 3',
  '/outbox': 'Notification Outbox',
  '/allocation': 'Assessments · Agent 2',
  '/approvals': 'My Work Queue',
  '/kpis': 'Reports & Analytics',
}

export function Topbar({ onMenuClick }) {
  const { pathname } = useLocation()
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'light')

  const title = pathname.startsWith('/orders/')
    ? 'Order Details'
    : pageTitles[pathname] || 'Command Center'

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('theme', theme)
  }, [theme])

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'))
  }

  return (
    <header
      className="topbar"
      style={{
        background: 'var(--dr-surface, var(--surface-hi))',
        borderBottom: '1px solid var(--dr-border, var(--line))',
        padding: '0 24px',
        height: 60,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        position: 'sticky',
        top: 0,
        zIndex: 15,
        transition: 'background 0.2s ease, border-color 0.2s ease',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <button
          type="button"
          className="icon-button mobile-menu-button"
          onClick={onMenuClick}
          aria-label="Open navigation"
        >
          <Menu size={20} />
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
          <span style={{ color: 'var(--text-muted)', fontWeight: 500 }}>Manufacturing 360</span>
          <span style={{ color: 'var(--line)' }}>/</span>
          <strong style={{ color: 'var(--text-primary)', fontWeight: 700 }}>{title}</strong>
        </div>
      </div>

      {/* CENTER USECASE HEADING */}
      <div
        className="topbar-usecase"
        style={{
          position: 'absolute',
          left: '50%',
          top: '50%',
          transform: 'translate(-50%, -50%)',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          pointerEvents: 'none',
        }}
      >
        <span
          style={{
            fontSize: 16,
            fontWeight: 700,
            letterSpacing: '-0.01em',
            color: 'var(--text-primary)',
            fontFamily: "'Montserrat', sans-serif",
            whiteSpace: 'nowrap',
          }}
        >
          Customer Order Management
        </span>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        {/* LIGHT / DARK THEME TOGGLE BUTTON */}
        <button
          type="button"
          onClick={toggleTheme}
          title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} theme`}
          style={{
            background: 'var(--kg-bg-2, var(--surface-hi))',
            border: '1px solid var(--line)',
            borderRadius: 8,
            padding: '6px 10px',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            color: 'var(--text-primary)',
            cursor: 'pointer',
            fontSize: 12,
            fontWeight: 600,
            transition: 'all 0.15s ease',
          }}
        >
          {theme === 'dark' ? (
            <>
              <Sun size={15} style={{ color: 'var(--brand-orange)' }} />
              <span>Light</span>
            </>
          ) : (
            <>
              <Moon size={15} style={{ color: 'var(--brand-purple)' }} />
              <span>Dark</span>
            </>
          )}
        </button>
      </div>
    </header>
  )
}
