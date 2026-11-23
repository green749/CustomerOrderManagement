import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  ClipboardList,
  Cpu,
  CheckSquare,
  Activity,
  Bot,
  BarChart3,
  Settings,
  ChevronLeft,
  ChevronRight,
  LogOut,
  X,
  Shield,
  Layers,
  Plug2,
} from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import gwcFullLogo from '../../assets/gwc-full-logo.webp'
import gwcIcon from '../../assets/gwc-icon.webp'

export const NAVIGATION_ITEMS = [
  { label: 'Home', to: '/architecture', icon: Layers },
  { label: 'Overview', to: '/', icon: LayoutDashboard },
  { label: 'Orders', to: '/orders', icon: ClipboardList },
  { label: 'Assessments', to: '/assessments', icon: Cpu },
  { label: 'My Work', to: '/my-work', icon: CheckSquare },
  { label: 'Monitoring', to: '/monitoring', icon: Activity },
  { label: 'Connectors', to: '/connectors', icon: Plug2 },
  { label: 'Reports', to: '/reports', icon: BarChart3 },
  { label: 'Settings', to: '/settings', icon: Settings },
]

export function Sidebar({ mobileOpen, onClose }) {
  const { user, logout } = useAuth()
  const [collapsed, setCollapsed] = useState(false)

  const userName = user?.full_name || user?.email?.split('@')[0] || 'User'
  const userRole = user?.role ? user.role.toUpperCase() : 'OPERATOR'

  const navItems = [
    ...NAVIGATION_ITEMS,
    ...(user?.role === 'admin' ? [{ label: 'Agent Control', to: '/admin/agents', icon: Shield }] : []),
  ]

  return (
    <>
      {mobileOpen && (
        <button
          type="button"
          className="sidebar-backdrop"
          onClick={onClose}
          aria-label="Close navigation"
        />
      )}

      <aside
        className={`sidebar ${collapsed ? 'sidebar-collapsed' : ''} ${mobileOpen ? 'sidebar-mobile-open' : ''
          }`}
        style={{
          background: 'var(--dr-bg, var(--surface-hi))',
          borderRight: '1px solid var(--dr-border, var(--line))',
        }}
      >
        {/* BRAND LOGO / HEADER */}
        <div
          className="brand-row"
          style={{
            margin: '0 4px 22px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: 'auto',
            minHeight: 48,
          }}
        >
          {collapsed ? (
            <NavLink to="/" style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: '100%' }}>
              <img
                src={gwcIcon}
                alt="GWC DATA.AI"
                style={{
                  width: 36,
                  height: 36,
                  objectFit: 'contain',
                  filter: 'drop-shadow(0 2px 6px rgba(111, 61, 186, 0.25))',
                }}
              />
            </NavLink>
          ) : (
            <div style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center', width: '100%', padding: '4px 0' }}>
              <NavLink to="/" style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto' }}>
                <img
                  src={gwcFullLogo}
                  alt="GWC DATA.AI"
                  style={{
                    height: 52,
                    maxWidth: 180,
                    objectFit: 'contain',
                    filter: 'drop-shadow(0 2px 6px rgba(111, 61, 186, 0.12))',
                  }}
                />
              </NavLink>
              <button
                type="button"
                className="icon-button sidebar-mobile-close"
                onClick={onClose}
                aria-label="Close menu"
                style={{ position: 'absolute', right: 0 }}
              >
                <X size={18} />
              </button>
            </div>
          )}
        </div>

        {/* PRIMARY 8 NAVIGATION ITEMS */}
        <nav className="sidebar-nav" aria-label="Main Navigation" style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {navItems.map((item) => {
            const Icon = item.icon
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                onClick={onClose}
                title={collapsed && !mobileOpen ? item.label : undefined}
                className={({ isActive }) => `nav-link ${isActive ? 'nav-link-active' : ''}`}
                style={({ isActive }) => ({
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  padding: collapsed ? '10px 0' : '10px 14px',
                  justifyContent: collapsed ? 'center' : 'flex-start',
                  borderRadius: 8,
                  fontSize: 13,
                  fontWeight: isActive ? 700 : 500,
                  color: isActive ? 'var(--dr-purple, var(--brand-purple))' : 'var(--text-secondary)',
                  background: isActive ? 'var(--dr-active, var(--brand-purple-soft))' : 'transparent',
                  border: isActive ? '1px solid var(--dr-border, rgba(111, 61, 186, 0.25))' : '1px solid transparent',
                  transition: 'all 0.15s ease',
                  textDecoration: 'none',
                })}
              >
                <Icon
                  size={18}
                  style={{
                    flexShrink: 0,
                    color: 'inherit',
                  }}
                />
                {!collapsed && (
                  <span style={{ flex: 1, display: 'flex', alignItems: 'center' }}>
                    <span>{item.label}</span>
                  </span>
                )}
              </NavLink>
            )
          })}
        </nav>

        {/* FOOTER USER PROFILE SECTION & COLLAPSE */}
        <div
          className="sidebar-bottom"
          style={{
            borderTop: '1px solid var(--line)',
            paddingTop: 14,
            marginTop: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
          }}
        >
          {/* User profile card */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: collapsed ? '4px 0' : '6px 10px',
              borderRadius: 8,
              background: 'var(--surface-hi)',
              border: '1px solid var(--line)',
              justifyContent: collapsed ? 'center' : 'flex-start',
            }}
          >
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: '50%',
                background: 'linear-gradient(135deg, var(--brand-purple) 0%, var(--brand-blue) 100%)',
                color: '#ffffff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 800,
                fontSize: 12,
                flexShrink: 0,
              }}
            >
              {userName.charAt(0).toUpperCase()}
            </div>

            {!collapsed && (
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    color: 'var(--text-primary)',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {userName}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <Shield size={10} color="var(--brand-orange)" />
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 600,
                      color: 'var(--brand-orange)',
                      letterSpacing: '0.04em',
                    }}
                  >
                    {userRole}{user?.department ? ` • ${user.department}` : ''}
                  </span>
                </div>
              </div>
            )}

            {!collapsed && (
              <button
                type="button"
                className="icon-button"
                onClick={logout}
                title="Log out"
                aria-label="Log out"
                style={{ padding: 4, color: 'var(--text-muted)' }}
              >
                <LogOut size={14} />
              </button>
            )}
          </div>

          {/* Collapse menu button */}
          <button
            type="button"
            className="collapse-button"
            onClick={() => setCollapsed((v) => !v)}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: collapsed ? 'center' : 'flex-start',
              gap: 8,
              background: 'transparent',
              border: 'none',
              color: 'var(--text-secondary)',
              cursor: 'pointer',
              padding: '6px 8px',
              borderRadius: 6,
              fontSize: 11,
              fontWeight: 600,
            }}
          >
            {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
            {!collapsed && <span>Collapse Sidebar</span>}
          </button>
        </div>
      </aside>
    </>
  )
}
