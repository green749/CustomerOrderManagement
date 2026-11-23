import { useState, useMemo, useEffect, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Bot,
  BellRing,
  Layers,
  Factory,
  ShieldAlert,
  Warehouse,
  Truck,
  Building2,
  Cpu,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Play,
  RotateCcw,
  Mail,
  UserCheck,
  Send,
  Clock,
  Calendar,
  Check,
  HelpCircle,
  Filter,
  CheckSquare,
  ArrowUpRight,
  Eye,
  Search,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  ChevronDown,
  Zap,
  Package,
  RefreshCw,
  X,
  ArrowRight,
} from 'lucide-react'
import { agentsApi } from '../../api/agents.api'
import { formatDate, formatINR, formatNumber } from '../../utils/format'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'

// All 7 operational departments supported by Manufacturing 360
const DEPTS = [
  { code: 'ERP', name: 'Order & Commercial', icon: Building2, desc: 'Commitments & SLA terms' },
  { code: 'MMS', name: 'Material Planning', icon: Layers, desc: 'Component stock & shortages' },
  { code: 'MES', name: 'Plant Production', icon: Factory, desc: 'Plant cycles & bottlenecks' },
  { code: 'QMS', name: 'Quality Release', icon: ShieldAlert, desc: 'Quality holds & lot scrap' },
  { code: 'WMS', name: 'Warehouse & Staging', icon: Warehouse, desc: 'FG staging & bay readiness' },
  { code: 'TMS', name: 'Logistics & Transit', icon: Truck, desc: 'Carrier transit & milestones' },
  { code: 'PLM', name: 'Product Lifecycle', icon: Cpu, desc: 'BOM revisions & config drift' },
]

const extractBreachBadge = (desc) => {
  if (!desc) return null
  const match = desc.match(/(\d+)\s*days?\s*overdue/i)
  if (match) return `${match[1]}d Overdue`
  if (desc.toLowerCase().includes('breached')) return 'Breached'
  if (desc.toLowerCase().includes('overdue')) return 'Overdue'
  return null
}

export function Agent3MonitoringWorkspace({ customerOrderId, surveillanceTrigger = 0, onShowOrders }) {
  const { user } = useAuth()
  const { toast } = useToast()
  const navigate = useNavigate()
  const [runningCycle, setRunningCycle] = useState(false)
  const [cycleNotice, setCycleNotice] = useState('')
  const [triggerError, setTriggerError] = useState(null)
  const [isScanning, setIsScanning] = useState(false)
  const [scanningDept, setScanningDept] = useState(null)
  const [scannedDepts, setScannedDepts] = useState({})
  const [assigneeInput, setAssigneeInput] = useState({})
  const [resolutionInput, setResolutionInput] = useState({})
  const [activeActionModal, setActiveActionModal] = useState(null) // { type: 'assign' | 'resolve', alertId }
  const [showAgent3Trace, setShowAgent3Trace] = useState(false)
  const [expandedA3Steps, setExpandedA3Steps] = useState({})
  
  // Interactive filters
  const [selectedDept, setSelectedDept] = useState('ALL')
  const [selectedStatus, setSelectedStatus] = useState('ALL')
  const [actionSuccessMsg, setActionSuccessMsg] = useState('')
  const [dispatchingAlertId, setDispatchingAlertId] = useState(null)
  const [selectedEmailPreview, setSelectedEmailPreview] = useState(null)
  const [testEmailLoading, setTestEmailLoading] = useState(false)

  // Monitored orders state
  const [activeOrderFilter, setActiveOrderFilter] = useState(customerOrderId || '')
  const [recordSearch, setRecordSearch] = useState('')
  const [recordTab, setRecordTab] = useState('ALL') // 'ALL' | 'ACTIVE' | 'RISKS' | 'CLEAR' | 'DELIVERED'
  const [recordPage, setRecordPage] = useState(1)
  const RECORDS_PER_PAGE = 8

  // Agent corrective actions state
  const [actionFilter, setActionFilter] = useState('ALL') // 'ALL' | 'PROPOSED' | 'EXECUTED' | 'REJECTED'
  const [actionSubmitting, setActionSubmitting] = useState({})

  const effectiveOrderId = activeOrderFilter || customerOrderId || undefined

  const {
    data: workspaceData = {
      alerts: [],
      summary: null,
      logs: [],
      notifications: [],
      contacts: [],
      records: [],
      monitoringRec: null,
      actions: [],
    },
    isLoading: loading,
    refetch: loadData,
  } = useQuery({
    queryKey: ['agent3-monitoring', effectiveOrderId],
    queryFn: async () => {
      const promises = [
        agentsApi.listAlerts({ customer_order_id: effectiveOrderId, page_size: 100 }),
        agentsApi.getAlertsSummary(),
        agentsApi.listMonitoringLogs(5),
        agentsApi.listNotifications({ customer_order_id: effectiveOrderId }),
        agentsApi.listDepartmentContacts().catch(() => []),
        agentsApi.listMonitoringRecords({ limit: 200 }).catch(() => []),
        agentsApi.listActions({ customer_order_id: effectiveOrderId }).catch(() => []),
      ]

      if (effectiveOrderId) {
        promises.push(agentsApi.getMonitoringRecord(effectiveOrderId).catch(() => null))
      }

      const [alertsRes, summaryRes, logsRes, notificationsRes, contactsRes, recordsRes, actionsRes, recordRes] = await Promise.all(promises)
      return {
        alerts: Array.isArray(alertsRes) ? alertsRes : [],
        summary: summaryRes || null,
        logs: Array.isArray(logsRes) ? logsRes : [],
        notifications: Array.isArray(notificationsRes) ? notificationsRes : [],
        contacts: Array.isArray(contactsRes) ? contactsRes : [],
        records: Array.isArray(recordsRes) ? recordsRes : [],
        actions: Array.isArray(actionsRes) ? actionsRes : [],
        monitoringRec: recordRes || null,
      }
    },
    staleTime: 45 * 1000,
  })

  const alerts = workspaceData.alerts
  const summary = workspaceData.summary
  const logs = workspaceData.logs
  const notifications = workspaceData.notifications
  const contacts = workspaceData.contacts
  const records = workspaceData.records || []
  const actions = workspaceData.actions || []
  const monitoringRec = workspaceData.monitoringRec

  const csContact = contacts.find((c) => c.department === 'CUSTOMER_SERVICE')

  const { data: agent3Runs = [], refetch: refetchAgent3Runs } = useQuery({
    queryKey: ['agent3-runs', effectiveOrderId],
    queryFn: () => agentsApi.getAgentRuns({ customer_order_id: effectiveOrderId || undefined, agent_name: 'agent3' }),
    staleTime: 30 * 1000,
  })

  const handleRunSurveillance = async () => {
    if (isScanning || runningCycle) return
    setIsScanning(true)
    setRunningCycle(true)
    setCycleNotice('')
    setTriggerError(null)

    try {
      const res = await agentsApi.runMonitoringCycle()
      const refetchResult = await loadData()
      refetchAgent3Runs()
      const freshAlerts = refetchResult.data?.alerts || []
      const openCount = freshAlerts.filter((a) => a.status === 'OPEN').length
      const risksFound = res?.risks_found_count !== undefined ? res.risks_found_count : openCount
      const sentCount = res?.emails_sent !== undefined ? res.emails_sent : 0
      const sourceLabel = res?.result_source === 'AGENT' ? 'AI Agent' : res?.result_source === 'RULES' ? 'Rule Engine' : 'Rules Fallback'

      setIsScanning(false)
      setRunningCycle(false)
      setCycleNotice(
        `Surveillance cycle completed (${sourceLabel})! All 7 departments audited. ${risksFound} active risks evaluated (${sentCount} notifications dispatched). Click any department card below to view its risks.`
      )
      toast.success(`Surveillance cycle completed: ${risksFound} active risks evaluated.`, { title: 'Surveillance Complete' })
    } catch (err) {
      console.error('Surveillance backend cycle error:', err)
      setIsScanning(false)
      setRunningCycle(false)
      const msg = err.response?.data?.detail || err.message || 'Surveillance monitoring cycle failed.'
      setTriggerError(msg)
      toast.error(`Monitoring cycle failed: ${msg}`, { title: 'Surveillance Error' })
    }
  }

  // Handle surveillance trigger from top-level page header
  const isMountedRef = useRef(false)
  useEffect(() => {
    if (!isMountedRef.current) {
      isMountedRef.current = true
      return
    }
    if (surveillanceTrigger > 0) {
      handleRunSurveillance()
    }
  }, [surveillanceTrigger])

  const scrollToOrders = () => {
    if (onShowOrders) {
      onShowOrders()
    } else {
      navigate('/monitoring/orders')
    }
  }

  const handleDispatchNotification = async (alertId) => {
    setDispatchingAlertId(alertId)
    try {
      const res = await agentsApi.dispatchAlertNotification(alertId)
      const cs = res.customer_service_notification
      const op = res.operational_notification
      setActionSuccessMsg(`Dispatched notifications for Alert #${alertId}: CS (${cs?.recipient || 'N/A'}: ${cs?.status}) & ${alert?.department || 'Dept'} (${op?.recipient || 'N/A'}: ${op?.status}).`)
      setTimeout(() => setActionSuccessMsg(''), 6000)
      await loadData()
    } catch (err) {
      alert(`Could not dispatch notification: ${err.response?.data?.detail || err.message}`)
    } finally {
      setDispatchingAlertId(null)
    }
  }

  const handleSendTestEmail = async () => {
    const targetEmail = csContact?.email
    if (!targetEmail) {
      alert('No Customer Service recipient email is configured in Settings.')
      return
    }
    setTestEmailLoading(true)
    try {
      const res = await agentsApi.sendTestNotification({
        recipient_email: targetEmail,
        recipient_category: 'CUSTOMER_SERVICE',
      })
      setActionSuccessMsg(`Test notification sent to Customer Service: ${targetEmail} (Status: ${res.status}).`)
      setTimeout(() => setActionSuccessMsg(''), 6000)
      await loadData()
    } catch (err) {
      alert(`Test notification failed: ${err.response?.data?.detail || err.message}`)
    } finally {
      setTestEmailLoading(false)
    }
  }

  const handleAcknowledge = async (alertId) => {
    try {
      await agentsApi.acknowledgeAlert(alertId)
      setActionSuccessMsg(`Alert #${alertId} acknowledged successfully.`)
      setTimeout(() => setActionSuccessMsg(''), 4000)
      await loadData()
    } catch (err) {
      alert(`Could not acknowledge alert: ${err.response?.data?.detail || err.message}`)
    }
  }

  const handleAssign = async (alertId) => {
    const owner = assigneeInput[alertId]
    if (!owner || !owner.trim()) return
    try {
      await agentsApi.assignAlert(alertId, owner.trim())
      setActiveActionModal(null)
      setActionSuccessMsg(`Alert #${alertId} assigned to ${owner.trim()}.`)
      setTimeout(() => setActionSuccessMsg(''), 4000)
      await loadData()
    } catch (err) {
      alert(`Could not assign owner: ${err.response?.data?.detail || err.message}`)
    }
  }

  const handleResolve = async (alertId) => {
    const notes = resolutionInput[alertId]
    if (!notes || !notes.trim()) return
    try {
      await agentsApi.resolveAlert(alertId, notes.trim())
      setActiveActionModal(null)
      setActionSuccessMsg(`Alert #${alertId} resolved and logged to audit trail.`)
      setTimeout(() => setActionSuccessMsg(''), 4000)
      await loadData()
    } catch (err) {
      alert(`Could not resolve alert: ${err.response?.data?.detail || err.message}`)
    }
  }

  const handleRetryEmail = async (logId) => {
    try {
      await agentsApi.retryNotification(logId)
      await loadData()
    } catch (err) {
      alert(`Email retry failed: ${err.response?.data?.detail || err.message}`)
    }
  }

  const handleApproveAction = async (actionId) => {
    try {
      setActionSubmitting((prev) => ({ ...prev, [actionId]: true }))
      await agentsApi.approveAction(actionId)
      setActionSuccessMsg(`Action #${actionId} approved and executed successfully!`)
      setTimeout(() => setActionSuccessMsg(''), 4000)
      await loadData()
    } catch (err) {
      alert(`Could not approve action: ${err.response?.data?.detail || err.message}`)
    } finally {
      setActionSubmitting((prev) => ({ ...prev, [actionId]: false }))
    }
  }

  const handleRejectAction = async (actionId) => {
    const reason = window.prompt('Enter optional rejection reason (leave blank to proceed):', '')
    if (reason === null) return
    try {
      setActionSubmitting((prev) => ({ ...prev, [actionId]: true }))
      await agentsApi.rejectAction(actionId, { reason: reason.trim() || 'Rejected by operational reviewer' })
      setActionSuccessMsg(`Action #${actionId} rejected.`)
      setTimeout(() => setActionSuccessMsg(''), 4000)
      await loadData()
    } catch (err) {
      alert(`Could not reject action: ${err.response?.data?.detail || err.message}`)
    } finally {
      setActionSubmitting((prev) => ({ ...prev, [actionId]: false }))
    }
  }

  const getSeverityBadge = (severity) => {
    switch (severity?.toUpperCase()) {
      case 'CRITICAL':
        return (
          <span style={{
            fontSize: 10,
            fontWeight: 800,
            padding: '3px 8px',
            borderRadius: 6,
            background: 'rgba(239, 68, 68, 0.12)',
            color: '#dc2626',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            letterSpacing: '0.04em'
          }}>
            CRITICAL
          </span>
        )
      case 'HIGH':
        return (
          <span style={{
            fontSize: 10,
            fontWeight: 800,
            padding: '3px 8px',
            borderRadius: 6,
            background: 'rgba(249, 115, 22, 0.12)',
            color: '#ea580c',
            border: '1px solid rgba(249, 115, 22, 0.3)',
            letterSpacing: '0.04em'
          }}>
            HIGH
          </span>
        )
      case 'MEDIUM':
        return (
          <span style={{
            fontSize: 10,
            fontWeight: 700,
            padding: '3px 8px',
            borderRadius: 6,
            background: 'rgba(234, 179, 8, 0.12)',
            color: '#ca8a04',
            border: '1px solid rgba(234, 179, 8, 0.3)',
            letterSpacing: '0.04em'
          }}>
            MEDIUM
          </span>
        )
      default:
        return (
          <span style={{
            fontSize: 10,
            fontWeight: 700,
            padding: '3px 8px',
            borderRadius: 6,
            background: 'rgba(100, 116, 139, 0.12)',
            color: '#475569',
            border: '1px solid rgba(100, 116, 139, 0.3)',
            letterSpacing: '0.04em'
          }}>
            LOW
          </span>
        )
    }
  }

  const depts = DEPTS

  // Filter alerts based on active UI selections
  const filteredAlerts = alerts.filter((a) => {
    if (selectedDept !== 'ALL' && a.department?.toUpperCase() !== selectedDept) return false
    if (selectedStatus !== 'ALL' && a.status?.toUpperCase() !== selectedStatus) return false
    return true
  })

  // Filtered and paginated monitored orders
  const filteredRecords = useMemo(() => {
    return records.filter((r) => {
      // Tab filter
      if (recordTab === 'ACTIVE' && r.status !== 'ACTIVE') return false
      if (recordTab === 'DELIVERED' && r.status !== 'DELIVERED') return false
      if (recordTab === 'RISKS' && (r.open_alerts_count || 0) === 0) return false
      if (recordTab === 'CLEAR' && ((r.open_alerts_count || 0) > 0 || r.status !== 'ACTIVE')) return false

      // Search filter
      if (recordSearch.trim()) {
        const q = recordSearch.toLowerCase().replace('order #', '').replace('order ', '').trim()
        const qHyphen = q.replaceAll(' ', '-')
        const matches =
          r.customer_order_id?.toLowerCase().includes(q) ||
          r.customer_order_id?.toLowerCase().includes(qHyphen) ||
          r.customer_name?.toLowerCase().includes(q) ||
          r.product_name?.toLowerCase().includes(q)
        if (!matches) return false
      }
      return true
    })
  }, [records, recordTab, recordSearch])

  const totalRecordPages = Math.ceil(filteredRecords.length / RECORDS_PER_PAGE) || 1
  const paginatedRecords = useMemo(() => {
    const start = (recordPage - 1) * RECORDS_PER_PAGE
    return filteredRecords.slice(start, start + RECORDS_PER_PAGE)
  }, [filteredRecords, recordPage])

  const activeRecordsCount = records.filter((r) => r.status === 'ACTIVE').length
  const riskyRecordsCount = records.filter((r) => (r.open_alerts_count || 0) > 0).length
  const clearRecordsCount = records.filter((r) => r.status === 'ACTIVE' && (r.open_alerts_count || 0) === 0).length
  const deliveredRecordsCount = records.filter((r) => r.status === 'DELIVERED').length

  const filteredActions = useMemo(() => {
    return actions.filter((a) => {
      if (actionFilter !== 'ALL' && a.status?.toUpperCase() !== actionFilter) return false
      return true
    })
  }, [actions, actionFilter])

  return (
    <div className="page-stack" style={{ gap: 20 }}>
      {/* 1. SPECIFIC ORDER MONITORING RECORD METADATA (IF PRESENT) */}
      {monitoringRec && (
        <div className="card" style={{ padding: 18, background: 'var(--surface-hi)', border: '1px solid var(--line)', borderRadius: 12 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 14 }}>
            <div>
              <span style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>Monitored Order</span>
              <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', marginTop: 2 }}>{monitoringRec.customer_order_id}</div>
            </div>
            <div>
              <span style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>Committed Delivery Date</span>
              <div style={{ fontSize: 14, fontWeight: 700, color: '#16a34a', marginTop: 2 }}>{formatDate(monitoringRec.approved_delivery_date)}</div>
            </div>
            <div>
              <span style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>Surveillance Status</span>
              <div style={{ fontSize: 14, fontWeight: 700, color: monitoringRec.status === 'ACTIVE' ? '#16a34a' : 'var(--text-muted)', marginTop: 2 }}>
                {monitoringRec.status}
              </div>
            </div>
            <div>
              <span style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>Surveillance Activation</span>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
                {monitoringRec.started_at ? new Date(monitoringRec.started_at).toLocaleString() : 'N/A'}
              </div>
            </div>
            <div>
              <span style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>Last Evaluation Run</span>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
                {monitoringRec.last_checked_at ? new Date(monitoringRec.last_checked_at).toLocaleString() : 'Scheduled'}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 2. COMBINED ACTIVE SURVEILLANCE & DEPARTMENT RISK CARD */}
      <div 
        className="card"
        style={{
          padding: '18px 20px',
          background: 'var(--surface-hi)',
          border: '1px solid var(--line)',
          borderRadius: 14,
          boxShadow: '0 2px 8px rgba(0,0,0,0.02)',
          display: 'flex',
          flexDirection: 'column',
          gap: 16
        }}
      >
        {/* Top Header Bar: Title, Metrics & Run Cycle Button */}
        <div 
          style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center', 
            flexWrap: 'wrap', 
            gap: 14,
            paddingBottom: 14,
            borderBottom: '1px solid var(--line)'
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
              <h3 style={{ 
                fontSize: 13, 
                fontWeight: 800, 
                margin: 0, 
                textTransform: 'uppercase', 
                letterSpacing: '0.04em', 
                color: 'var(--brand-purple)', 
                display: 'flex', 
                alignItems: 'center', 
                gap: 8 
              }}>
                <Bot size={16} /> Active Surveillance Departments
              </h3>

              {summary && (
                <div 
                  style={{ 
                    display: 'inline-flex', 
                    gap: 10, 
                    fontSize: 12, 
                    alignItems: 'center',
                    background: 'var(--kg-bg-2)',
                    padding: '4px 12px',
                    borderRadius: 8,
                    border: '1px solid var(--line)',
                    color: 'var(--text-primary)'
                  }}
                >
                  <span>Total Open Risks: <strong style={{ color: '#ef4444', fontWeight: 800 }}>{summary.total_open}</strong></span>
                  <span style={{ color: 'var(--text-muted)' }}>·</span>
                  <span>Critical: <strong style={{ color: '#ef4444', fontWeight: 800 }}>{summary.critical}</strong></span>
                  <span style={{ color: 'var(--text-muted)' }}>·</span>
                  <span>Resolved: <strong style={{ color: '#16a34a', fontWeight: 800 }}>{summary.resolved}</strong></span>
                </div>
              )}
            </div>

            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>
              Click department card to inspect risks · Selected: <strong style={{ color: 'var(--brand-purple)' }}>{selectedDept}</strong>
            </div>
          </div>

          {/* CONDUIT SURVEILLANCE STATUS & FILTER CONTROLS */}
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                fontSize: 11,
                fontWeight: 700,
                padding: '4px 10px',
                borderRadius: 20,
                background: isScanning ? 'rgba(139, 92, 246, 0.12)' : 'rgba(34, 197, 94, 0.1)',
                color: isScanning ? '#8b5cf6' : '#16a34a',
                border: isScanning ? '1px solid rgba(139, 92, 246, 0.3)' : '1px solid rgba(34, 197, 94, 0.25)',
              }}
            >
              {isScanning ? (
                <>
                  <span className="spin"><RefreshCw size={11} /></span>
                  Scanning {scanningDept || 'Conduits'}...
                </>
              ) : (
                <>
                  <span
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: '50%',
                      background: '#22c55e',
                    }}
                    className="animate-pulse"
                  />
                  7/7 Conduits Online
                </>
              )}
            </span>

            {selectedDept !== 'ALL' && (
              <button
                type="button"
                className="button button-secondary"
                onClick={() => setSelectedDept('ALL')}
                style={{
                  fontSize: 11,
                  padding: '4px 10px',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  fontWeight: 600,
                  color: 'var(--brand-purple)',
                }}
                title="Clear department filter"
              >
                <X size={12} /> Clear Filter ({selectedDept})
              </button>
            )}
          </div>
        </div>

        {/* Dynamic Scan & Flow Connectivity CSS Keyframes */}
        <style>{`
          @keyframes pulseScanBorder {
            0% { box-shadow: 0 0 0 0 rgba(139, 92, 246, 0.45); border-color: #8b5cf6; }
            50% { box-shadow: 0 0 0 8px rgba(139, 92, 246, 0.08); border-color: #a78bfa; }
            100% { box-shadow: 0 0 0 0 rgba(139, 92, 246, 0); border-color: #8b5cf6; }
          }
          .scanning-pulse {
            animation: pulseScanBorder 0.85s infinite ease-in-out !important;
          }
          @keyframes scanline {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
          }
          @keyframes flowLaser {
            0% { left: -10%; opacity: 0.2; }
            50% { opacity: 1; }
            100% { left: 100%; opacity: 0.2; }
          }
        `}</style>

        {/* Notices */}
        {triggerError && (
          <div style={{
            padding: '10px 14px',
            background: 'rgba(239, 68, 68, 0.08)',
            border: '1px solid rgba(239, 68, 68, 0.25)',
            borderRadius: 8,
            fontSize: 12,
            color: '#dc2626',
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}>
            <XCircle size={16} /> {triggerError}
          </div>
        )}

        {cycleNotice && (
          <div style={{ 
            padding: '10px 14px', 
            background: 'rgba(111, 61, 186, 0.08)', 
            border: '1px solid rgba(111, 61, 186, 0.25)', 
            borderRadius: 8, 
            fontSize: 12, 
            color: 'var(--brand-purple)',
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            gap: 8
          }}>
            <CheckCircle2 size={16} /> {cycleNotice}
          </div>
        )}

        {actionSuccessMsg && (
          <div style={{ 
            padding: '10px 14px', 
            background: 'rgba(34, 197, 94, 0.08)', 
            border: '1px solid rgba(34, 197, 94, 0.3)', 
            borderRadius: 8, 
            fontSize: 12, 
            color: '#16a34a',
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            gap: 8
          }}>
            <CheckCircle2 size={16} /> {actionSuccessMsg}
          </div>
        )}

        {/* Department Surveillance Pipeline with Connected Arrow Flow */}
        <div 
          style={{ 
            display: 'flex', 
            alignItems: 'stretch',
            width: '100%',
            overflowX: 'auto',
            paddingBottom: 8,
            gap: 0,
          }}
        >
          {depts.map((d, idx) => {
            const Icon = d.icon
            const isLast = idx === depts.length - 1
            const nextDept = depts[idx + 1]
            const deptAlerts = alerts.filter((a) => a.department === d.code && a.status === 'OPEN')
            const hasRisks = deptAlerts.length > 0
            const isSelected = selectedDept === d.code
            const isScanningThis = scanningDept === d.code
            const isScanned = Boolean(scannedDepts[d.code])
            
            // Flow connectivity: active when this card is scanning or transitioning to the next card
            const isFlowConnecting = isScanning && (isScanningThis || (isScanned && !scannedDepts[nextDept?.code]))
            const isFlowPassed = isScanned && Boolean(scannedDepts[nextDept?.code])

            return (
              <div
                key={d.code}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  flex: '1 1 0',
                  minWidth: 132,
                }}
              >
                {/* 1. THE DEPARTMENT CARD */}
                <div
                  onClick={() => {
                    const nextDept = isSelected ? 'ALL' : d.code
                    setSelectedDept(nextDept)
                    setTimeout(() => {
                      document.getElementById('risk-alerts-feed-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
                    }, 50)
                  }}
                  className={`card ${isScanningThis ? 'scanning-pulse' : ''}`}
                  style={{
                    flex: 1,
                    padding: '12px 14px',
                    cursor: 'pointer',
                    borderRadius: 12,
                    transition: 'all 0.22s cubic-bezier(0.4, 0, 0.2, 1)',
                    border: isSelected 
                      ? '2px solid var(--brand-purple)' 
                      : isScanningThis
                      ? '2px solid #8b5cf6'
                      : hasRisks 
                      ? '1px solid rgba(239, 68, 68, 0.35)' 
                      : '1px solid var(--line)',
                    borderTop: isSelected
                      ? '3px solid var(--brand-purple)'
                      : isScanningThis
                      ? '3px solid #8b5cf6'
                      : hasRisks
                      ? '3px solid #ef4444'
                      : '3px solid #22c55e',
                    background: isSelected
                      ? 'rgba(111, 61, 186, 0.06)'
                      : isScanningThis
                      ? 'rgba(139, 92, 246, 0.08)'
                      : hasRisks
                      ? 'rgba(239, 68, 68, 0.025)'
                      : 'var(--surface-hi)',
                    boxShadow: isSelected 
                      ? '0 0 0 1px var(--brand-purple), 0 6px 18px rgba(111, 61, 186, 0.16)' 
                      : isScanningThis
                      ? '0 0 16px rgba(139, 92, 246, 0.35)'
                      : '0 1px 3px rgba(0,0,0,0.02)',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    minHeight: 116,
                    position: 'relative',
                    overflow: 'visible',
                  }}
                >
                  {/* Active Scanning Top Bar Effect */}
                  {isScanningThis && (
                    <div
                      style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        right: 0,
                        height: 3,
                        background: 'linear-gradient(90deg, #8b5cf6, #d946ef, #8b5cf6)',
                        animation: 'scanline 1s infinite linear',
                        borderRadius: '12px 12px 0 0',
                      }}
                    />
                  )}

                  {/* Active Selection Pointer Caret */}
                  {isSelected && (
                    <div
                      style={{
                        position: 'absolute',
                        bottom: -7,
                        left: '50%',
                        transform: 'translateX(-50%)',
                        width: 0,
                        height: 0,
                        borderLeft: '6px solid transparent',
                        borderRight: '6px solid transparent',
                        borderTop: '6px solid var(--brand-purple)',
                        zIndex: 5,
                      }}
                    />
                  )}

                  {/* Card Top: Icon, Code, Stage Number & Status Pill (Never wraps!) */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, gap: 6 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 7, minWidth: 0 }}>
                      <div style={{
                        width: 28,
                        height: 28,
                        borderRadius: 7,
                        background: isScanningThis 
                          ? 'rgba(139, 92, 246, 0.18)' 
                          : hasRisks 
                          ? 'rgba(239, 68, 68, 0.12)' 
                          : 'rgba(34, 197, 94, 0.1)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: isScanningThis ? '#8b5cf6' : hasRisks ? '#ef4444' : '#16a34a',
                        flexShrink: 0,
                      }}>
                        <Icon size={15} />
                      </div>
                      <div style={{ minWidth: 0, overflow: 'hidden' }}>
                        <div style={{ fontSize: 13, color: 'var(--text-primary)', fontWeight: 800, lineHeight: 1.1 }}>
                          {d.code}
                        </div>
                        <div style={{ fontSize: 9.5, color: 'var(--text-muted)', fontWeight: 600, marginTop: 1, letterSpacing: '0.02em' }}>
                          0{idx + 1}
                        </div>
                      </div>
                    </div>

                    {/* Status Badge: Crisp, Single-Line, Never Wraps! */}
                    {isScanningThis ? (
                      <span style={{
                        fontSize: 9.5,
                        fontWeight: 800,
                        padding: '2px 6px',
                        borderRadius: 12,
                        background: 'rgba(139, 92, 246, 0.18)',
                        color: '#8b5cf6',
                        border: '1px solid rgba(139, 92, 246, 0.4)',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 2,
                        whiteSpace: 'nowrap',
                        flexShrink: 0,
                      }}>
                        <span className="spin"><RefreshCw size={8} /></span>
                        Audit
                      </span>
                    ) : hasRisks ? (
                      <span style={{
                        fontSize: 10,
                        fontWeight: 800,
                        padding: '2px 7px',
                        borderRadius: 12,
                        background: 'rgba(239, 68, 68, 0.14)',
                        color: '#dc2626',
                        border: '1px solid rgba(239, 68, 68, 0.3)',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 3,
                        whiteSpace: 'nowrap',
                        flexShrink: 0,
                      }}>
                        <AlertTriangle size={10} />
                        {deptAlerts.length}
                      </span>
                    ) : (
                      <span style={{
                        fontSize: 9.5,
                        fontWeight: 700,
                        padding: '2px 6px',
                        borderRadius: 12,
                        background: 'rgba(34, 197, 94, 0.12)',
                        color: '#16a34a',
                        border: '1px solid rgba(34, 197, 94, 0.25)',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 2,
                        whiteSpace: 'nowrap',
                        flexShrink: 0,
                      }}>
                        <Check size={9} strokeWidth={3} />
                        Clear
                      </span>
                    )}
                  </div>

                  {/* Card Middle: Title & Scope */}
                  <div>
                    <div style={{
                      fontSize: 11.5,
                      fontWeight: 700,
                      color: 'var(--text-primary)',
                      marginBottom: 2,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis'
                    }}>
                      {d.name}
                    </div>
                    <div style={{
                      fontSize: 10,
                      color: 'var(--text-secondary)',
                      lineHeight: 1.3,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis'
                    }}>
                      {d.desc}
                    </div>
                  </div>

                  {/* Card Bottom: Micro Status Dot */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 4, paddingTop: 4, borderTop: '1px solid rgba(0,0,0,0.03)' }}>
                    <span style={{
                      fontSize: 9.5,
                      fontWeight: 700,
                      color: hasRisks ? '#dc2626' : '#16a34a',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 4
                    }}>
                      <span style={{
                        width: 5,
                        height: 5,
                        borderRadius: '50%',
                        background: hasRisks ? '#dc2626' : '#16a34a'
                      }} />
                      {hasRisks ? `${deptAlerts.length} Active` : 'Nominal'}
                    </span>
                    <span style={{ fontSize: 9.5, color: isSelected ? 'var(--brand-purple)' : 'var(--text-muted)', fontWeight: 600 }}>
                      {isSelected ? 'Inspecting' : 'Click to inspect'}
                    </span>
                  </div>
                </div>

                {/* 2. ARROW MARKED FLOW CONNECTOR WITH CONNECTIVITY BEAM */}
                {!isLast && (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      position: 'relative',
                      width: 24,
                      flexShrink: 0,
                      height: '100%',
                      margin: '0 1px',
                    }}
                  >
                    {/* Horizontal connection line */}
                    <div
                      style={{
                        position: 'absolute',
                        top: '50%',
                        left: 0,
                        right: 0,
                        height: 2,
                        background: isFlowConnecting
                          ? 'linear-gradient(90deg, #8b5cf6, #3b82f6)'
                          : isFlowPassed
                          ? 'rgba(139, 92, 246, 0.35)'
                          : 'var(--line)',
                        zIndex: 1,
                        transition: 'all 0.3s ease',
                      }}
                    >
                      {/* Active traveling pulse when flowing */}
                      {isFlowConnecting && (
                        <div
                          style={{
                            position: 'absolute',
                            top: -2,
                            left: 0,
                            width: 12,
                            height: 6,
                            background: '#a855f7',
                            borderRadius: 3,
                            boxShadow: '0 0 10px #a855f7, 0 0 4px #c084fc',
                            animation: 'flowLaser 0.5s infinite linear',
                          }}
                        />
                      )}
                    </div>

                    {/* Arrow circle badge */}
                    <div
                      style={{
                        width: 18,
                        height: 18,
                        borderRadius: '50%',
                        background: isFlowConnecting
                          ? 'linear-gradient(135deg, #8b5cf6, #3b82f6)'
                          : isFlowPassed
                          ? 'rgba(139, 92, 246, 0.15)'
                          : 'var(--surface-hi)',
                        border: isFlowConnecting
                          ? '2px solid #a855f7'
                          : isFlowPassed
                          ? '1.5px solid rgba(139, 92, 246, 0.45)'
                          : '1px solid var(--line)',
                        color: isFlowConnecting
                          ? 'white'
                          : isFlowPassed
                          ? 'var(--brand-purple)'
                          : 'var(--text-muted)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        zIndex: 2,
                        boxShadow: isFlowConnecting
                          ? '0 0 10px rgba(139, 92, 246, 0.6)'
                          : '0 1px 2px rgba(0,0,0,0.03)',
                        transition: 'all 0.25s ease',
                      }}
                      title={`Conduit Flow: ${d.code} → ${nextDept?.code}`}
                    >
                      <ArrowRight size={9} className={isFlowConnecting ? 'animate-pulse' : ''} />
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* 3. MASTER OPERATIONAL RISK RADAR & TRIAGE CENTER */}
      <div 
        id="risk-alerts-feed-section" 
        className="card" 
        style={{ 
          padding: 22, 
          background: 'var(--surface-hi)', 
          border: '1px solid var(--line)', 
          borderRadius: 14,
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
          boxShadow: '0 2px 8px rgba(0,0,0,0.02)'
        }}
      >
        {/* ACTION SUCCESS BANNER */}
        {actionSuccessMsg && (
          <div
            style={{
              padding: '10px 16px',
              borderRadius: 8,
              background: 'rgba(34, 197, 94, 0.1)',
              border: '1px solid rgba(34, 197, 94, 0.3)',
              color: '#16a34a',
              fontSize: 12.5,
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <CheckCircle2 size={16} />
            <span>{actionSuccessMsg}</span>
          </div>
        )}

        {/* ACTIVE ORDER FILTER NOTIFICATION */}
        {activeOrderFilter && (
          <div
            style={{
              padding: '10px 14px',
              borderRadius: 8,
              background: 'rgba(111, 61, 186, 0.08)',
              border: '1px solid rgba(111, 61, 186, 0.25)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              fontSize: 12,
              color: 'var(--brand-purple)',
              fontWeight: 600,
            }}
          >
            <span>Filtered alerts for Order <strong>#{activeOrderFilter}</strong></span>
            <button
              type="button"
              onClick={() => setActiveOrderFilter('')}
              className="button button-secondary"
              style={{ fontSize: 11, padding: '3px 8px' }}
            >
              Show All Orders
            </button>
          </div>
        )}

        {/* HEADER BAR: TITLE, ACTIVE SCOPE & FILTERS */}
        {(() => {
          const isDeptFiltered = selectedDept !== 'ALL'
          const activeDeptObj = isDeptFiltered ? depts.find((d) => d.code === selectedDept) : null
          const DeptIcon = activeDeptObj?.icon || BellRing

          return (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div
                  style={{
                    width: 38,
                    height: 38,
                    borderRadius: 10,
                    background: isDeptFiltered
                      ? (filteredAlerts.length > 0 ? 'rgba(239, 68, 68, 0.1)' : 'rgba(34, 197, 94, 0.1)')
                      : 'rgba(111, 61, 186, 0.1)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: isDeptFiltered
                      ? (filteredAlerts.length > 0 ? '#ef4444' : '#16a34a')
                      : 'var(--brand-purple)',
                    flexShrink: 0,
                  }}
                >
                  <DeptIcon size={20} />
                </div>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <h3 style={{ fontSize: 16, fontWeight: 800, margin: 0, color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>
                      {isDeptFiltered ? `${selectedDept} · ${activeDeptObj?.name}` : 'Operational Risk Radar & Triage Center'}
                    </h3>
                    <span
                      style={{
                        fontSize: 11,
                        fontWeight: 800,
                        padding: '2px 9px',
                        borderRadius: 12,
                        background: filteredAlerts.length > 0 ? 'rgba(239, 68, 68, 0.12)' : 'rgba(34, 197, 94, 0.12)',
                        color: filteredAlerts.length > 0 ? '#dc2626' : '#16a34a',
                        border: filteredAlerts.length > 0 ? '1px solid rgba(239, 68, 68, 0.25)' : '1px solid rgba(34, 197, 94, 0.25)',
                      }}
                    >
                      {filteredAlerts.length > 0
                        ? `${filteredAlerts.length} ${filteredAlerts.length === 1 ? 'Active Risk' : 'Active Risks'}`
                        : '✓ 100% Operational Health'}
                    </span>
                  </div>
                  <p style={{ margin: '3px 0 0', fontSize: 12, color: 'var(--text-secondary)' }}>
                    {isDeptFiltered
                      ? `Operational surveillance alerts detected in ${selectedDept} conduit (${activeDeptObj?.desc}).`
                      : `Continuous multi-department operational anomaly detection across all 7 monitored plant conduits.`}
                  </p>
                </div>
              </div>

              {/* FILTER CONTROLS: DEPARTMENT PILLS & STATUS TABS */}
              <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                {/* Department quick pills */}
                <div style={{ display: 'flex', gap: 4, alignItems: 'center', background: 'var(--kg-bg-2)', padding: '3px 4px', borderRadius: 8, border: '1px solid var(--line)' }}>
                  <button
                    type="button"
                    onClick={() => setSelectedDept('ALL')}
                    style={{
                      border: 0,
                      background: selectedDept === 'ALL' ? 'var(--surface-hi)' : 'transparent',
                      color: selectedDept === 'ALL' ? 'var(--brand-purple)' : 'var(--text-muted)',
                      fontWeight: selectedDept === 'ALL' ? 700 : 500,
                      fontSize: 11,
                      padding: '4px 8px',
                      borderRadius: 6,
                      cursor: 'pointer',
                      boxShadow: selectedDept === 'ALL' ? '0 1px 3px rgba(0,0,0,0.06)' : 'none',
                    }}
                  >
                    All ({alerts.length})
                  </button>
                  {depts.map((d) => {
                    const count = alerts.filter((a) => a.department === d.code && a.status === 'OPEN').length
                    const isSel = selectedDept === d.code
                    return (
                      <button
                        key={d.code}
                        type="button"
                        onClick={() => setSelectedDept(isSel ? 'ALL' : d.code)}
                        style={{
                          border: 0,
                          background: isSel ? 'var(--surface-hi)' : 'transparent',
                          color: isSel ? (count > 0 ? '#dc2626' : 'var(--brand-purple)') : 'var(--text-muted)',
                          fontWeight: isSel ? 700 : 500,
                          fontSize: 11,
                          padding: '4px 7px',
                          borderRadius: 6,
                          cursor: 'pointer',
                          boxShadow: isSel ? '0 1px 3px rgba(0,0,0,0.06)' : 'none',
                        }}
                      >
                        {d.code} {count > 0 && <span style={{ color: '#dc2626', fontWeight: 800 }}>({count})</span>}
                      </button>
                    )
                  })}
                </div>

                {/* Status tabs */}
                <div style={{ display: 'flex', gap: 4, alignItems: 'center', background: 'var(--kg-bg-2)', padding: '3px 4px', borderRadius: 8, border: '1px solid var(--line)' }}>
                  {['ALL', 'OPEN', 'ACKNOWLEDGED', 'RESOLVED'].map((st) => (
                    <button
                      key={st}
                      type="button"
                      onClick={() => setSelectedStatus(st)}
                      style={{
                        border: 0,
                        background: selectedStatus === st ? 'var(--surface-hi)' : 'transparent',
                        color: selectedStatus === st ? 'var(--brand-purple)' : 'var(--text-muted)',
                        fontWeight: selectedStatus === st ? 700 : 500,
                        fontSize: 11,
                        padding: '4px 8px',
                        borderRadius: 6,
                        cursor: 'pointer',
                        boxShadow: selectedStatus === st ? '0 1px 3px rgba(0,0,0,0.06)' : 'none',
                      }}
                    >
                      {st}
                    </button>
                  ))}
                </div>

                {isDeptFiltered && (
                  <button
                    type="button"
                    onClick={() => setSelectedDept('ALL')}
                    className="button button-secondary"
                    style={{ fontSize: 11, padding: '5px 10px', display: 'flex', alignItems: 'center', gap: 4 }}
                  >
                    <X size={12} /> Show All
                  </button>
                )}
              </div>
            </div>
          )
        })()}

        {/* RISK CARDS GRID OR REASSURING EMPTY STATE */}
        {filteredAlerts.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', background: 'var(--kg-bg-2)', borderRadius: 12, border: '1px solid var(--line)' }}>
            <CheckCircle2 size={38} color="#16a34a" style={{ margin: '0 auto 10px' }} />
            <h4 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: 'var(--text-primary)' }}>
              No Operational Risks Detected
            </h4>
            <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: '4px 0 14px' }}>
              {selectedDept !== 'ALL'
                ? `Department ${selectedDept} operational tolerances, work orders, cycle times, and schedules are verified 100% clear.`
                : 'All monitored manufacturing conduits are operating within designated tolerances with zero active breaches.'}
            </p>
            {selectedDept !== 'ALL' && (
              <button
                type="button"
                className="button button-secondary"
                onClick={() => setSelectedDept('ALL')}
                style={{ fontSize: 12, padding: '6px 14px' }}
              >
                View All Monitored Departments
              </button>
            )}
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 14 }}>
            {filteredAlerts.map((alert) => {
              const breachBadge = extractBreachBadge(alert.description)
              const isCrit = alert.severity === 'CRITICAL'

              return (
                <div
                  key={alert.id}
                  style={{
                    background: 'var(--surface-hi)',
                    border: isCrit ? '1px solid rgba(239, 68, 68, 0.35)' : '1px solid var(--line)',
                    borderLeft: isCrit ? '4px solid #ef4444' : '4px solid var(--brand-purple)',
                    borderRadius: 12,
                    padding: 16,
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    gap: 12,
                    boxShadow: '0 2px 8px rgba(0,0,0,0.03)',
                    transition: 'all 0.18s ease',
                  }}
                >
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {/* Top row: ID, Dept, Order Link, Breach Badge & Severity */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8, flexWrap: 'wrap' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                        <span style={{ fontSize: 10.5, fontWeight: 700, color: 'var(--text-muted)' }}>
                          #{alert.id}
                        </span>
                        <span
                          style={{
                            fontSize: 10,
                            fontWeight: 800,
                            padding: '2px 7px',
                            borderRadius: 6,
                            background: 'rgba(111, 61, 186, 0.1)',
                            color: 'var(--brand-purple)',
                            border: '1px solid rgba(111, 61, 186, 0.25)',
                          }}
                        >
                          [{alert.department}]
                        </span>
                        <Link
                          to={`/orders/${encodeURIComponent(alert.customer_order_id)}`}
                          style={{
                            fontWeight: 800,
                            fontSize: 13,
                            color: 'var(--brand-purple)',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 3,
                            textDecoration: 'none',
                          }}
                          title="Open Order Details"
                        >
                          {alert.customer_order_id} <ArrowUpRight size={12} />
                        </Link>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        {breachBadge && (
                          <span
                            style={{
                              fontSize: 10,
                              fontWeight: 800,
                              padding: '2px 8px',
                              borderRadius: 6,
                              background: 'rgba(239, 68, 68, 0.14)',
                              color: '#dc2626',
                              border: '1px solid rgba(239, 68, 68, 0.3)',
                              letterSpacing: '0.02em',
                            }}
                          >
                            {breachBadge}
                          </span>
                        )}
                        {getSeverityBadge(alert.severity)}
                        {alert.result_source && (
                          <span
                            style={{
                              fontSize: 10,
                              fontWeight: 700,
                              padding: '2px 7px',
                              borderRadius: 4,
                              background:
                                alert.result_source === 'AGENT'
                                  ? 'rgba(34, 197, 94, 0.12)'
                                  : alert.result_source === 'RULES'
                                  ? 'rgba(59, 130, 246, 0.12)'
                                  : 'rgba(245, 158, 11, 0.12)',
                              color:
                                alert.result_source === 'AGENT'
                                  ? '#16a34a'
                                  : alert.result_source === 'RULES'
                                  ? '#2563eb'
                                  : '#d97706',
                            }}
                            title={`Result produced by: ${alert.result_source}`}
                          >
                            {alert.result_source === 'AGENT' ? 'AI Agent' : alert.result_source === 'RULES' ? 'Rule Engine' : 'Rules Fallback'}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Alert Title */}
                    <div style={{ fontSize: 13.5, fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1.35 }}>
                      {alert.title || alert.risk_category}
                    </div>

                    {/* Alert Description */}
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.48 }}>
                      {alert.description}
                    </div>

                    {/* Agent 3 Mitigation Callout */}
                    {alert.recommended_action && (
                      <div
                        style={{
                          fontSize: 11.5,
                          color: 'var(--text-primary)',
                          background: 'rgba(245, 158, 11, 0.08)',
                          padding: '9px 12px',
                          borderRadius: 8,
                          border: '1px solid rgba(245, 158, 11, 0.24)',
                          lineHeight: 1.45,
                        }}
                      >
                        <div
                          style={{
                            color: '#d97706',
                            fontWeight: 800,
                            fontSize: 10.5,
                            display: 'flex',
                            alignItems: 'center',
                            gap: 5,
                            marginBottom: 4,
                            letterSpacing: '0.04em',
                            textTransform: 'uppercase',
                          }}
                        >
                          <Zap size={13} color="#d97706" /> Agent 3 Mitigation Proposal
                        </div>
                        <div>{alert.recommended_action}</div>
                      </div>
                    )}

                    {/* Assigned Owner or Resolution Notes */}
                    {(alert.assigned_owner || alert.resolution_notes) && (
                      <div
                        style={{
                          fontSize: 11.5,
                          padding: '8px 12px',
                          borderRadius: 6,
                          background: 'var(--kg-bg-2)',
                          border: '1px solid var(--line)',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: 4,
                        }}
                      >
                        {alert.assigned_owner && (
                          <div>
                            <strong style={{ color: 'var(--brand-purple)', fontSize: 11 }}>OWNER: </strong>
                            <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{alert.assigned_owner}</span>
                          </div>
                        )}
                        {alert.resolution_notes && (
                          <div>
                            <strong style={{ color: '#16a34a', fontSize: 11 }}>RESOLUTION: </strong>
                            <span style={{ color: 'var(--text-primary)' }}>{alert.resolution_notes}</span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Actions Footer */}
                  <div>
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        paddingTop: 10,
                        borderTop: '1px solid var(--line)',
                        fontSize: 11,
                        flexWrap: 'wrap',
                        gap: 8,
                      }}
                    >
                      <span style={{ color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                        <Clock size={12} /> {formatDate(alert.detected_at)}
                      </span>

                      <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                        {alert.status !== 'RESOLVED' && (
                          <button
                            type="button"
                            className="button button-secondary"
                            onClick={() => handleDispatchNotification(alert.id)}
                            disabled={dispatchingAlertId === alert.id}
                            style={{
                              fontSize: 11,
                              padding: '4px 9px',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: 5,
                              color: 'var(--brand-purple)',
                              borderColor: 'var(--brand-purple)',
                            }}
                            title="Dispatch alert notification to customer service and department lead"
                          >
                            <Send size={11} /> {dispatchingAlertId === alert.id ? 'Dispatching...' : 'Dispatch Email'}
                          </button>
                        )}

                        {alert.status === 'OPEN' && (
                          <button
                            type="button"
                            className="button button-secondary"
                            onClick={() => handleAcknowledge(alert.id)}
                            style={{ fontSize: 11, padding: '4px 9px', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                          >
                            <UserCheck size={12} /> Acknowledge
                          </button>
                        )}

                        {alert.status !== 'RESOLVED' && (
                          <>
                            <button
                              type="button"
                              className="button button-secondary"
                              onClick={() =>
                                setActiveActionModal(
                                  activeActionModal?.alertId === alert.id && activeActionModal?.type === 'assign'
                                    ? null
                                    : { type: 'assign', alertId: alert.id }
                                )
                              }
                              style={{ fontSize: 11, padding: '4px 9px' }}
                            >
                              Assign
                            </button>
                            <button
                              type="button"
                              className="button button-secondary"
                              onClick={() =>
                                setActiveActionModal(
                                  activeActionModal?.alertId === alert.id && activeActionModal?.type === 'resolve'
                                    ? null
                                    : { type: 'resolve', alertId: alert.id }
                                )
                              }
                              style={{
                                fontSize: 11,
                                padding: '4px 9px',
                                color: '#16a34a',
                                borderColor: 'rgba(22, 163, 74, 0.35)',
                              }}
                            >
                              Resolve
                            </button>
                          </>
                        )}

                        <Link
                          to={`/orders/${encodeURIComponent(alert.customer_order_id)}`}
                          className="button button-secondary"
                          style={{
                            fontSize: 11,
                            padding: '4px 9px',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 3,
                            textDecoration: 'none',
                          }}
                        >
                          <Eye size={12} /> View
                        </Link>
                      </div>
                    </div>

                    {/* Inline Action Trays for Assign / Resolve */}
                    {activeActionModal?.alertId === alert.id && (
                      <div
                        style={{
                          marginTop: 10,
                          padding: 12,
                          background: 'var(--kg-bg-2)',
                          borderRadius: 8,
                          border: '1px solid var(--line)',
                        }}
                      >
                        {activeActionModal.type === 'assign' ? (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                            <span style={{ fontSize: 11.5, fontWeight: 700, color: 'var(--text-primary)' }}>
                              Assign Operational Lead for Alert #{alert.id} ({alert.department}):
                            </span>
                            <div style={{ display: 'flex', gap: 6 }}>
                              <input
                                type="text"
                                placeholder="Enter owner name (e.g. ERP Lead, MMS Planner)..."
                                value={assigneeInput[alert.id] || ''}
                                onChange={(e) => setAssigneeInput({ ...assigneeInput, [alert.id]: e.target.value })}
                                style={{
                                  flex: 1,
                                  padding: '6px 10px',
                                  borderRadius: 6,
                                  border: '1px solid var(--line)',
                                  background: 'var(--surface-hi)',
                                  color: 'var(--text-primary)',
                                  fontSize: 11.5,
                                  outline: 'none',
                                }}
                              />
                              <button
                                type="button"
                                className="button button-primary"
                                onClick={() => handleAssign(alert.id)}
                                style={{ fontSize: 11.5, padding: '6px 12px' }}
                              >
                                Save
                              </button>
                              <button
                                type="button"
                                className="button button-secondary"
                                onClick={() => setActiveActionModal(null)}
                                style={{ fontSize: 11.5, padding: '6px 10px' }}
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                            <span style={{ fontSize: 11.5, fontWeight: 700, color: 'var(--text-primary)' }}>
                              Record Corrective Action and Resolve Alert #{alert.id}:
                            </span>
                            <div style={{ display: 'flex', gap: 6 }}>
                              <input
                                type="text"
                                placeholder="Describe corrective action taken with supporting evidence..."
                                value={resolutionInput[alert.id] || ''}
                                onChange={(e) => setResolutionInput({ ...resolutionInput, [alert.id]: e.target.value })}
                                style={{
                                  flex: 1,
                                  padding: '6px 10px',
                                  borderRadius: 6,
                                  border: '1px solid var(--line)',
                                  background: 'var(--surface-hi)',
                                  color: 'var(--text-primary)',
                                  fontSize: 11.5,
                                  outline: 'none',
                                }}
                              />
                              <button
                                type="button"
                                className="button button-primary"
                                onClick={() => handleResolve(alert.id)}
                                style={{
                                  background: '#16a34a',
                                  borderColor: '#16a34a',
                                  fontSize: 11.5,
                                  padding: '6px 12px',
                                }}
                              >
                                Resolve
                              </button>
                              <button
                                type="button"
                                className="button button-secondary"
                                onClick={() => setActiveActionModal(null)}
                                style={{ fontSize: 11.5, padding: '6px 10px' }}
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* AGENT 3 REASONING & SURVEILLANCE RUN TRACE */}
      <div className="card" style={{ padding: 18, borderRadius: 12 }}>
        <div
          onClick={() => setShowAgent3Trace((v) => !v)}
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            cursor: 'pointer',
            userSelect: 'none',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Cpu size={16} color="var(--brand-purple)" />
            <h3 style={{ fontSize: 13.5, fontWeight: 800, margin: 0, color: 'var(--text-primary)' }}>
              Agent 3 Reasoning &amp; Surveillance Execution Trace
            </h3>
            <span
              className="mfg-badge"
              style={{
                fontSize: 10,
                background: 'rgba(111, 61, 186, 0.12)',
                color: 'var(--brand-purple)',
              }}
            >
              {agent3Runs.length} Surveillance Runs
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-muted)' }}>
            <span>{showAgent3Trace ? 'Hide Trace' : 'View Trace'}</span>
            {showAgent3Trace ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </div>
        </div>

        {showAgent3Trace && (
          <div style={{ marginTop: 14, paddingTop: 14, borderTop: '1px solid var(--line)' }}>
            {agent3Runs.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {agent3Runs.map((run) => (
                  <div
                    key={run.id}
                    style={{
                      padding: '12px 14px',
                      background: 'var(--kg-bg-2)',
                      borderRadius: 8,
                      border: '1px solid var(--line)',
                      fontSize: 12,
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                      <span style={{ fontWeight: 700, color: 'var(--brand-purple)' }}>
                        Run #{run.id} · Order #{run.customer_order_id}
                      </span>
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 700,
                          padding: '2px 8px',
                          borderRadius: 6,
                          background: run.status === 'success' ? 'rgba(34, 197, 94, 0.12)' : 'rgba(245, 158, 11, 0.12)',
                          color: run.status === 'success' ? '#16a34a' : '#d97706',
                        }}
                      >
                        Status: {run.status} ({run.provider})
                      </span>
                    </div>
                    {Array.isArray(run.steps) && run.steps.length > 0 ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
                        {run.steps.map((s, sIdx) => {
                          const tName = s.tool || s.action
                          const tInput = s.input || s.action_input
                          const tOutput = s.output || s.observation
                          const isErr = s.status === 'error' || Boolean(tOutput && typeof tOutput === 'object' && tOutput.error)
                          const stepKey = `${run.id}-${sIdx}`
                          const isExp = expandedA3Steps[stepKey]

                          return (
                            <div
                              key={sIdx}
                              style={{
                                padding: 10,
                                background: isErr ? 'rgba(239, 68, 68, 0.05)' : 'var(--surface-hi)',
                                borderRadius: 6,
                                border: `1px solid ${isErr ? '#ef4444' : 'var(--line)'}`,
                              }}
                            >
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <span style={{ fontWeight: 700, color: isErr ? '#dc2626' : 'var(--text-primary)' }}>
                                  Step {s.step || sIdx + 1}: {tName || 'Action'}
                                </span>
                              </div>
                              {s.thought && (
                                <p style={{ margin: '4px 0', color: 'var(--text-secondary)' }}>
                                  <strong>Thought:</strong> {s.thought}
                                </p>
                              )}
                              {tInput && (
                                <div style={{ fontSize: 11, color: 'var(--text-muted)', margin: '4px 0' }}>
                                  <strong>Input:</strong> <code>{typeof tInput === 'object' ? JSON.stringify(tInput) : String(tInput)}</code>
                                </div>
                              )}
                              {tOutput && (
                                <div
                                  style={{
                                    padding: '4px 8px',
                                    background: isErr ? 'rgba(239, 68, 68, 0.08)' : 'rgba(0,0,0,0.03)',
                                    borderRadius: 4,
                                    fontSize: 11,
                                    color: isErr ? '#b91c1c' : 'var(--text-primary)',
                                    maxHeight: isExp ? 'none' : 100,
                                    overflowY: isExp ? 'visible' : 'auto',
                                  }}
                                >
                                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 }}>
                                    <strong>Output:</strong>
                                    {JSON.stringify(tOutput).length > 200 && (
                                      <button
                                        type="button"
                                        onClick={() => setExpandedA3Steps((prev) => ({ ...prev, [stepKey]: !prev[stepKey] }))}
                                        style={{ background: 'none', border: 'none', color: 'var(--brand-purple)', cursor: 'pointer', fontSize: 10 }}
                                      >
                                        {isExp ? 'Collapse' : 'Expand full output'}
                                      </button>
                                    )}
                                  </div>
                                  <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'inherit' }}>
                                    {typeof tOutput === 'object' ? JSON.stringify(tOutput, null, 2) : String(tOutput)}
                                  </pre>
                                </div>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    ) : (
                      <p style={{ margin: '4px 0 0', color: 'var(--text-muted)', fontStyle: 'italic', fontSize: 11 }}>
                        No step observations recorded for this run.
                      </p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ margin: 0, color: 'var(--text-muted)', fontStyle: 'italic', fontSize: 12 }}>
                No recorded Agent 3 execution runs found.
              </p>
            )}
          </div>
        )}
      </div>

      {/* 4.5. AGENT CORRECTIVE ACTIONS PANEL (EXCEPTION CENTER) */}
      <div id="agent-actions-panel" className="card" style={{ padding: 22, background: 'var(--surface-hi)', border: '1px solid var(--line)', borderRadius: 14 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h3 style={{ fontSize: 15, fontWeight: 800, margin: 0, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--brand-purple)', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Zap size={18} color="#f59e0b" /> Agent Actions · Recommended Corrective Actions
            </h3>
            <span style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2, display: 'inline-block' }}>
              Operational mitigations recommended by Agent 3 — Human Review Required ({actions.filter((a) => a.status === 'PROPOSED').length} awaiting human review)
            </span>
          </div>

          <div style={{ display: 'flex', gap: 6, alignItems: 'center', background: 'var(--kg-bg-2)', padding: 4, borderRadius: 8, border: '1px solid var(--line)' }}>
            {['ALL', 'PROPOSED', 'EXECUTED', 'REJECTED'].map((st) => (
              <button
                key={st}
                type="button"
                onClick={() => setActionFilter(st)}
                style={{
                  border: 0,
                  background: actionFilter === st ? 'var(--surface-hi)' : 'transparent',
                  color: actionFilter === st ? 'var(--brand-purple)' : 'var(--text-muted)',
                  fontWeight: actionFilter === st ? 700 : 500,
                  fontSize: 11,
                  padding: '5px 10px',
                  borderRadius: 6,
                  cursor: 'pointer',
                  boxShadow: actionFilter === st ? '0 1px 3px rgba(0,0,0,0.06)' : 'none',
                  transition: 'all 0.15s ease',
                }}
              >
                {st} {st !== 'ALL' && `(${actions.filter((a) => a.status === st).length})`}
              </button>
            ))}
          </div>
        </div>

        {filteredActions.length === 0 ? (
          <div style={{ padding: 26, textAlign: 'center', color: 'var(--text-secondary)' }}>
            <CheckCircle2 size={30} color="#16a34a" style={{ margin: '0 auto 8px' }} />
            <p style={{ margin: 0, fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
              No Agent Actions Found
            </p>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '4px 0 0' }}>
              {actionFilter !== 'ALL' ? `No corrective actions in ${actionFilter} status.` : 'When Agent 3 detects order risks, corrective actions will be proposed here.'}
            </p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {filteredActions.map((action) => {
              const isProposed = action.status === 'PROPOSED'
              const isSubmitting = !!actionSubmitting[action.id]
              return (
                <div
                  key={action.id}
                  style={{
                    padding: 16,
                    borderRadius: 10,
                    background: 'var(--surface-hi)',
                    border: isProposed ? '1px solid rgba(245, 158, 11, 0.4)' : '1px solid var(--line)',
                    boxShadow: '0 1px 4px rgba(0,0,0,0.02)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 10,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                      <span
                        style={{
                          fontSize: 11,
                          fontWeight: 800,
                          padding: '3px 8px',
                          borderRadius: 6,
                          background:
                            action.action_type === 'REQUEST_EXPEDITE'
                              ? 'rgba(245, 158, 11, 0.15)'
                              : action.action_type === 'REQUEST_REASSESSMENT'
                              ? 'rgba(111, 61, 186, 0.15)'
                              : action.action_type === 'REQUEST_CARRIER_UPGRADE'
                              ? 'rgba(59, 130, 246, 0.15)'
                              : 'rgba(16, 185, 129, 0.15)',
                          color:
                            action.action_type === 'REQUEST_EXPEDITE'
                              ? '#b45309'
                              : action.action_type === 'REQUEST_REASSESSMENT'
                              ? 'var(--brand-purple)'
                              : action.action_type === 'REQUEST_CARRIER_UPGRADE'
                              ? '#2563eb'
                              : '#059669',
                          textTransform: 'uppercase',
                        }}
                      >
                        {action.action_type.replace(/_/g, ' ')}
                      </span>

                      <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
                        Action #{action.id} · Order{' '}
                        <Link
                          to={`/orders/${action.customer_order_id}`}
                          style={{ color: 'var(--brand-purple)', textDecoration: 'none', fontWeight: 800 }}
                        >
                          #{action.customer_order_id}
                        </Link>
                      </span>

                      {action.alert_id && (
                        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                          (Linked to Alert #{action.alert_id})
                        </span>
                      )}
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      {/* TASK 3: LABEL AUTO-EXECUTED ACTIONS */}
                      {(action.approved_by === 'SYSTEM_AUTO_EXECUTE' || (!action.requires_approval && action.status === 'EXECUTED')) ? (
                        <span
                          style={{
                            fontSize: 10,
                            fontWeight: 800,
                            padding: '2px 8px',
                            borderRadius: 10,
                            background: 'rgba(111, 61, 186, 0.12)',
                            color: 'var(--brand-purple)',
                            border: '1px solid rgba(111, 61, 186, 0.3)',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 3,
                          }}
                        >
                          ⚡ Auto-Executed (Agent 3 Policy)
                        </span>
                      ) : (
                        <span
                          style={{
                            fontSize: 10,
                            fontWeight: 700,
                            padding: '2px 8px',
                            borderRadius: 10,
                            background: action.requires_approval ? 'rgba(245, 158, 11, 0.1)' : 'rgba(34, 197, 94, 0.1)',
                            color: action.requires_approval ? '#d97706' : '#16a34a',
                            border: `1px solid ${action.requires_approval ? 'rgba(245, 158, 11, 0.3)' : 'rgba(34, 197, 94, 0.3)'}`,
                          }}
                        >
                          {action.requires_approval ? 'Requires Approval' : 'Manual Approval'}
                        </span>
                      )}

                      <span
                        style={{
                          fontSize: 11,
                          fontWeight: 800,
                          padding: '3px 10px',
                          borderRadius: 12,
                          background:
                            action.status === 'EXECUTED'
                              ? 'rgba(34, 197, 94, 0.12)'
                              : action.status === 'PROPOSED'
                              ? 'rgba(245, 158, 11, 0.12)'
                              : action.status === 'REJECTED'
                              ? 'rgba(100, 116, 139, 0.12)'
                              : 'rgba(239, 68, 68, 0.12)',
                          color:
                            action.status === 'EXECUTED'
                              ? '#16a34a'
                              : action.status === 'PROPOSED'
                              ? '#d97706'
                              : action.status === 'REJECTED'
                              ? '#64748b'
                              : '#dc2626',
                        }}
                      >
                        {action.status}
                      </span>
                    </div>
                  </div>

                  {action.parameters && (
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)', background: 'var(--kg-bg-2)', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--line)' }}>
                      <div><strong>Risk:</strong> {action.parameters.title || action.parameters.risk_category} ({action.parameters.department})</div>
                      {action.parameters.recommended_action && (
                        <div style={{ marginTop: 2 }}><strong>Proposed Directive:</strong> {action.parameters.recommended_action}</div>
                      )}
                      {action.parameters.delivery_impact && (
                        <div style={{ marginTop: 2 }}><strong>Impact:</strong> {action.parameters.delivery_impact}</div>
                      )}
                    </div>
                  )}

                  {/* TASK 3: SHOW FAILED ACTIONS WITH ERROR MESSAGE */}
                  {action.status === 'FAILED' && (
                    <div
                      style={{
                        padding: '10px 14px',
                        borderRadius: 8,
                        background: 'rgba(239, 68, 68, 0.08)',
                        border: '1px solid rgba(239, 68, 68, 0.25)',
                        color: '#dc2626',
                        fontSize: 12,
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: 8,
                      }}
                    >
                      <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: 1 }} />
                      <div>
                        <strong>Action Execution Failed:</strong>{' '}
                        <span>
                          {action.result?.error || action.result?.message || (typeof action.result === 'string' ? action.result : 'Agent execution failed during action processing.')}
                        </span>
                      </div>
                    </div>
                  )}

                  {action.result && action.status !== 'FAILED' && (
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)', background: 'rgba(34, 197, 94, 0.06)', padding: '8px 12px', borderRadius: 8, border: '1px solid rgba(34, 197, 94, 0.2)' }}>
                      <div><strong>Execution Result:</strong> {action.result.message || JSON.stringify(action.result)}</div>
                      {action.result.revised_proposal_id && (
                        <div style={{ marginTop: 4 }}>
                          <Link to={`/my-work?tab=approvals&proposalId=${action.result.revised_proposal_id}`} style={{ color: 'var(--brand-purple)', fontWeight: 700, fontSize: 11, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                            View Revised Proposal #{action.result.revised_proposal_id} in Approvals <ArrowUpRight size={11} />
                          </Link>
                        </div>
                      )}
                    </div>
                  )}

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: 4, flexWrap: 'wrap', gap: 8 }}>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                      Proposed by: <strong>{action.proposed_by}</strong> · {new Date(action.created_at).toLocaleString()}
                      {action.executed_at && ` · Executed: ${new Date(action.executed_at).toLocaleString()}`}
                    </span>

                    {isProposed && (
                      <div style={{ display: 'flex', gap: 8 }}>
                        <button
                          type="button"
                          className="button button-secondary"
                          onClick={() => handleRejectAction(action.id)}
                          disabled={isSubmitting}
                          style={{ fontSize: 12, padding: '5px 12px', color: '#dc2626', borderColor: 'rgba(220, 38, 38, 0.3)' }}
                        >
                          Reject
                        </button>
                        <button
                          type="button"
                          className="button button-primary"
                          onClick={() => handleApproveAction(action.id)}
                          disabled={isSubmitting}
                          style={{ fontSize: 12, padding: '5px 14px', background: '#16a34a', borderColor: '#16a34a', display: 'flex', alignItems: 'center', gap: 4 }}
                        >
                          <Check size={13} /> {isSubmitting ? 'Executing...' : 'Approve & Execute'}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* 5. COMPACT NOTIFICATION OUTBOX BANNER & NAVIGATION */}
      <div
        className="card"
        style={{
          padding: '16px 20px',
          background: 'var(--surface-hi)',
          border: '1px solid var(--line)',
          borderRadius: 12,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 14,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div
            style={{
              width: 38,
              height: 38,
              borderRadius: 10,
              background: 'rgba(111, 61, 186, 0.1)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--brand-purple)',
              position: 'relative',
              flexShrink: 0,
            }}
          >
            <Mail size={18} />
            <span
              style={{
                position: 'absolute',
                top: -3,
                right: -3,
                width: 14,
                height: 14,
                borderRadius: '50%',
                background: 'var(--brand-purple)',
                color: 'white',
                fontSize: 9,
                fontWeight: 800,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                lineHeight: 1,
              }}
            >
              i
            </span>
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <h4 style={{ margin: 0, fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
                Department &amp; Customer Service Notification Outbox
              </h4>
              <span
                style={{
                  background: 'rgba(111, 61, 186, 0.12)',
                  color: 'var(--brand-purple)',
                  fontWeight: 700,
                  fontSize: 11,
                  padding: '2px 8px',
                  borderRadius: 10,
                }}
              >
                {notifications.length} notification record{notifications.length === 1 ? '' : 's'}
              </span>
            </div>
            <p style={{ margin: '3px 0 0 0', fontSize: 12, color: 'var(--text-secondary)' }}>
              Live multi-department recipient routing, delivery audit logs, and message inspection across Customer Service and 7 plant departments.
            </p>
          </div>
        </div>

        <Link
          to="/monitoring/outbox"
          className="button button-primary"
          style={{
            fontSize: 12,
            padding: '8px 16px',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            textDecoration: 'none',
            fontWeight: 600,
            background: 'linear-gradient(135deg, var(--brand-purple), var(--dr-purple))',
            color: 'white',
            borderRadius: 8,
            boxShadow: '0 2px 6px rgba(111, 61, 186, 0.2)',
          }}
        >
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <Mail size={14} />
            <span
              style={{
                position: 'absolute',
                top: -5,
                right: -5,
                width: 8,
                height: 8,
                borderRadius: '50%',
                background: 'white',
                color: 'var(--brand-purple)',
                fontSize: 6,
                fontWeight: 900,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              i
            </span>
          </div>
          <span>Open Notification Outbox</span>
          <ExternalLink size={13} />
        </Link>
      </div>

      {/* EMAIL PREVIEW MODAL */}
      {selectedEmailPreview && (
        <div style={{
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
          padding: 20
        }}>
          <div className="card" style={{
            background: 'var(--surface-hi)',
            border: '1px solid var(--line)',
            borderRadius: 14,
            maxWidth: 700,
            width: '100%',
            maxHeight: '85vh',
            display: 'flex',
            flexDirection: 'column',
            boxShadow: '0 10px 40px rgba(0,0,0,0.2)'
          }}>
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--line)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Mail size={18} style={{ color: 'var(--brand-purple)' }} />
                <strong style={{ fontSize: 15, color: 'var(--text-primary)' }}>Email Notification Inspection #{selectedEmailPreview.id}</strong>
              </div>
              <button
                type="button"
                className="button button-secondary"
                onClick={() => setSelectedEmailPreview(null)}
                style={{ padding: '4px 10px', fontSize: 12 }}
              >
                Close
              </button>
            </div>

            <div style={{ padding: 20, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 8, fontSize: 12 }}>
                <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Recipient:</span>
                <span style={{ fontFamily: 'monospace', fontWeight: 700, color: 'var(--text-primary)' }}>{selectedEmailPreview.recipient_email}</span>

                <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Category:</span>
                <span style={{ color: 'var(--text-primary)' }}>{selectedEmailPreview.recipient_category} ({selectedEmailPreview.department})</span>

                <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Status:</span>
                <span style={{ color: selectedEmailPreview.status === 'SENT' ? '#16a34a' : '#dc2626', fontWeight: 700 }}>
                  {selectedEmailPreview.status} {selectedEmailPreview.sent_at && `at ${new Date(selectedEmailPreview.sent_at).toLocaleString()}`}
                </span>

                <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Subject:</span>
                <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{selectedEmailPreview.subject}</span>
              </div>

              {selectedEmailPreview.failure_reason && (
                <div style={{ padding: 10, borderRadius: 8, background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.25)', color: '#dc2626', fontSize: 12 }}>
                  <strong>Error details:</strong> {selectedEmailPreview.failure_reason}
                </div>
              )}

              <div>
                <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Formatted Email Body:</span>
                <pre style={{
                  marginTop: 6,
                  padding: 14,
                  borderRadius: 8,
                  background: 'var(--kg-bg-2)',
                  border: '1px solid var(--line)',
                  fontSize: 12,
                  fontFamily: 'monospace',
                  color: 'var(--text-primary)',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  lineHeight: 1.5,
                  maxHeight: 350,
                  overflowY: 'auto'
                }}>
                  {selectedEmailPreview.body_text}
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
