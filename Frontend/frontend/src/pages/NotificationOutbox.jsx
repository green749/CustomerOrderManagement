import { useState, useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Mail,
  Send,
  RotateCcw,
  ArrowLeft,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Search,
  Filter,
  ExternalLink,
  Info,
  Building2,
  UserCheck,
  Check,
  X,
  RefreshCw,
} from 'lucide-react'
import { agentsApi } from '../api/agents.api'
import { useToast } from '../context/ToastContext'

export default function NotificationOutbox() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const [searchQuery, setSearchQuery] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('ALL') // ALL, CUSTOMER_SERVICE, OPERATIONAL
  const [statusFilter, setStatusFilter] = useState('ALL') // ALL, SENT, FAILED, PENDING_CONFIG
  const [selectedEmail, setSelectedEmail] = useState(null)
  const [retryingId, setRetryingId] = useState(null)
  const [testSending, setTestSending] = useState(false)
  const [showTestModal, setShowTestModal] = useState(false)
  const [testEmailInput, setTestEmailInput] = useState('')
  const [testCategoryInput, setTestCategoryInput] = useState('CUSTOMER_SERVICE')

  // Fetch notifications
  const {
    data: notifications = [],
    isLoading,
    isRefetching,
    refetch,
  } = useQuery({
    queryKey: ['notificationOutbox'],
    queryFn: async () => {
      const res = await agentsApi.listNotifications({ limit: 150 })
      return Array.isArray(res) ? res : []
    },
    refetchInterval: 15000,
  })

  // Filtered notifications
  const filteredNotifications = useMemo(() => {
    return notifications.filter((n) => {
      // Category filter
      if (categoryFilter !== 'ALL') {
        if ((n.recipient_category || 'OPERATIONAL').toUpperCase() !== categoryFilter) {
          return false
        }
      }

      // Status filter
      if (statusFilter !== 'ALL') {
        if ((n.status || '').toUpperCase() !== statusFilter) {
          return false
        }
      }

      // Search filter
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim()
        const matchOrder = (n.customer_order_id || '').toLowerCase().includes(q)
        const matchEmail = (n.recipient_email || '').toLowerCase().includes(q)
        const matchSubject = (n.subject || '').toLowerCase().includes(q)
        const matchDept = (n.department || '').toLowerCase().includes(q)
        if (!matchOrder && !matchEmail && !matchSubject && !matchDept) {
          return false
        }
      }

      return true
    })
  }, [notifications, categoryFilter, statusFilter, searchQuery])

  // Aggregate metrics
  const metrics = useMemo(() => {
    const total = notifications.length
    const sent = notifications.filter((n) => n.status === 'SENT').length
    const failed = notifications.filter((n) => n.status === 'FAILED').length
    const customer = notifications.filter((n) => (n.recipient_category || '').toUpperCase() === 'CUSTOMER').length
    const cs = notifications.filter((n) => (n.recipient_category || '').toUpperCase() === 'CUSTOMER_SERVICE').length
    const operational = notifications.filter((n) => (n.recipient_category || '').toUpperCase() === 'OPERATIONAL').length
    return { total, sent, failed, customer, cs, operational }
  }, [notifications])

  // Handle single notification retry
  const handleRetry = async (logId) => {
    setRetryingId(logId)
    try {
      await agentsApi.retryNotification(logId)
      toast({
        title: 'Notification Retried',
        description: `Notification #${logId} was re-dispatched successfully.`,
        type: 'success',
      })
      refetch()
    } catch (err) {
      toast({
        title: 'Retry Failed',
        description: err.response?.data?.detail || err.message,
        type: 'error',
      })
    } finally {
      setRetryingId(null)
    }
  }

  // Handle batch retry
  const handleRetryAllFailed = async () => {
    try {
      const res = await agentsApi.retryAllFailedNotifications()
      toast({
        title: 'Batch Retry Triggered',
        description: res?.message || 'Retried all failed notifications.',
        type: 'success',
      })
      refetch()
    } catch (err) {
      toast({
        title: 'Batch Retry Error',
        description: err.response?.data?.detail || err.message,
        type: 'error',
      })
    }
  }

  // Handle send test notification
  const handleSendTest = async (e) => {
    e.preventDefault()
    setTestSending(true)
    try {
      const res = await agentsApi.sendTestNotification({
        recipient_email: testEmailInput.trim(),
        recipient_category: testCategoryInput,
      })
      toast({
        title: 'Test Notification Dispatched',
        description: `Sent test alert to ${testEmailInput} (Status: ${res.status}).`,
        type: 'success',
      })
      setShowTestModal(false)
      refetch()
    } catch (err) {
      toast({
        title: 'Test Notification Failed',
        description: err.response?.data?.detail || err.message,
        type: 'error',
      })
    } finally {
      setTestSending(false)
    }
  }

  return (
    <div className="page-stack">
      {/* NAVIGATION BREADCRUMB & BACK BUTTON */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
        <button
          type="button"
          onClick={() => navigate('/monitoring')}
          className="button button-secondary"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            padding: '7px 14px',
            fontSize: 12,
            fontWeight: 600,
            borderRadius: 8,
            background: 'var(--surface-hi)',
            border: '1px solid var(--line)',
            color: 'var(--text-primary)',
          }}
        >
          <ArrowLeft size={14} /> Back to Monitoring
        </button>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button
            type="button"
            className="button button-secondary"
            onClick={() => setShowTestModal(true)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 12,
              padding: '7px 14px',
              borderRadius: 8,
              border: '1px solid var(--line)',
              background: 'var(--surface-hi)',
              color: 'var(--text-primary)',
              fontWeight: 600,
            }}
          >
            <Send size={13} style={{ color: 'var(--brand-purple)' }} /> Send Test Notification
          </button>

          {metrics.failed > 0 && (
            <button
              type="button"
              className="button button-secondary"
              onClick={handleRetryAllFailed}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                fontSize: 12,
                padding: '7px 14px',
                borderRadius: 8,
                border: '1px solid rgba(239, 68, 68, 0.3)',
                background: 'rgba(239, 68, 68, 0.08)',
                color: '#dc2626',
                fontWeight: 600,
              }}
            >
              <RotateCcw size={13} /> Retry All Failed ({metrics.failed})
            </button>
          )}

          <button
            type="button"
            className="button button-secondary"
            onClick={() => refetch()}
            disabled={isRefetching}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 12,
              padding: '7px 14px',
              borderRadius: 8,
              border: '1px solid var(--line)',
              background: 'var(--surface-hi)',
              color: 'var(--text-primary)',
              fontWeight: 600,
            }}
          >
            <RefreshCw size={13} className={isRefetching ? 'spin' : ''} />
            {isRefetching ? 'Refreshing…' : 'Refresh Outbox'}
          </button>
        </div>
      </div>

      {/* METRIC CARDS */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 14 }}>
        <div className="card" style={{ padding: '16px 20px', background: 'var(--surface-hi)', border: '1px solid var(--line)', borderRadius: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Total Outbox Records
          </div>
          <div style={{ fontSize: 26, fontWeight: 800, color: 'var(--text-primary)', marginTop: 4 }}>
            {metrics.total}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
            Cumulative surveillance dispatches
          </div>
        </div>

        <div className="card" style={{ padding: '16px 20px', background: 'var(--surface-hi)', border: '1px solid var(--line)', borderRadius: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Successful Deliveries
          </div>
          <div style={{ fontSize: 26, fontWeight: 800, color: '#16a34a', marginTop: 4 }}>
            {metrics.sent}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
            {metrics.total > 0 ? Math.round((metrics.sent / metrics.total) * 100) : 100}% verified delivery rate
          </div>
        </div>

        <div className="card" style={{ padding: '16px 20px', background: 'var(--surface-hi)', border: '1px solid var(--line)', borderRadius: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Customer Confirmations
          </div>
          <div style={{ fontSize: 26, fontWeight: 800, color: '#2563eb', marginTop: 4 }}>
            {metrics.customer}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
            Direct promised delivery notices
          </div>
        </div>

        <div className="card" style={{ padding: '16px 20px', background: 'var(--surface-hi)', border: '1px solid var(--line)', borderRadius: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Customer Service
          </div>
          <div style={{ fontSize: 26, fontWeight: 800, color: 'var(--brand-purple)', marginTop: 4 }}>
            {metrics.cs}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
            Commercial breach alerts
          </div>
        </div>

        <div className="card" style={{ padding: '16px 20px', background: 'var(--surface-hi)', border: '1px solid var(--line)', borderRadius: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Plant Operational
          </div>
          <div style={{ fontSize: 26, fontWeight: 800, color: '#ea580c', marginTop: 4 }}>
            {metrics.operational}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
            Departmental corrective actions
          </div>
        </div>
      </div>

      {/* FILTER & SEARCH TOOLBAR */}
      <div className="card" style={{ padding: 16, background: 'var(--surface-hi)', border: '1px solid var(--line)', borderRadius: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          {/* SEARCH INPUT */}
          <div style={{ position: 'relative', flex: '1 1 280px', maxWidth: 420 }}>
            <Search size={14} style={{ position: 'absolute', left: 12, top: 11, color: 'var(--text-muted)' }} />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by Order ID, recipient email, or subject…"
              style={{
                width: '100%',
                padding: '9px 12px 9px 34px',
                background: 'var(--surface-hi)',
                border: '1px solid var(--line)',
                borderRadius: 8,
                color: 'var(--text-primary)',
                fontSize: 12,
                outline: 'none',
              }}
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                style={{
                  position: 'absolute',
                  right: 10,
                  top: 9,
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                  padding: 2,
                }}
              >
                <X size={14} />
              </button>
            )}
          </div>

          {/* FILTER CONTROLS */}
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
            {/* CATEGORY TABS */}
            <div style={{ display: 'flex', background: 'var(--kg-bg-2)', padding: 3, borderRadius: 8, border: '1px solid var(--line)', gap: 2 }}>
              <button
                type="button"
                onClick={() => setCategoryFilter('ALL')}
                style={{
                  padding: '5px 12px',
                  borderRadius: 6,
                  border: 'none',
                  fontSize: 11,
                  fontWeight: 600,
                  cursor: 'pointer',
                  background: categoryFilter === 'ALL' ? 'var(--brand-purple)' : 'transparent',
                  color: categoryFilter === 'ALL' ? 'white' : 'var(--text-secondary)',
                  transition: 'all 0.15s ease',
                }}
              >
                All Recipients ({metrics.total})
              </button>
              <button
                type="button"
                onClick={() => setCategoryFilter('CUSTOMER')}
                style={{
                  padding: '5px 12px',
                  borderRadius: 6,
                  border: 'none',
                  fontSize: 11,
                  fontWeight: 600,
                  cursor: 'pointer',
                  background: categoryFilter === 'CUSTOMER' ? '#2563eb' : 'transparent',
                  color: categoryFilter === 'CUSTOMER' ? 'white' : 'var(--text-secondary)',
                  transition: 'all 0.15s ease',
                }}
              >
                Customer Direct ({metrics.customer})
              </button>
              <button
                type="button"
                onClick={() => setCategoryFilter('CUSTOMER_SERVICE')}
                style={{
                  padding: '5px 12px',
                  borderRadius: 6,
                  border: 'none',
                  fontSize: 11,
                  fontWeight: 600,
                  cursor: 'pointer',
                  background: categoryFilter === 'CUSTOMER_SERVICE' ? 'var(--brand-purple)' : 'transparent',
                  color: categoryFilter === 'CUSTOMER_SERVICE' ? 'white' : 'var(--text-secondary)',
                  transition: 'all 0.15s ease',
                }}
              >
                Customer Service ({metrics.cs})
              </button>
              <button
                type="button"
                onClick={() => setCategoryFilter('OPERATIONAL')}
                style={{
                  padding: '5px 12px',
                  borderRadius: 6,
                  border: 'none',
                  fontSize: 11,
                  fontWeight: 600,
                  cursor: 'pointer',
                  background: categoryFilter === 'OPERATIONAL' ? 'var(--brand-purple)' : 'transparent',
                  color: categoryFilter === 'OPERATIONAL' ? 'white' : 'var(--text-secondary)',
                  transition: 'all 0.15s ease',
                }}
              >
                Operational Plant ({metrics.operational})
              </button>
            </div>

            {/* STATUS SELECT */}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{
                padding: '7px 12px',
                borderRadius: 8,
                border: '1px solid var(--line)',
                background: 'var(--surface-hi)',
                color: 'var(--text-primary)',
                fontSize: 12,
                fontWeight: 600,
                outline: 'none',
                cursor: 'pointer',
              }}
            >
              <option value="ALL">All Delivery Statuses</option>
              <option value="SENT">Sent &amp; Verified</option>
              <option value="FAILED">Failed / Undelivered</option>
              <option value="PENDING_CONFIG">Pending Config</option>
            </select>
          </div>
        </div>
      </div>

      {/* NOTIFICATION RECORDS LIST */}
      <div className="card" style={{ padding: 20, background: 'var(--surface-hi)', border: '1px solid var(--line)', borderRadius: 14 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
            Showing {filteredNotifications.length} of {notifications.length} notification logs
          </div>
          {(categoryFilter !== 'ALL' || statusFilter !== 'ALL' || searchQuery) && (
            <button
              type="button"
              className="button button-secondary"
              onClick={() => {
                setCategoryFilter('ALL')
                setStatusFilter('ALL')
                setSearchQuery('')
              }}
              style={{ fontSize: 11, padding: '4px 10px', display: 'flex', alignItems: 'center', gap: 4 }}
            >
              <RotateCcw size={11} /> Clear Filters
            </button>
          )}
        </div>

        {isLoading ? (
          <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)' }}>
            Loading notification outbox logs…
          </div>
        ) : filteredNotifications.length === 0 ? (
          <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-secondary)' }}>
            <Mail size={32} style={{ color: 'var(--text-muted)', marginBottom: 8, opacity: 0.6 }} />
            <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>No notifications match your current filter</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
              Try adjusting your search query, recipient category, or status filter.
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {filteredNotifications.map((n) => {
              const cat = (n.recipient_category || 'OPERATIONAL').toUpperCase()
              const isCustomer = cat === 'CUSTOMER'
              const isCS = cat === 'CUSTOMER_SERVICE'
              const formattedDate = n.sent_at || n.created_at ? new Date(n.sent_at || n.created_at).toLocaleString() : 'N/A'
              return (
                <div
                  key={n.id}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    background: 'var(--kg-bg-2)',
                    border: '1px solid var(--line)',
                    padding: '14px 18px',
                    borderRadius: 10,
                    fontSize: 12,
                    flexWrap: 'wrap',
                    gap: 12,
                    transition: 'border-color 0.15s ease, box-shadow 0.15s ease',
                  }}
                >
                  {/* LEFT: CATEGORY, RECIPIENT, ORDER, SUBJECT */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', flex: '1 1 500px' }}>
                    <span
                      style={{
                        background: isCustomer
                          ? 'rgba(37, 99, 235, 0.12)'
                          : isCS
                          ? 'rgba(111, 61, 186, 0.12)'
                          : 'rgba(245, 138, 58, 0.12)',
                        color: isCustomer
                          ? '#2563eb'
                          : isCS
                          ? 'var(--brand-purple)'
                          : '#ea580c',
                        fontWeight: 700,
                        fontSize: 10,
                        padding: '3px 8px',
                        borderRadius: 6,
                        border: isCustomer
                          ? '1px solid rgba(37, 99, 235, 0.25)'
                          : isCS
                          ? '1px solid rgba(111, 61, 186, 0.25)'
                          : '1px solid rgba(245, 138, 58, 0.25)',
                        letterSpacing: '0.02em',
                      }}
                    >
                      {isCustomer ? 'CUSTOMER · DIRECT' : isCS ? 'CUSTOMER SERVICE' : `OPERATIONAL · ${n.department || 'PLANT'}`}
                    </span>

                    {n.customer_order_id && (
                      <Link
                        to={`/orders/${encodeURIComponent(n.customer_order_id)}`}
                        style={{
                          textDecoration: 'none',
                          color: 'var(--brand-purple)',
                          fontFamily: 'monospace',
                          fontWeight: 700,
                          fontSize: 11,
                          background: 'rgba(111, 61, 186, 0.08)',
                          padding: '2px 6px',
                          borderRadius: 4,
                          border: '1px solid rgba(111, 61, 186, 0.2)',
                        }}
                        title={`View Order ${n.customer_order_id}`}
                      >
                        {n.customer_order_id}
                      </Link>
                    )}

                    <span style={{ fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'monospace' }}>
                      {n.recipient_email}
                    </span>

                    <span style={{ color: 'var(--text-secondary)' }}>• {n.subject}</span>
                  </div>

                  {/* RIGHT: TIMESTAMP, STATUS BADGE, ACTION BUTTONS */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                      {formattedDate}
                    </span>

                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 700,
                        padding: '3px 9px',
                        borderRadius: 12,
                        background: n.status === 'SENT' ? 'rgba(34, 197, 94, 0.12)' : n.status === 'FAILED' ? 'rgba(239, 68, 68, 0.12)' : 'rgba(234, 179, 8, 0.12)',
                        color: n.status === 'SENT' ? '#16a34a' : n.status === 'FAILED' ? '#dc2626' : '#ca8a04',
                        border: n.status === 'SENT' ? '1px solid rgba(34, 197, 94, 0.25)' : n.status === 'FAILED' ? '1px solid rgba(239, 68, 68, 0.25)' : '1px solid rgba(234, 179, 8, 0.25)',
                      }}
                    >
                      {n.status}
                    </span>

                    <button
                      type="button"
                      className="button button-secondary"
                      onClick={() => setSelectedEmail(n)}
                      style={{
                        fontSize: 11,
                        padding: '5px 12px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 5,
                        fontWeight: 600,
                      }}
                      title="Inspect full email message headers and formatted body"
                    >
                      <Mail size={12} /> View Email
                    </button>

                    {(n.status === 'FAILED' || n.status === 'PENDING_CONFIG') && (
                      <button
                        type="button"
                        className="button button-secondary"
                        onClick={() => handleRetry(n.id)}
                        disabled={retryingId === n.id}
                        style={{
                          fontSize: 11,
                          padding: '5px 10px',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 4,
                          color: '#dc2626',
                          borderColor: 'rgba(239, 68, 68, 0.3)',
                          fontWeight: 600,
                        }}
                      >
                        <RotateCcw size={11} className={retryingId === n.id ? 'spin' : ''} />
                        {retryingId === n.id ? 'Retrying…' : 'Retry'}
                      </button>
                    )}
                  </div>

                  {n.failure_reason && (
                    <div style={{
                      width: '100%',
                      fontSize: 11,
                      color: '#dc2626',
                      background: 'rgba(239, 68, 68, 0.06)',
                      padding: '8px 12px',
                      borderRadius: 6,
                      border: '1px solid rgba(239, 68, 68, 0.15)',
                      marginTop: 2,
                    }}>
                      <strong>Delivery Notice:</strong> {n.failure_reason}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* EMAIL PREVIEW INSPECTION MODAL */}
      {selectedEmail && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
            padding: 20,
          }}
        >
          <div
            className="card"
            style={{
              background: 'var(--surface-hi)',
              border: '1px solid var(--line)',
              borderRadius: 14,
              maxWidth: 720,
              width: '100%',
              maxHeight: '85vh',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '0 12px 48px rgba(0,0,0,0.25)',
            }}
          >
            {/* MODAL HEADER */}
            <div
              style={{
                padding: '16px 20px',
                borderBottom: '1px solid var(--line)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Mail size={18} style={{ color: 'var(--brand-purple)' }} />
                <strong style={{ fontSize: 15, color: 'var(--text-primary)' }}>
                  Email Notification Inspection #{selectedEmail.id}
                </strong>
              </div>
              <button
                type="button"
                className="button button-secondary"
                onClick={() => setSelectedEmail(null)}
                style={{ padding: '4px 10px', fontSize: 12 }}
              >
                Close
              </button>
            </div>

            {/* MODAL BODY */}
            <div style={{ padding: 20, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 8, fontSize: 12 }}>
                <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Recipient:</span>
                <span style={{ fontFamily: 'monospace', fontWeight: 700, color: 'var(--text-primary)' }}>
                  {selectedEmail.recipient_email}
                </span>

                <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Category:</span>
                <span style={{ color: 'var(--text-primary)' }}>
                  {selectedEmail.recipient_category} ({selectedEmail.department})
                </span>

                {selectedEmail.customer_order_id && (
                  <>
                    <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Order ID:</span>
                    <span style={{ fontFamily: 'monospace', fontWeight: 700, color: 'var(--brand-purple)' }}>
                      {selectedEmail.customer_order_id}
                    </span>
                  </>
                )}

                <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Status:</span>
                <span style={{ color: selectedEmail.status === 'SENT' ? '#16a34a' : '#dc2626', fontWeight: 700 }}>
                  {selectedEmail.status} {selectedEmail.sent_at && `· Dispatched ${new Date(selectedEmail.sent_at).toLocaleString()}`}
                </span>

                <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Subject:</span>
                <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>
                  {selectedEmail.subject}
                </span>
              </div>

              {selectedEmail.failure_reason && (
                <div style={{
                  padding: 10,
                  borderRadius: 8,
                  background: 'rgba(239, 68, 68, 0.08)',
                  border: '1px solid rgba(239, 68, 68, 0.25)',
                  color: '#dc2626',
                  fontSize: 12,
                }}>
                  <strong>Delivery Failure Reason:</strong> {selectedEmail.failure_reason}
                </div>
              )}

              <div>
                <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  Formatted Email Message Body:
                </span>
                <pre
                  style={{
                    marginTop: 6,
                    padding: 16,
                    borderRadius: 8,
                    background: 'var(--kg-bg-2)',
                    border: '1px solid var(--line)',
                    fontSize: 12,
                    fontFamily: 'monospace',
                    color: 'var(--text-primary)',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    lineHeight: 1.55,
                    maxHeight: 360,
                    overflowY: 'auto',
                  }}
                >
                  {selectedEmail.body_text}
                </pre>
              </div>

              {selectedEmail.status === 'FAILED' && (
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 8 }}>
                  <button
                    type="button"
                    className="button button-primary"
                    onClick={() => {
                      handleRetry(selectedEmail.id)
                      setSelectedEmail(null)
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                      fontSize: 12,
                      padding: '7px 16px',
                      background: 'var(--brand-purple)',
                      color: 'white',
                    }}
                  >
                    <RotateCcw size={12} /> Retry Delivery Now
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* SEND TEST NOTIFICATION MODAL */}
      {showTestModal && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
            padding: 20,
          }}
        >
          <div
            className="card"
            style={{
              background: 'var(--surface-hi)',
              border: '1px solid var(--line)',
              borderRadius: 14,
              maxWidth: 500,
              width: '100%',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '0 12px 48px rgba(0,0,0,0.25)',
            }}
          >
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--line)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Send size={16} style={{ color: 'var(--brand-purple)' }} />
                <strong style={{ fontSize: 14, color: 'var(--text-primary)' }}>Send Test Risk Alert Notification</strong>
              </div>
              <button
                type="button"
                className="button button-secondary"
                onClick={() => setShowTestModal(false)}
                style={{ padding: '4px 10px', fontSize: 12 }}
              >
                Close
              </button>
            </div>

            <form onSubmit={handleSendTest} style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 4 }}>
                  Recipient Email Address
                </label>
                <input
                  type="email"
                  required
                  placeholder="e.g. alerts@company.com or test@yopmail.com"
                  value={testEmailInput}
                  onChange={(e) => setTestEmailInput(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: 8,
                    border: '1px solid var(--line)',
                    background: 'var(--surface-hi)',
                    color: 'var(--text-primary)',
                    fontSize: 12,
                    outline: 'none',
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 4 }}>
                  Recipient Category
                </label>
                <select
                  value={testCategoryInput}
                  onChange={(e) => setTestCategoryInput(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: 8,
                    border: '1px solid var(--line)',
                    background: 'var(--surface-hi)',
                    color: 'var(--text-primary)',
                    fontSize: 12,
                    outline: 'none',
                    cursor: 'pointer',
                  }}
                >
                  <option value="CUSTOMER">Customer Direct (Order Commitment Confirmation)</option>
                  <option value="CUSTOMER_SERVICE">Customer Service</option>
                  <option value="OPERATIONAL">Plant Operational (ERP / MES / TMS / QMS)</option>
                </select>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 8 }}>
                <button
                  type="button"
                  className="button button-secondary"
                  onClick={() => setShowTestModal(false)}
                  style={{ fontSize: 12, padding: '7px 14px' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={testSending}
                  className="button button-primary"
                  style={{
                    fontSize: 12,
                    padding: '7px 18px',
                    background: 'linear-gradient(135deg, var(--brand-purple), var(--dr-purple))',
                    color: 'white',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                  }}
                >
                  <Send size={12} /> {testSending ? 'Sending…' : 'Send Test Notification'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
