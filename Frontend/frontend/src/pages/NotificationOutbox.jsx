import { useState, useMemo, useEffect } from 'react'
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
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Copy,
} from 'lucide-react'
import { agentsApi } from '../api/agents.api'
import { useToast } from '../context/ToastContext'

export default function NotificationOutbox() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { toast } = useToast()

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('ALL') // ALL, CUSTOMER, CUSTOMER_SERVICE, OPERATIONAL
  const [statusFilter, setStatusFilter] = useState('ALL') // ALL, SENT, FAILED, PENDING_CONFIG

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize, setPageSize] = useState(25)

  // Interaction State
  const [selectedEmail, setSelectedEmail] = useState(null)
  const [modalTab, setModalTab] = useState('html') // 'html' | 'text'
  const [copiedBody, setCopiedBody] = useState(false)
  const [retryingId, setRetryingId] = useState(null)
  const [isRetryingAll, setIsRetryingAll] = useState(false)
  const [testSending, setTestSending] = useState(false)
  const [showTestModal, setShowTestModal] = useState(false)
  const [testEmailInput, setTestEmailInput] = useState('dyfs2m763cn7s2uz@ethereal.email')
  const [testCategoryInput, setTestCategoryInput] = useState('CUSTOMER_SERVICE')

  // Debounce search query
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(searchQuery)
      setCurrentPage(1)
    }, 300)
    return () => clearTimeout(handler)
  }, [searchQuery])

  // Reset page when filters change
  const handleCategoryChange = (cat) => {
    setCategoryFilter(cat)
    setCurrentPage(1)
  }

  const handleStatusChange = (st) => {
    setStatusFilter(st)
    setCurrentPage(1)
  }

  // Fetch paginated notification logs
  const {
    data: queryResult,
    isLoading,
    isRefetching,
    refetch,
  } = useQuery({
    queryKey: ['notificationOutbox', currentPage, pageSize, categoryFilter, statusFilter, debouncedSearch],
    queryFn: async () => {
      const res = await agentsApi.listNotifications({
        paginated: true,
        page: currentPage,
        page_size: pageSize,
        recipient_category: categoryFilter !== 'ALL' ? categoryFilter : undefined,
        status: statusFilter !== 'ALL' ? statusFilter : undefined,
        search: debouncedSearch.trim() || undefined,
      })
      return res
    },
    refetchInterval: 10000,
  })

  // Normalize response
  const { notifications, totalCount, totalPages, counts } = useMemo(() => {
    if (!queryResult) {
      return { notifications: [], totalCount: 0, totalPages: 1, counts: {} }
    }
    if (Array.isArray(queryResult)) {
      // Fallback if backend returned plain array
      const items = queryResult
      const total = items.length
      const pages = Math.max(1, Math.ceil(total / pageSize))
      const sliced = items.slice((currentPage - 1) * pageSize, currentPage * pageSize)
      const c = {
        total,
        sent: items.filter((i) => i.status === 'SENT').length,
        failed: items.filter((i) => i.status === 'FAILED').length,
        customer: items.filter((i) => (i.recipient_category || '').toUpperCase() === 'CUSTOMER').length,
        cs: items.filter((i) => (i.recipient_category || '').toUpperCase() === 'CUSTOMER_SERVICE').length,
        operational: items.filter((i) => (i.recipient_category || '').toUpperCase() === 'OPERATIONAL').length,
      }
      return { notifications: sliced, totalCount: total, totalPages: pages, counts: c }
    }

    return {
      notifications: queryResult.items || [],
      totalCount: queryResult.total || 0,
      totalPages: queryResult.total_pages || 1,
      counts: queryResult.counts || {},
    }
  }, [queryResult, currentPage, pageSize])

  // Metrics summary
  const metrics = useMemo(() => {
    return {
      total: counts.total ?? totalCount,
      sent: counts.sent ?? 0,
      failed: counts.failed ?? 0,
      customer: counts.customer ?? 0,
      cs: counts.cs ?? 0,
      operational: counts.operational ?? 0,
    }
  }, [counts, totalCount])

  // Single retry
  const handleRetry = async (logId) => {
    setRetryingId(logId)
    try {
      const updated = await agentsApi.retryNotification(logId)
      toast({
        title: 'Notification Dispatched & Synced',
        description: `Notification #${logId} was redelivered via relay (Status: ${updated.status}).`,
        type: updated.status === 'SENT' ? 'success' : 'error',
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

  // Batch retry
  const handleRetryAllFailed = async () => {
    setIsRetryingAll(true)
    try {
      const res = await agentsApi.retryAllFailedNotifications()
      toast({
        title: 'Batch Sync & Delivery Completed',
        description: res?.message || `Retried ${res?.succeeded || 0} failed notifications successfully.`,
        type: 'success',
      })
      refetch()
    } catch (err) {
      toast({
        title: 'Batch Retry Error',
        description: err.response?.data?.detail || err.message,
        type: 'error',
      })
    } finally {
      setIsRetryingAll(false)
    }
  }

  // Send test email
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
        description: `Alert delivered to ${testEmailInput} (Status: ${res.status}).`,
        type: res.status === 'SENT' ? 'success' : 'error',
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

  // Copy body to clipboard
  const handleCopyBody = (text) => {
    if (!text) return
    navigator.clipboard.writeText(text)
    setCopiedBody(true)
    setTimeout(() => setCopiedBody(false), 2000)
  }

  // Calculate row display bounds
  const startItem = totalCount === 0 ? 0 : (currentPage - 1) * pageSize + 1
  const endItem = Math.min(currentPage * pageSize, totalCount)

  return (
    <div className="page-stack">
      {/* HEADER & TOP BAR */}
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

        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
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
              disabled={isRetryingAll}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                fontSize: 12,
                padding: '7px 14px',
                borderRadius: 8,
                border: '1px solid rgba(239, 68, 68, 0.35)',
                background: 'rgba(239, 68, 68, 0.08)',
                color: '#dc2626',
                fontWeight: 700,
              }}
              title="Re-dispatch all failed/pending notifications through the active relay"
            >
              <RotateCcw size={13} className={isRetryingAll ? 'spin' : ''} />
              {isRetryingAll ? 'Syncing & Retrying…' : `Retry All Failed (${metrics.failed})`}
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
            {isRefetching ? 'Synchronizing…' : 'Sync Outbox'}
          </button>
        </div>
      </div>

      {/* METRIC KPI TILES */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
        <div className="card" style={{ padding: '14px 18px', background: 'var(--surface-hi)', border: '1px solid var(--line)', borderRadius: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Total Outbox Records
          </div>
          <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--text-primary)', marginTop: 4 }}>
            {metrics.total.toLocaleString()}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
            Cumulative surveillance dispatches
          </div>
        </div>

        <div className="card" style={{ padding: '14px 18px', background: 'var(--surface-hi)', border: '1px solid var(--line)', borderRadius: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Successful Deliveries
          </div>
          <div style={{ fontSize: 24, fontWeight: 800, color: '#16a34a', marginTop: 4 }}>
            {metrics.sent.toLocaleString()}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
            {metrics.total > 0 ? Math.round((metrics.sent / metrics.total) * 100) : 100}% verified delivery rate
          </div>
        </div>

        <div className="card" style={{ padding: '14px 18px', background: 'var(--surface-hi)', border: '1px solid var(--line)', borderRadius: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Failed / Undelivered
          </div>
          <div style={{ fontSize: 24, fontWeight: 800, color: metrics.failed > 0 ? '#dc2626' : 'var(--text-muted)', marginTop: 4 }}>
            {metrics.failed.toLocaleString()}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
            {metrics.failed > 0 ? 'Click "Retry All Failed" to deliver' : 'All alerts delivered'}
          </div>
        </div>

        <div className="card" style={{ padding: '14px 18px', background: 'var(--surface-hi)', border: '1px solid var(--line)', borderRadius: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Customer Service
          </div>
          <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--brand-purple)', marginTop: 4 }}>
            {metrics.cs.toLocaleString()}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
            Delivery delay risk alerts
          </div>
        </div>

        <div className="card" style={{ padding: '14px 18px', background: 'var(--surface-hi)', border: '1px solid var(--line)', borderRadius: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Plant Operational
          </div>
          <div style={{ fontSize: 24, fontWeight: 800, color: '#ea580c', marginTop: 4 }}>
            {metrics.operational.toLocaleString()}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
            7-conduit corrective directives
          </div>
        </div>
      </div>

      {/* FILTER & SEARCH TOOLBAR */}
      <div className="card" style={{ padding: 14, background: 'var(--surface-hi)', border: '1px solid var(--line)', borderRadius: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
          {/* SEARCH INPUT */}
          <div style={{ position: 'relative', flex: '1 1 260px', maxWidth: 380 }}>
            <Search size={14} style={{ position: 'absolute', left: 12, top: 11, color: 'var(--text-muted)' }} />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search Order ID, recipient email, or subject…"
              style={{
                width: '100%',
                padding: '8px 12px 8px 34px',
                background: 'var(--kg-bg-2)',
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
                  top: 8,
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

          {/* CATEGORY & STATUS FILTERS */}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            {/* CATEGORY TABS */}
            <div style={{ display: 'flex', background: 'var(--kg-bg-2)', padding: 3, borderRadius: 8, border: '1px solid var(--line)', gap: 2 }}>
              <button
                type="button"
                onClick={() => handleCategoryChange('ALL')}
                style={{
                  padding: '5px 10px',
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
                All Recipients
              </button>
              <button
                type="button"
                onClick={() => handleCategoryChange('CUSTOMER')}
                style={{
                  padding: '5px 10px',
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
                Customer Direct
              </button>
              <button
                type="button"
                onClick={() => handleCategoryChange('CUSTOMER_SERVICE')}
                style={{
                  padding: '5px 10px',
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
                Customer Service
              </button>
              <button
                type="button"
                onClick={() => handleCategoryChange('OPERATIONAL')}
                style={{
                  padding: '5px 10px',
                  borderRadius: 6,
                  border: 'none',
                  fontSize: 11,
                  fontWeight: 600,
                  cursor: 'pointer',
                  background: categoryFilter === 'OPERATIONAL' ? '#ea580c' : 'transparent',
                  color: categoryFilter === 'OPERATIONAL' ? 'white' : 'var(--text-secondary)',
                  transition: 'all 0.15s ease',
                }}
              >
                Operational Plant
              </button>
            </div>

            {/* STATUS SELECT */}
            <select
              value={statusFilter}
              onChange={(e) => handleStatusChange(e.target.value)}
              style={{
                padding: '6px 10px',
                borderRadius: 8,
                border: '1px solid var(--line)',
                background: 'var(--kg-bg-2)',
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

            {/* PAGE SIZE SELECT */}
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value))
                setCurrentPage(1)
              }}
              style={{
                padding: '6px 10px',
                borderRadius: 8,
                border: '1px solid var(--line)',
                background: 'var(--kg-bg-2)',
                color: 'var(--text-primary)',
                fontSize: 12,
                fontWeight: 600,
                outline: 'none',
                cursor: 'pointer',
              }}
              title="Rows per page"
            >
              <option value={10}>10 per page</option>
              <option value={25}>25 per page</option>
              <option value={50}>50 per page</option>
              <option value={100}>100 per page</option>
            </select>
          </div>
        </div>
      </div>

      {/* NOTIFICATION LOGS DATA TABLE */}
      <div className="card" style={{ padding: 0, background: 'var(--surface-hi)', border: '1px solid var(--line)', borderRadius: 14, overflow: 'hidden' }}>
        {/* SUBHEADER: RECORD COUNT & ACTIVE FILTERS */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '14px 20px',
            borderBottom: '1px solid var(--line)',
            background: 'var(--kg-bg-2)',
          }}
        >
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
            Showing <strong>{startItem}–{endItem}</strong> of <strong>{totalCount.toLocaleString()}</strong> notification logs
            {isRefetching && <span style={{ marginLeft: 8, fontSize: 11, color: 'var(--text-muted)' }}>(Syncing…)</span>}
          </div>

          {(categoryFilter !== 'ALL' || statusFilter !== 'ALL' || searchQuery) && (
            <button
              type="button"
              className="button button-secondary"
              onClick={() => {
                setCategoryFilter('ALL')
                setStatusFilter('ALL')
                setSearchQuery('')
                setCurrentPage(1)
              }}
              style={{ fontSize: 11, padding: '4px 10px', display: 'flex', alignItems: 'center', gap: 4 }}
            >
              <RotateCcw size={11} /> Reset Filters
            </button>
          )}
        </div>

        {/* TABLE CONTENT */}
        <div style={{ overflowX: 'auto', width: '100%' }}>
          <table className="orders-table" style={{ width: '100%', borderCollapse: 'collapse', minWidth: 920 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--line)', background: 'var(--kg-bg-2)' }}>
                <th style={{ padding: '12px 18px', textAlign: 'left', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)' }}>
                  Order ID
                </th>
                <th style={{ padding: '12px 18px', textAlign: 'left', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)' }}>
                  Recipient Conduit
                </th>
                <th style={{ padding: '12px 18px', textAlign: 'left', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)' }}>
                  Target Address
                </th>
                <th style={{ padding: '12px 18px', textAlign: 'left', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)' }}>
                  Subject / Alert Title
                </th>
                <th style={{ padding: '12px 18px', textAlign: 'left', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)' }}>
                  Delivery Status
                </th>
                <th style={{ padding: '12px 18px', textAlign: 'left', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)' }}>
                  Dispatched At
                </th>
                <th style={{ padding: '12px 18px', textAlign: 'right', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)' }}>
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                Array.from({ length: 6 }).map((_, i) => (
                  <tr key={`loading-${i}`} style={{ borderBottom: '1px solid var(--line)' }}>
                    <td colSpan={7} style={{ padding: '16px 20px', textAlign: 'center' }}>
                      <div className="skeleton-line" style={{ height: 16, width: '90%', margin: '0 auto', background: 'var(--line)', borderRadius: 4, opacity: 0.6 }} />
                    </td>
                  </tr>
                ))
              ) : notifications.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ padding: '48px 20px', textAlign: 'center', color: 'var(--text-secondary)' }}>
                    <Mail size={32} style={{ color: 'var(--text-muted)', marginBottom: 8, opacity: 0.6 }} />
                    <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>No notifications match your current filter</div>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                      Try adjusting your search query, recipient conduit, or delivery status filter.
                    </div>
                  </td>
                </tr>
              ) : (
                notifications.map((n) => {
                  const cat = (n.recipient_category || 'OPERATIONAL').toUpperCase()
                  const isCustomer = cat === 'CUSTOMER'
                  const isCS = cat === 'CUSTOMER_SERVICE'
                  const formattedDate = n.sent_at || n.created_at ? new Date(n.sent_at || n.created_at).toLocaleString() : 'N/A'
                  const isSent = n.status === 'SENT'
                  const isFailed = n.status === 'FAILED'

                  return (
                    <tr
                      key={n.id}
                      style={{
                        borderBottom: '1px solid var(--line)',
                        background: 'transparent',
                        transition: 'background 0.15s ease',
                      }}
                      className="table-row-hover"
                    >
                      {/* ORDER ID */}
                      <td style={{ padding: '12px 18px', verticalAlign: 'middle', whiteSpace: 'nowrap' }}>
                        {n.customer_order_id && n.customer_order_id !== 'SYSTEM' ? (
                          <Link
                            to={`/orders/${encodeURIComponent(n.customer_order_id)}`}
                            style={{
                              textDecoration: 'none',
                              color: 'var(--brand-purple)',
                              fontFamily: 'monospace',
                              fontWeight: 700,
                              fontSize: 12,
                              background: 'rgba(111, 61, 186, 0.08)',
                              padding: '3px 8px',
                              borderRadius: 6,
                              border: '1px solid rgba(111, 61, 186, 0.25)',
                              display: 'inline-block',
                            }}
                            title={`Inspect Order ${n.customer_order_id}`}
                          >
                            {n.customer_order_id}
                          </Link>
                        ) : (
                          <span style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--text-muted)' }}>
                            {n.customer_order_id || 'N/A'}
                          </span>
                        )}
                      </td>

                      {/* RECIPIENT CONDUIT */}
                      <td style={{ padding: '12px 18px', verticalAlign: 'middle', whiteSpace: 'nowrap' }}>
                        <span
                          style={{
                            background: isCustomer
                              ? 'rgba(37, 99, 235, 0.12)'
                              : isCS
                              ? 'rgba(111, 61, 186, 0.12)'
                              : 'rgba(234, 88, 12, 0.12)',
                            color: isCustomer ? '#2563eb' : isCS ? 'var(--brand-purple)' : '#ea580c',
                            fontWeight: 700,
                            fontSize: 10,
                            padding: '3px 8px',
                            borderRadius: 6,
                            border: isCustomer
                              ? '1px solid rgba(37, 99, 235, 0.25)'
                              : isCS
                              ? '1px solid rgba(111, 61, 186, 0.25)'
                              : '1px solid rgba(234, 88, 12, 0.25)',
                            letterSpacing: '0.02em',
                            display: 'inline-block',
                          }}
                        >
                          {isCustomer ? 'CUSTOMER · DIRECT' : isCS ? 'CUSTOMER SERVICE' : `OPERATIONAL · ${n.department || 'PLANT'}`}
                        </span>
                      </td>

                      {/* TARGET EMAIL */}
                      <td style={{ padding: '12px 18px', verticalAlign: 'middle', whiteSpace: 'nowrap' }}>
                        <span style={{ fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'monospace', fontSize: 12 }}>
                          {n.recipient_email}
                        </span>
                      </td>

                      {/* SUBJECT */}
                      <td style={{ padding: '12px 18px', verticalAlign: 'middle', maxWidth: 360 }}>
                        <div
                          style={{
                            fontSize: 12,
                            fontWeight: 600,
                            color: 'var(--text-primary)',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                          title={n.subject}
                        >
                          {n.subject}
                        </div>
                        {n.failure_reason && (
                          <div
                            style={{
                              fontSize: 11,
                              color: '#dc2626',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                              marginTop: 2,
                            }}
                            title={n.failure_reason}
                          >
                            ⚠️ {n.failure_reason}
                          </div>
                        )}
                      </td>

                      {/* STATUS */}
                      <td style={{ padding: '12px 18px', verticalAlign: 'middle', whiteSpace: 'nowrap' }}>
                        <span
                          style={{
                            fontSize: 11,
                            fontWeight: 700,
                            padding: '4px 10px',
                            borderRadius: 12,
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 5,
                            background: isSent
                              ? 'rgba(34, 197, 94, 0.12)'
                              : isFailed
                              ? 'rgba(239, 68, 68, 0.12)'
                              : 'rgba(234, 179, 8, 0.12)',
                            color: isSent ? '#16a34a' : isFailed ? '#dc2626' : '#ca8a04',
                            border: isSent
                              ? '1px solid rgba(34, 197, 94, 0.3)'
                              : isFailed
                              ? '1px solid rgba(239, 68, 68, 0.3)'
                              : '1px solid rgba(234, 179, 8, 0.3)',
                          }}
                          title={isSent ? 'Delivered via Vercel Relay to Ethereal mailbox' : n.failure_reason || 'Pending delivery'}
                        >
                          {isSent && <CheckCircle2 size={12} />}
                          {isFailed && <AlertTriangle size={12} />}
                          {!isSent && !isFailed && <Clock size={12} />}
                          {n.status}
                        </span>
                      </td>

                      {/* DISPATCHED AT */}
                      <td style={{ padding: '12px 18px', verticalAlign: 'middle', whiteSpace: 'nowrap', fontSize: 11, color: 'var(--text-muted)' }}>
                        {formattedDate}
                      </td>

                      {/* ACTIONS */}
                      <td style={{ padding: '12px 18px', verticalAlign: 'middle', textAlign: 'right', whiteSpace: 'nowrap' }}>
                        <div style={{ display: 'inline-flex', gap: 6 }}>
                          <button
                            type="button"
                            className="button button-secondary"
                            onClick={() => {
                              setSelectedEmail(n)
                              setModalTab('html')
                            }}
                            style={{
                              fontSize: 11,
                              padding: '4px 10px',
                              display: 'inline-flex',
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
                                padding: '4px 10px',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 4,
                                color: '#dc2626',
                                borderColor: 'rgba(239, 68, 68, 0.35)',
                                background: 'rgba(239, 68, 68, 0.05)',
                                fontWeight: 700,
                              }}
                              title="Re-dispatch this email via Vercel HTTPS Relay"
                            >
                              <RotateCcw size={11} className={retryingId === n.id ? 'spin' : ''} />
                              {retryingId === n.id ? 'Retrying…' : 'Retry'}
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>

        {/* PAGINATION CONTROLS FOOTER */}
        <div
          className="table-footer"
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '12px 20px',
            borderTop: '1px solid var(--line)',
            background: 'var(--kg-bg-2)',
            flexWrap: 'wrap',
            gap: 12,
          }}
        >
          <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
            Page <strong>{currentPage}</strong> of <strong>{totalPages || 1}</strong> &nbsp;·&nbsp; Total <strong>{totalCount.toLocaleString()}</strong> notifications
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <button
              type="button"
              className="button button-secondary"
              onClick={() => setCurrentPage(1)}
              disabled={currentPage <= 1 || isLoading}
              style={{ padding: '5px 8px', fontSize: 11, display: 'inline-flex', alignItems: 'center' }}
              title="First Page"
            >
              <ChevronsLeft size={14} />
            </button>
            <button
              type="button"
              className="button button-secondary"
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage <= 1 || isLoading}
              style={{ padding: '5px 8px', fontSize: 11, display: 'inline-flex', alignItems: 'center', gap: 4 }}
              title="Previous Page"
            >
              <ChevronLeft size={14} /> Prev
            </button>

            {/* Quick page jumper pills */}
            {Array.from({ length: Math.min(5, totalPages) }, (_, idx) => {
              let pageNum = currentPage - 2 + idx
              if (pageNum < 1) pageNum = idx + 1
              if (pageNum > totalPages) pageNum = totalPages - 4 + idx
              if (pageNum < 1 || pageNum > totalPages) return null

              const isActive = pageNum === currentPage
              return (
                <button
                  key={pageNum}
                  type="button"
                  onClick={() => setCurrentPage(pageNum)}
                  style={{
                    padding: '4px 10px',
                    borderRadius: 6,
                    fontSize: 11,
                    fontWeight: isActive ? 800 : 500,
                    border: isActive ? '1px solid var(--brand-purple)' : '1px solid var(--line)',
                    background: isActive ? 'var(--brand-purple)' : 'var(--surface-hi)',
                    color: isActive ? 'white' : 'var(--text-secondary)',
                    cursor: 'pointer',
                    minWidth: 28,
                  }}
                >
                  {pageNum}
                </button>
              )
            })}

            <button
              type="button"
              className="button button-secondary"
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage >= totalPages || isLoading}
              style={{ padding: '5px 8px', fontSize: 11, display: 'inline-flex', alignItems: 'center', gap: 4 }}
              title="Next Page"
            >
              Next <ChevronRight size={14} />
            </button>
            <button
              type="button"
              className="button button-secondary"
              onClick={() => setCurrentPage(totalPages)}
              disabled={currentPage >= totalPages || isLoading}
              style={{ padding: '5px 8px', fontSize: 11, display: 'inline-flex', alignItems: 'center' }}
              title="Last Page"
            >
              <ChevronsRight size={14} />
            </button>
          </div>
        </div>
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
            background: 'rgba(0,0,0,0.6)',
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
              maxWidth: 760,
              width: '100%',
              maxHeight: '90vh',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '0 16px 64px rgba(0,0,0,0.3)',
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
                  Email Inspection #{selectedEmail.id}
                </strong>
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 800,
                    padding: '2px 8px',
                    borderRadius: 10,
                    background: selectedEmail.status === 'SENT' ? 'rgba(34, 197, 94, 0.12)' : 'rgba(239, 68, 68, 0.12)',
                    color: selectedEmail.status === 'SENT' ? '#16a34a' : '#dc2626',
                    border: selectedEmail.status === 'SENT' ? '1px solid rgba(34, 197, 94, 0.25)' : '1px solid rgba(239, 68, 68, 0.25)',
                  }}
                >
                  {selectedEmail.status}
                </span>
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
              {/* METADATA GRID */}
              <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 8, fontSize: 12, background: 'var(--kg-bg-2)', padding: 14, borderRadius: 8, border: '1px solid var(--line)' }}>
                <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Recipient:</span>
                <span style={{ fontFamily: 'monospace', fontWeight: 700, color: 'var(--text-primary)' }}>
                  {selectedEmail.recipient_email}
                </span>

                <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Conduit:</span>
                <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
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

                <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Subject:</span>
                <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>
                  {selectedEmail.subject}
                </span>

                <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Dispatched:</span>
                <span style={{ color: 'var(--text-secondary)' }}>
                  {selectedEmail.sent_at || selectedEmail.created_at ? new Date(selectedEmail.sent_at || selectedEmail.created_at).toLocaleString() : 'N/A'}
                </span>

                {selectedEmail.provider_message_id && (
                  <>
                    <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Message ID:</span>
                    <span style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--text-secondary)' }}>
                      {selectedEmail.provider_message_id}
                    </span>
                  </>
                )}
              </div>

              {/* FAILURE BANNER */}
              {selectedEmail.failure_reason && (
                <div style={{
                  padding: 12,
                  borderRadius: 8,
                  background: 'rgba(239, 68, 68, 0.08)',
                  border: '1px solid rgba(239, 68, 68, 0.25)',
                  color: '#dc2626',
                  fontSize: 12,
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: 12,
                }}>
                  <div>
                    <strong>Delivery Failure Notice:</strong> {selectedEmail.failure_reason}
                  </div>
                  <button
                    type="button"
                    className="button button-primary"
                    onClick={() => {
                      handleRetry(selectedEmail.id)
                      setSelectedEmail(null)
                    }}
                    style={{
                      padding: '5px 12px',
                      fontSize: 11,
                      background: 'var(--brand-purple)',
                      color: 'white',
                      whiteSpace: 'nowrap',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4,
                    }}
                  >
                    <RotateCcw size={11} /> Retry Now
                  </button>
                </div>
              )}

              {/* TABS FOR BODY VIEW */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                  <div style={{ display: 'flex', gap: 4 }}>
                    <button
                      type="button"
                      onClick={() => setModalTab('html')}
                      style={{
                        padding: '4px 10px',
                        borderRadius: 6,
                        border: 'none',
                        fontSize: 11,
                        fontWeight: modalTab === 'html' ? 700 : 500,
                        background: modalTab === 'html' ? 'var(--brand-purple)' : 'var(--kg-bg-2)',
                        color: modalTab === 'html' ? 'white' : 'var(--text-secondary)',
                        cursor: 'pointer',
                      }}
                    >
                      Formatted View
                    </button>
                    <button
                      type="button"
                      onClick={() => setModalTab('text')}
                      style={{
                        padding: '4px 10px',
                        borderRadius: 6,
                        border: 'none',
                        fontSize: 11,
                        fontWeight: modalTab === 'text' ? 700 : 500,
                        background: modalTab === 'text' ? 'var(--brand-purple)' : 'var(--kg-bg-2)',
                        color: modalTab === 'text' ? 'white' : 'var(--text-secondary)',
                        cursor: 'pointer',
                      }}
                    >
                      Raw Plain Text
                    </button>
                  </div>

                  <button
                    type="button"
                    onClick={() => handleCopyBody(selectedEmail.body_text)}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'var(--text-secondary)',
                      fontSize: 11,
                      cursor: 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 4,
                    }}
                  >
                    {copiedBody ? <Check size={12} color="#16a34a" /> : <Copy size={12} />}
                    {copiedBody ? 'Copied!' : 'Copy Body'}
                  </button>
                </div>

                {modalTab === 'text' ? (
                  <pre
                    style={{
                      marginTop: 4,
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
                      maxHeight: 380,
                      overflowY: 'auto',
                    }}
                  >
                    {selectedEmail.body_text}
                  </pre>
                ) : (
                  <div
                    style={{
                      marginTop: 4,
                      padding: 16,
                      borderRadius: 8,
                      background: '#FFFFFF',
                      color: '#1E293B',
                      border: '1px solid var(--line)',
                      fontSize: 13,
                      lineHeight: 1.6,
                      maxHeight: 400,
                      overflowY: 'auto',
                      boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.05)',
                    }}
                  >
                    {selectedEmail.html_body ? (
                      <div dangerouslySetInnerHTML={{ __html: selectedEmail.html_body }} />
                    ) : (
                      <div style={{ whiteSpace: 'pre-line' }}>{selectedEmail.body_text}</div>
                    )}
                  </div>
                )}
              </div>
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
                  placeholder="e.g. dyfs2m763cn7s2uz@ethereal.email"
                  value={testEmailInput}
                  onChange={(e) => setTestEmailInput(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: 8,
                    border: '1px solid var(--line)',
                    background: 'var(--kg-bg-2)',
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
                    background: 'var(--kg-bg-2)',
                    color: 'var(--text-primary)',
                    fontSize: 12,
                    outline: 'none',
                    cursor: 'pointer',
                  }}
                >
                  <option value="CUSTOMER">Customer Direct (Order Confirmation)</option>
                  <option value="CUSTOMER_SERVICE">Customer Service (Delivery Delay Alert)</option>
                  <option value="OPERATIONAL">Plant Operational (ERP / MES / TMS / QMS Directive)</option>
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
