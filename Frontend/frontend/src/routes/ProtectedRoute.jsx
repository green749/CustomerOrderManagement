import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { PageLoader } from '../components/common/PageLoader'
import { hasAnyRole } from '../utils/permissions'

export function ProtectedRoute({ roles }) {
  const { user, initializing } = useAuth()
  const location = useLocation()
  if (initializing) return <PageLoader />
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />
  if (roles && !hasAnyRole(user, roles)) return <Navigate to="/" replace />
  return <Outlet />
}
