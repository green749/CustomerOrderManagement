import { lazy, Suspense } from 'react'
import { Route, Routes, Navigate } from 'react-router-dom'
import { ProtectedRoute } from './routes/ProtectedRoute'
import { AppLayout } from './components/layout/AppLayout'
import { PageLoader } from './components/common/PageLoader'

const Login = lazy(() => import('./pages/Login'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Orders = lazy(() => import('./pages/Orders'))
const CreateOrder = lazy(() => import('./pages/CreateOrder'))
const OrderDetails = lazy(() => import('./pages/OrderDetails'))
const CustomerDetails = lazy(() => import('./pages/CustomerDetails'))
const Assessments = lazy(() => import('./pages/Assessments'))
const MyWork = lazy(() => import('./pages/MyWork'))
const Monitoring = lazy(() => import('./pages/Monitoring'))
const MonitoringOrders = lazy(() => import('./pages/MonitoringOrders'))
const NotificationOutbox = lazy(() => import('./pages/NotificationOutbox'))
const Assistant = lazy(() => import('./pages/Assistant'))
const Architecture = lazy(() => import('./pages/ArchitectureDiagram'))
const Framework = lazy(() => import('./pages/Architecture'))
const Connectors = lazy(() => import('./pages/Connectors'))
const Reports = lazy(() => import('./pages/Reports'))
const Settings = lazy(() => import('./pages/Settings'))
const AgentControl = lazy(() => import('./pages/AgentControl'))
const Inventory = lazy(() => import('./pages/Inventory'))
const NotFound = lazy(() => import('./pages/NotFound'))

export default function App() {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            {/* PRIMARY MANUFACTURING 360 NAVIGATION */}
            <Route index element={<Dashboard />} />
            <Route path="orders" element={<Orders />} />
            <Route path="orders/new" element={<CreateOrder />} />
            <Route path="orders/:orderId" element={<OrderDetails />} />
            <Route path="customers/:customerId" element={<CustomerDetails />} />
            <Route path="assessments" element={<Assessments />} />
            <Route path="my-work" element={<MyWork />} />
            <Route path="monitoring" element={<Monitoring />} />
            <Route path="monitoring/orders" element={<MonitoringOrders />} />
            <Route path="monitoring/outbox" element={<NotificationOutbox />} />
            <Route path="architecture" element={<Architecture />} />
            <Route path="framework" element={<Navigate to="/architecture" replace />} />
            <Route path="architecture-diagram" element={<Navigate to="/architecture" replace />} />
            <Route path="assistant" element={<Assistant />} />
            <Route path="connectors" element={<Connectors />} />
            <Route path="reports" element={<Reports />} />
            <Route path="settings" element={<Settings />} />
            <Route path="admin/agents" element={<AgentControl />} />

            {/* RAW INVENTORY */}
            <Route path="inventory" element={<Inventory />} />

            {/* BACKWARD-COMPATIBILITY ALIASES */}
            <Route path="allocation" element={<Navigate to="/assessments" replace />} />
            <Route path="approvals" element={<Navigate to="/my-work" replace />} />
            <Route path="alerts" element={<Navigate to="/monitoring" replace />} />
            <Route path="outbox" element={<Navigate to="/monitoring/outbox" replace />} />
            <Route path="kpis" element={<Navigate to="/reports" replace />} />
          </Route>
        </Route>
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  )
}
