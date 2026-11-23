import { useState, Suspense } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'
import { PageLoader } from '../common/PageLoader'
import { FloatingChatbot } from '../chat/FloatingChatbot'

export function AppLayout() {
  const [mobileOpen, setMobileOpen] = useState(false)
  return (
    <div className="app-shell">
      <Sidebar mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />
      <div className="app-main">
        <Topbar onMenuClick={() => setMobileOpen(true)} />
        <main className="page-content">
          <Suspense fallback={<PageLoader />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
      <FloatingChatbot />
    </div>
  )
}
