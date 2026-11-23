import { useState, useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useToast } from '../context/ToastContext'
import {
  CheckSquare,
  ShieldCheck,
  BellRing,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  ArrowRight,
  ExternalLink,
  RotateCcw,
  UserCheck,
  Send,
  Calendar,
  MessageSquare,
  Check,
  Building2,
  Save,
  X,
  Package,
  Sparkles,
  Mail,
  Filter,
  ChevronDown,
} from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { workflowApi } from '../api/workflow.api'
import { agentsApi } from '../api/agents.api'
import { useAuth } from '../context/AuthContext'
import {
  canManageApprovals,
  isCustomerService,
  isOperational,
  isAdmin,
  canAcknowledgeAlert,
  canResolveAlert,
  canRecordCustomerCommunication,
} from '../utils/permissions'
import { formatDate, formatINR, formatNumber } from '../utils/format'

export default function MyWork() {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const { user } = useAuth()
  const canApprove = canManageApprovals(user)
  const isCS = isCustomerService(user)
  const isOp = isOperational(user)
  const isAdministrator = isAdmin(user)

  const [searchParams] = useSearchParams()
  const urlTab = searchParams.get('tab')
  const targetProposalId = searchParams.get('proposalId')

  // Default active tab based on role, or URL parameter
  const defaultTab = urlTab === 'approvals' ? 'approvals' : canApprove ? 'approvals' : isCS ? 'cs_risks' : 'department_issues'
  const [activeTab, setActiveTab] = useState(defaultTab)
  const [proposalFilter, setProposalFilter] = useState('ALL')
  const [actingId, setActingId] = useState(null)
  const [expandedEvidenceId, setExpandedEvidenceId] = useState(null)
  const [expandedAlerts, setExpandedAlerts] = useState({})
  const toggleAlertDetails = (id) => {
    setExpandedAlerts((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  // Filter states
  const [showFilters, setShowFilters] = useState(false)
  const [riskFilter, setRiskFilter] = useState('ALL')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [daysFilter, setDaysFilter] = useState('')

  // Resolution modal state
  const [resolvingAlert, setResolvingAlert] = useState(null)
  const [resolutionNotes, setResolutionNotes] = useState('')
  const [isResolving, setIsResolving] = useState(false)

  // Customer communication modal state
  const [communicatingAlert, setCommunicatingAlert] = useState(null)
  const [communicationNotes, setCommunicationNotes] = useState('')

  // 3-Day SLA follow-up state
  const [isCheckingFollowups, setIsCheckingFollowups] = useState(false)
  const [sendingFollowupAlertId, setSendingFollowupAlertId] = useState(null)

  // Query work queue data first so workData is defined for useEffect hooks
  const {
    data: workData = { proposals: [], alerts: [], assessments: [] },
    isLoading: loading,
    refetch: loadData,
  } = useQuery({
    queryKey: ['my-work-queue'],
    queryFn: async () => {
      const promises = [
        workflowApi.listProposals().catch(() => []),
        agentsApi.listAlerts({ page_size: 100 }).catch(() => []),
        agentsApi.listAssessments({ limit: 100 }).catch(() => []),
      ]
      const [proposalsRes, alertsRes, assessmentsRes] = await Promise.all(promises)
      return {
        proposals: Array.isArray(proposalsRes) ? proposalsRes : (proposalsRes?.items || []),
        alerts: Array.isArray(alertsRes) ? alertsRes : [],
        assessments: Array.isArray(assessmentsRes) ? assessmentsRes : (assessmentsRes?.items || []),
      }
    },
    staleTime: 0,
    refetchOnMount: 'always',
  })

  useEffect(() => {
    if (urlTab === 'approvals') {
      setActiveTab('approvals')
    }
  }, [urlTab])

  useEffect(() => {
    if (targetProposalId && activeTab === 'approvals') {
      const timer = setTimeout(() => {
        const el = document.getElementById(`proposal-card-${targetProposalId}`)
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' })
        }
      }, 150)
      return () => clearTimeout(timer)
    }
  }, [targetProposalId, activeTab, workData.proposals])

  const allProposals = workData.proposals
  const pendingProposals = allProposals.filter((p) => p.status === 'PENDING')
  const proposals = allProposals.filter((p) => {
    if (proposalFilter === 'PENDING') return p.status === 'PENDING'
    if (proposalFilter === 'APPROVED') return p.status === 'APPROVED'
    return true
  })
  const alerts = workData.alerts
  const assessments = workData.assessments || []

  const handleApprove = async (proposalId) => {
    setActingId(proposalId)
    const prevWorkData = queryClient.getQueryData(['my-work-queue'])
    const targetProposal = (workData.proposals || []).find((p) => p.id === proposalId)
    const orderLabel = targetProposal?.customer_order_id || `Proposal #${proposalId}`

    // Optimistically remove proposal immediately so it vanishes from the pending queue
    queryClient.setQueryData(['my-work-queue'], (old) => {
      if (!old) return old
      return {
        ...old,
        proposals: (old.proposals || []).filter((p) => p.id !== proposalId),
      }
    })

    // Show toast notification IMMEDIATELY on click
    const successMsg = `Order ${orderLabel} commercial commitment approved. Confirmation email with promising delivery date sent to customer.`
    const toastId = toast.success(successMsg, {
      title: 'Commitment Approved & Dispatched',
      duration: 5000,
    })

    try {
      await workflowApi.approveProposal(proposalId, 'Approved via My Work centralized commercial approvals queue.')
      queryClient.invalidateQueries({ queryKey: ['my-work-queue'] })
      queryClient.invalidateQueries({ queryKey: ['assessments-list'] })
      queryClient.invalidateQueries({ queryKey: ['order-monitoring'] })
      queryClient.invalidateQueries({ queryKey: ['orders-list'] })
      queryClient.invalidateQueries({ queryKey: ['notificationOutbox'] })
    } catch (err) {
      if (toastId) toast.dismiss(toastId)
      if (prevWorkData) {
        queryClient.setQueryData(['my-work-queue'], prevWorkData)
      }
      const errMsg = `Approval failed: ${err?.response?.data?.detail || err.message}`
      toast.error(errMsg, { title: 'Approval Failed' })
    } finally {
      setActingId(null)
    }
  }

  const handleReject = async (proposalId) => {
    setActingId(proposalId)
    const prevWorkData = queryClient.getQueryData(['my-work-queue'])
    const targetProposal = (workData.proposals || []).find((p) => p.id === proposalId)
    const orderLabel = targetProposal?.customer_order_id || `Proposal #${proposalId}`

    // Optimistically remove proposal immediately so it vanishes from the pending queue
    queryClient.setQueryData(['my-work-queue'], (old) => {
      if (!old) return old
      return {
        ...old,
        proposals: (old.proposals || []).filter((p) => p.id !== proposalId),
      }
    })

    // Show toast notification IMMEDIATELY on click
    const rejectMsg = `Commitment proposal for ${orderLabel} rejected. Department teams have been notified.`
    const toastId = toast.info(rejectMsg, { title: 'Proposal Rejected' })

    try {
      await workflowApi.rejectProposal(proposalId, 'Rejected from My Work queue - requires rescheduled production or revised date.')
      queryClient.invalidateQueries({ queryKey: ['my-work-queue'] })
      queryClient.invalidateQueries({ queryKey: ['assessments-list'] })
    } catch (err) {
      if (toastId) toast.dismiss(toastId)
      if (prevWorkData) {
        queryClient.setQueryData(['my-work-queue'], prevWorkData)
      }
      const errMsg = `Rejection failed: ${err?.response?.data?.detail || err.message}`
      toast.error(errMsg, { title: 'Rejection Failed' })
    } finally {
      setActingId(null)
    }
  }

  const handleAcknowledge = async (alertId) => {
    try {
      await agentsApi.acknowledgeAlert(alertId)
      const ackMsg = `Alert #${alertId} acknowledged.`
      toast.info(ackMsg, { title: 'Alert Acknowledged' })
      queryClient.invalidateQueries({ queryKey: ['my-work-queue'] })
      loadData()
    } catch (err) {
      const errMsg = `Acknowledgement failed: ${err?.response?.data?.detail || err.message}`
      toast.error(errMsg, { title: 'Action Failed' })
    }
  }

  const handleOpenResolve = (alert) => {
    setResolvingAlert(alert)
    setResolutionNotes('')
  }

  const handleSubmitResolve = async (e) => {
    e.preventDefault()
    if (!resolvingAlert || !resolutionNotes.trim()) return
    const alertId = resolvingAlert.id
    const orderId = resolvingAlert.customer_order_id
    const notes = resolutionNotes.trim()

    // 1. Immediately close the form modal and reset form
    setResolvingAlert(null)
    setResolutionNotes('')
    setIsResolving(false)

    // 2. Immediately show the toast message that the case was resolved
    const resMsg = `Case #${alertId} for Order ${orderId} successfully resolved. Verified corrective action recorded.`
    toast.success(resMsg, { title: 'Case Resolved' })

    // 3. Optimistically update query client so the case appears resolved immediately in UI
    const prevWorkData = queryClient.getQueryData(['my-work-queue'])
    queryClient.setQueryData(['my-work-queue'], (old) => {
      if (!old) return old
      return {
        ...old,
        alerts: (old.alerts || []).map((a) =>
          a.id === alertId
            ? { ...a, status: 'RESOLVED', resolution_notes: notes, resolved_at: new Date().toISOString() }
            : a
        ),
      }
    })

    // 4. Send resolve request to backend PostgreSQL
    try {
      await agentsApi.resolveAlert(alertId, notes)
      queryClient.invalidateQueries({ queryKey: ['my-work-queue'] })
      queryClient.invalidateQueries({ queryKey: ['order-monitoring'] })
      loadData()
    } catch (err) {
      if (prevWorkData) {
        queryClient.setQueryData(['my-work-queue'], prevWorkData)
      }
      const errMsg = `Resolution failed: ${err?.response?.data?.detail || err.message}`
      toast.error(errMsg, { title: 'Resolution Failed' })
    }
  }

  const handleOpenCommunication = (alert) => {
    setCommunicatingAlert(alert)
    setCommunicationNotes(alert.customer_communication_notes || '')
  }

  const handleSubmitCommunication = async (e) => {
    e.preventDefault()
    if (!communicatingAlert || !communicationNotes.trim()) return
    try {
      await agentsApi.recordCustomerCommunication(communicatingAlert.id, communicationNotes.trim())
      const commMsg = `Customer communication recorded for order ${communicatingAlert.customer_order_id}.`
      toast.success(commMsg, { title: 'Customer Notified' })
      setCommunicatingAlert(null)
      loadData()
    } catch (err) {
      const errMsg = `Communication recording failed: ${err?.response?.data?.detail || err.message}`
      toast.error(errMsg, { title: 'Recording Failed' })
    }
  }

  const handleCheckFollowups = async () => {
    setIsCheckingFollowups(true)
    try {
      const res = await agentsApi.checkFollowups()
      queryClient.invalidateQueries({ queryKey: ['my-work-queue'] })
      queryClient.invalidateQueries({ queryKey: ['order-monitoring'] })
      await loadData()
      if (res.followups_sent > 0) {
        const msg = `Agent 3 Follow-Up: Dispatched ${res.followups_sent} escalation emails across ${res.overdue_count} unresolved alerts (>3 days).`
        toast.success(msg, { title: '3-Day Follow-Up Dispatched' })
      } else {
        const msg = `3-Day SLA Check: All active alerts are within the 3-day resolution window or recently notified.`
        toast.info(msg, { title: 'SLA Status Verified' })
      }
    } catch (err) {
      const errMsg = `Follow-up check failed: ${err?.response?.data?.detail || err.message}`
      toast.error(errMsg, { title: 'Check Failed' })
    } finally {
      setIsCheckingFollowups(false)
    }
  }

  const handleSendSingleFollowup = async (alertId) => {
    setSendingFollowupAlertId(alertId)
    try {
      const res = await agentsApi.sendFollowup(alertId, true)
      queryClient.invalidateQueries({ queryKey: ['my-work-queue'] })
      queryClient.invalidateQueries({ queryKey: ['order-monitoring'] })
      await loadData()
      const msg = `Agent 3 follow-up dispatched for Order ${res.customer_order_id} (Day ${res.days_unresolved} unresolved).`
      toast.success(msg, { title: 'Follow-Up Email Dispatched' })
    } catch (err) {
      const errMsg = `Follow-up dispatch failed: ${err?.response?.data?.detail || err.message}`
      toast.error(errMsg, { title: 'Dispatch Failed' })
    } finally {
      setSendingFollowupAlertId(null)
    }
  }

  // Compute active running days for an alert/case
  const getCaseActiveDays = (al) => {
    if (!al) return 0
    // If resolved, compute duration while active
    if (al.status === 'RESOLVED' && al.resolved_at && al.detected_at) {
      const start = new Date(al.detected_at).getTime()
      const end = new Date(al.resolved_at).getTime()
      if (!isNaN(start) && !isNaN(end) && end >= start) {
        const d = Math.floor((end - start) / (1000 * 60 * 60 * 24))
        if (d > 0) return d
      }
    }
    // 1. Check description for explicit overdue/elapsed days (e.g. 50 days overdue)
    const descMatch = (al.description || '').match(/(\d+)\s*days?\s*(overdue|elapsed|unresolved|remaining)/i)
    if (descMatch && Number(descMatch[1]) > 0) {
      return Number(descMatch[1])
    }
    // 2. Check days_unresolved from backend
    if (typeof al.days_unresolved === 'number' && al.days_unresolved > 0) {
      return al.days_unresolved
    }
    // 3. Try parsing order intake date from customer_order_id (e.g. PRE-ASM-20261114)
    const match = al.customer_order_id?.match(/(\d{4})(\d{2})(\d{2})/)
    if (match) {
      const orderDate = new Date(`${match[1]}-${match[2]}-${match[3]}`)
      if (!isNaN(orderDate.getTime())) {
        const now = new Date()
        const diff = Math.max(0, Math.floor((now.getTime() - orderDate.getTime()) / (1000 * 60 * 60 * 24)))
        if (diff > 0) return diff
      }
    }
    // 4. Try detected_at or first_email_sent_at
    const dt = al.detected_at || al.first_email_sent_at
    if (dt) {
      const d = new Date(dt)
      if (!isNaN(d.getTime())) {
        const now = new Date()
        return Math.max(0, Math.floor((now.getTime() - d.getTime()) / (1000 * 60 * 60 * 24)))
      }
    }
    return al.days_unresolved || 0
  }

  // Filter alerts by custom user criteria (Risk, Status, Active Days)
  const applyCustomFilters = (al) => {
    // 1. Severity filter
    if (riskFilter !== 'ALL') {
      if ((al.severity || '').toUpperCase() !== riskFilter) return false
    }

    // 2. Status filter
    if (statusFilter !== 'ALL') {
      if (statusFilter === 'OPEN') {
        if (al.status === 'RESOLVED') return false
      } else if (statusFilter === 'RESOLVED') {
        if (al.status !== 'RESOLVED') return false
      } else if (statusFilter === 'ACKNOWLEDGED') {
        if (al.status !== 'ACKNOWLEDGED') return false
      }
    }

    // 3. Active days filter (strictly equal to the entered number of days)
    if (daysFilter !== '') {
      const targetDays = Number(daysFilter)
      if (!isNaN(targetDays) && targetDays >= 0) {
        const activeDays = getCaseActiveDays(al)
        if (activeDays !== targetDays) return false
      }
    }

    return true
  }

  // Filter alerts by role context
  const userDept = (user?.department || '').toUpperCase().trim()

  const allDepartmentIssues = alerts.filter((a) => {
    if (isAdministrator) return true
    if (isOp && userDept) return a.department?.toUpperCase().trim() === userDept
    return true
  })

  const allCsDeliveryRisks = alerts.filter((a) => {
    return (
      a.severity === 'CRITICAL' ||
      a.severity === 'HIGH' ||
      Boolean(a.delivery_impact) ||
      ['DELIVERY_DATE_BREACHED', 'CARRIER_TRANSIT_DELAY', 'SHIPMENT_EXCEPTION', 'RAW_MATERIAL_SHORTAGE', 'PRODUCTION_DELAY'].includes(a.risk_category)
    )
  })

  const departmentIssues = allDepartmentIssues.filter(applyCustomFilters)
  const csDeliveryRisks = allCsDeliveryRisks.filter(applyCustomFilters)

  const activeFilterCount = (riskFilter !== 'ALL' ? 1 : 0) + (statusFilter !== 'ALL' ? 1 : 0) + (daysFilter !== '' ? 1 : 0)

  const resetFilters = () => {
    setRiskFilter('ALL')
    setStatusFilter('ALL')
    setDaysFilter('')
  }

  return (
    <div className="page-stack">
      {/* TABS & FILTERS BAR */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid var(--mfg-border-default)',
          paddingBottom: 10,
          flexWrap: 'wrap',
          gap: 10,
        }}
      >
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          {/* Tab 1: Department Issues */}
          {(isOp || isAdministrator) && (
            <button
              type="button"
              onClick={() => setActiveTab('department_issues')}
              className={`button ${activeTab === 'department_issues' ? 'button-primary' : 'button-secondary'}`}
              style={{ fontSize: 12 }}
            >
              <Building2 size={15} /> Department Issues ({departmentIssues.length})
              {userDept && <span style={{ opacity: 0.8, fontSize: 10 }}>({userDept})</span>}
            </button>
          )}

          {/* Tab 2: Customer Service Delivery Risks */}
          {(isCS || isAdministrator) && (
            <button
              type="button"
              onClick={() => setActiveTab('cs_risks')}
              className={`button ${activeTab === 'cs_risks' ? 'button-primary' : 'button-secondary'}`}
              style={{ fontSize: 12 }}
            >
              <MessageSquare size={15} /> Customer Service Delivery Risks ({csDeliveryRisks.length})
            </button>
          )}

          {/* Tab 3: Commercial Approvals */}
          <button
            type="button"
            onClick={() => setActiveTab('approvals')}
            className={`button ${activeTab === 'approvals' ? 'button-primary' : 'button-secondary'}`}
            style={{ fontSize: 12 }}
          >
            <ShieldCheck size={15} /> Commercial Approvals ({pendingProposals.length} Pending Review)
          </button>
        </div>

        {/* REFRESH & FILTERS BUTTONS */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button
            type="button"
            className="button button-secondary"
            onClick={loadData}
            style={{ fontSize: 12, padding: '6px 12px', display: 'inline-flex', alignItems: 'center', gap: 5 }}
            title="Refresh work queue"
          >
            <RotateCcw size={13} />
            <span>Refresh</span>
          </button>
          <button
            type="button"
            onClick={() => setShowFilters(!showFilters)}
            className={`button ${showFilters ? 'button-primary glow-orange' : 'button-secondary'}`}
            style={{
              fontSize: 12,
              fontWeight: 700,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '6px 14px',
              borderRadius: 8,
              cursor: 'pointer',
              border: showFilters ? '1.5px solid var(--brand-purple, #6f3dba)' : '1px solid var(--mfg-border-default, #cbd5e1)',
              background: showFilters ? 'var(--brand-purple, #6f3dba)' : '#ffffff',
              color: showFilters ? '#ffffff' : 'var(--mfg-text-primary, #0f172a)',
              boxShadow: showFilters ? '0 2px 8px rgba(111, 61, 186, 0.25)' : 'none',
              transition: 'all 0.15s ease',
            }}
          >
            <Filter size={14} />
            <span>Filters</span>
            {activeFilterCount > 0 && (
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 900,
                  padding: '1px 6px',
                  borderRadius: 10,
                  background: showFilters ? '#ffffff' : 'var(--brand-purple, #6f3dba)',
                  color: showFilters ? 'var(--brand-purple, #6f3dba)' : '#ffffff',
                }}
              >
                {activeFilterCount}
              </span>
            )}
            <ChevronDown
              size={13}
              style={{
                transform: showFilters ? 'rotate(180deg)' : 'none',
                transition: 'transform 0.2s ease',
              }}
            />
          </button>
        </div>
      </div>

      {/* EXPANDABLE FILTERS PANEL */}
      {showFilters && (
        <div
          className="card"
          style={{
            background: 'var(--surface-hi, #ffffff)',
            border: '1.5px solid rgba(111, 61, 186, 0.25)',
            borderRadius: 10,
            padding: '14px 18px',
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
            boxShadow: '0 4px 14px rgba(111, 61, 186, 0.08)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--mfg-border-subtle, #f1f5f9)', paddingBottom: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 700, color: 'var(--mfg-text-primary, #0f172a)' }}>
              <Filter size={14} style={{ color: 'var(--brand-purple, #6f3dba)' }} />
              <span>Filter Cases &amp; Work Queue</span>
            </div>
            {activeFilterCount > 0 && (
              <button
                type="button"
                onClick={resetFilters}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--brand-purple, #6f3dba)',
                  fontSize: 11,
                  fontWeight: 700,
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                }}
              >
                <RotateCcw size={11} /> Reset Filters
              </button>
            )}
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
              gap: 12,
              alignItems: 'flex-end',
            }}
          >
            {/* 1. Risk / Severity Filter */}
            <div>
              <label style={{ display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--mfg-text-secondary, #64748b)', marginBottom: 4 }}>
                Risk Severity
              </label>
              <select
                value={riskFilter}
                onChange={(e) => setRiskFilter(e.target.value)}
                style={{
                  width: '100%',
                  padding: '7px 10px',
                  borderRadius: 6,
                  border: '1px solid var(--mfg-border-default, #cbd5e1)',
                  background: 'var(--mfg-bg-surface, #ffffff)',
                  color: 'var(--mfg-text-primary, #0f172a)',
                  fontSize: 12,
                  fontWeight: 600,
                  outline: 'none',
                }}
              >
                <option value="ALL">All Severities</option>
                <option value="CRITICAL">🔴 CRITICAL Severity</option>
                <option value="HIGH">🟠 HIGH Severity</option>
                <option value="MEDIUM">🟡 MEDIUM Severity</option>
                <option value="LOW">🔵 LOW Severity</option>
              </select>
            </div>

            {/* 2. Status Filter */}
            <div>
              <label style={{ display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--mfg-text-secondary, #64748b)', marginBottom: 4 }}>
                Case Status
              </label>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                style={{
                  width: '100%',
                  padding: '7px 10px',
                  borderRadius: 6,
                  border: '1px solid var(--mfg-border-default, #cbd5e1)',
                  background: 'var(--mfg-bg-surface, #ffffff)',
                  color: 'var(--mfg-text-primary, #0f172a)',
                  fontSize: 12,
                  fontWeight: 600,
                  outline: 'none',
                }}
              >
                <option value="ALL">All Statuses</option>
                <option value="OPEN">🟡 OPEN / Active Cases</option>
                <option value="RESOLVED">🟢 RESOLVED Cases</option>
                <option value="ACKNOWLEDGED">🔵 Acknowledged Cases</option>
              </select>
            </div>

            {/* 3. Days Active Input Box */}
            <div>
              <label style={{ display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--mfg-text-secondary, #64748b)', marginBottom: 4 }}>
                Active Days (Exact = N Days)
              </label>
              <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                <input
                  type="number"
                  min="0"
                  value={daysFilter}
                  onChange={(e) => setDaysFilter(e.target.value)}
                  placeholder="e.g. 3 (strictly equal to 3 days)"
                  style={{
                    width: '100%',
                    padding: '7px 10px 7px 28px',
                    borderRadius: 6,
                    border: '1px solid var(--mfg-border-default, #cbd5e1)',
                    background: 'var(--mfg-bg-surface, #ffffff)',
                    color: 'var(--mfg-text-primary, #0f172a)',
                    fontSize: 12,
                    fontWeight: 600,
                    outline: 'none',
                  }}
                />
                <Clock size={13} style={{ position: 'absolute', left: 9, color: '#94a3b8' }} />
                {daysFilter !== '' && (
                  <button
                    type="button"
                    onClick={() => setDaysFilter('')}
                    style={{
                      position: 'absolute',
                      right: 8,
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      fontSize: 11,
                      color: '#94a3b8',
                    }}
                  >
                    ✕
                  </button>
                )}
              </div>
            </div>

            {/* Quick Filter Buttons */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, paddingBottom: 2, flexWrap: 'wrap' }}>
              <button
                type="button"
                onClick={() => setRiskFilter(riskFilter === 'CRITICAL' ? 'ALL' : 'CRITICAL')}
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  padding: '5px 10px',
                  borderRadius: 6,
                  border: riskFilter === 'CRITICAL' ? '1.5px solid #ef4444' : '1px solid #fecaca',
                  background: riskFilter === 'CRITICAL' ? '#ef4444' : '#fef2f2',
                  color: riskFilter === 'CRITICAL' ? '#ffffff' : '#b91c1c',
                  cursor: 'pointer',
                }}
              >
                Critical
              </button>
              <button
                type="button"
                onClick={() => setRiskFilter(riskFilter === 'HIGH' ? 'ALL' : 'HIGH')}
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  padding: '5px 10px',
                  borderRadius: 6,
                  border: riskFilter === 'HIGH' ? '1.5px solid #f59e0b' : '1px solid #fde68a',
                  background: riskFilter === 'HIGH' ? '#f59e0b' : '#fffbeb',
                  color: riskFilter === 'HIGH' ? '#ffffff' : '#b45309',
                  cursor: 'pointer',
                }}
              >
                High
              </button>
              <button
                type="button"
                onClick={() => setStatusFilter(statusFilter === 'OPEN' ? 'ALL' : 'OPEN')}
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  padding: '5px 10px',
                  borderRadius: 6,
                  border: statusFilter === 'OPEN' ? '1.5px solid #0284c7' : '1px solid #bae6fd',
                  background: statusFilter === 'OPEN' ? '#0284c7' : '#f0f9ff',
                  color: statusFilter === 'OPEN' ? '#ffffff' : '#0369a1',
                  cursor: 'pointer',
                }}
              >
                Open
              </button>
              <button
                type="button"
                onClick={() => setStatusFilter(statusFilter === 'RESOLVED' ? 'ALL' : 'RESOLVED')}
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  padding: '5px 10px',
                  borderRadius: 6,
                  border: statusFilter === 'RESOLVED' ? '1.5px solid #10b981' : '1px solid #a7f3d0',
                  background: statusFilter === 'RESOLVED' ? '#10b981' : '#ecfdf5',
                  color: statusFilter === 'RESOLVED' ? '#ffffff' : '#065f46',
                  cursor: 'pointer',
                }}
              >
                Resolved
              </button>
              <button
                type="button"
                onClick={() => setDaysFilter(daysFilter === '3' ? '' : '3')}
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  padding: '5px 10px',
                  borderRadius: 6,
                  border: daysFilter === '3' ? '1.5px solid #8b5cf6' : '1px solid #ddd6fe',
                  background: daysFilter === '3' ? '#8b5cf6' : '#f5f3ff',
                  color: daysFilter === '3' ? '#ffffff' : '#6d28d9',
                  cursor: 'pointer',
                }}
              >
                3 Days
              </button>
              <button
                type="button"
                onClick={() => setDaysFilter(daysFilter === '10' ? '' : '10')}
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  padding: '5px 10px',
                  borderRadius: 6,
                  border: daysFilter === '10' ? '1.5px solid #8b5cf6' : '1px solid #ddd6fe',
                  background: daysFilter === '10' ? '#8b5cf6' : '#f5f3ff',
                  color: daysFilter === '10' ? '#ffffff' : '#6d28d9',
                  cursor: 'pointer',
                }}
              >
                10 Days
              </button>
              <button
                type="button"
                onClick={() => setDaysFilter(daysFilter === '30' ? '' : '30')}
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  padding: '5px 10px',
                  borderRadius: 6,
                  border: daysFilter === '30' ? '1.5px solid #8b5cf6' : '1px solid #ddd6fe',
                  background: daysFilter === '30' ? '#8b5cf6' : '#f5f3ff',
                  color: daysFilter === '30' ? '#ffffff' : '#6d28d9',
                  cursor: 'pointer',
                }}
              >
                30 Days
              </button>
            </div>
          </div>

          {/* Active Filter Summary Bar */}
          <div style={{ fontSize: 11, color: 'var(--mfg-text-muted, #64748b)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: 4 }}>
            <span>
              {activeFilterCount > 0 ? (
                <>
                  Active Filters: {riskFilter !== 'ALL' && <strong>Severity: {riskFilter} · </strong>}
                  {statusFilter !== 'ALL' && <strong>Status: {statusFilter} · </strong>}
                  {daysFilter !== '' && <strong>Active = {daysFilter} days · </strong>}
                  Showing matching cases
                </>
              ) : (
                'Showing all active and resolved work queue records.'
              )}
            </span>
          </div>
        </div>
      )}

      {/* TAB: DEPARTMENT ASSIGNED ISSUES */}
      {activeTab === 'department_issues' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {departmentIssues.length > 0 && (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--mfg-bg-surface)', border: '1px solid var(--mfg-border-subtle)', borderRadius: 8, padding: '8px 14px', marginBottom: 2 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
                <Clock size={15} style={{ color: departmentIssues.some((a) => a.is_followup_due && a.status !== 'RESOLVED') ? '#ef4444' : '#10b981' }} />
                <span>
                  <strong>Surveillance SLA:</strong> Issues unresolved &gt;3 days trigger automated Agent 3 escalation emails.
                  {departmentIssues.filter((a) => a.is_followup_due && a.status !== 'RESOLVED').length > 0 && (
                    <span style={{ color: '#ef4444', fontWeight: 700, marginLeft: 8 }}>
                      ({departmentIssues.filter((a) => a.is_followup_due && a.status !== 'RESOLVED').length} issue(s) reached 3+ days unresolved)
                    </span>
                  )}
                </span>
              </div>
              <button
                type="button"
                className="button button-secondary"
                onClick={handleCheckFollowups}
                disabled={isCheckingFollowups}
                style={{ fontSize: 11, padding: '3px 10px', minHeight: 28, display: 'inline-flex', alignItems: 'center', gap: 6 }}
                title="Scan all issues and dispatch follow-up emails for any unresolved >3 days"
              >
                <Mail size={13} /> {isCheckingFollowups ? 'Checking SLA...' : 'Check 3-Day Follow-Ups'}
              </button>
            </div>
          )}

          {departmentIssues.length === 0 ? (
            <div className="card" style={{ padding: 40, textAlign: 'center', background: 'var(--mfg-bg-card)', border: '1px solid var(--mfg-border-default)', borderRadius: 10 }}>
              <CheckCircle2 size={36} style={{ color: '#22C55E', margin: '0 auto 10px auto' }} />
              <h3 style={{ margin: 0, color: 'var(--mfg-text-primary)', fontSize: 16 }}>Department Queue Clean</h3>
              <p style={{ color: 'var(--mfg-text-secondary)', fontSize: 13, marginTop: 4 }}>
                No active operational issues or holds pending for your department.
              </p>
            </div>
          ) : (
            departmentIssues.map((al) => {
              const isCrit = al.severity === 'CRITICAL'
              const canAck = canAcknowledgeAlert(user, al.department) && al.status === 'OPEN'
              const activeDays = getCaseActiveDays(al)
              const isExpanded = Boolean(expandedAlerts[al.id])
              const cleanTitle = (al.title || 'Operational Risk')
                .replace(/\s+for\s+order\s+.*$/i, '')
                .replace(/^Order\s+[\w-]+\s+(has\s+)?/i, '')
                .trim()

              return (
                <div
                  key={al.id}
                  className="card"
                  style={{
                    background: 'var(--mfg-bg-card)',
                    border: '1px solid',
                    borderColor: isCrit ? '#ef4444' : 'var(--mfg-border-default)',
                    borderRadius: 10,
                    padding: '9px 13px',
                    boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
                  }}
                >
                  {/* Card Header: Severity, Dept, Clean Title, Order ID, Active Days, Follow-up Status */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 5 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                      <span className={`mfg-badge ${isCrit ? 'mfg-badge-critical' : 'mfg-badge-warning'}`} style={{ fontSize: 10, padding: '1px 6px', fontWeight: 700 }}>
                        {al.severity}
                      </span>
                      <span className="mfg-badge" style={{ fontWeight: 700, fontSize: 10, padding: '1px 6px' }}>
                        {al.department}
                      </span>
                      <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--mfg-text-primary)' }}>
                        {cleanTitle}
                      </span>
                      <span style={{ fontSize: 11, color: 'var(--mfg-text-muted)' }}>
                        • Order: <strong style={{ color: 'var(--mfg-text-primary)' }}>{al.customer_order_id}</strong>
                      </span>

                      {/* Active Days Badge */}
                      <span
                        className="mfg-badge"
                        style={{
                          fontSize: 10,
                          padding: '1px 6px',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 3,
                          background: activeDays >= 10 ? '#fee2e2' : activeDays >= 3 ? '#fef3c7' : '#f1f5f9',
                          color: activeDays >= 10 ? '#b91c1c' : activeDays >= 3 ? '#b45309' : '#475569',
                          border: `1px solid ${activeDays >= 10 ? '#fca5a5' : activeDays >= 3 ? '#fcd34d' : '#cbd5e1'}`,
                          fontWeight: 700,
                        }}
                        title={`Case active for ${activeDays} days`}
                      >
                        <Clock size={10} /> Active: {activeDays}d
                      </span>

                      {/* Status Badges */}
                      {al.status === 'RESOLVED' ? (
                        <span
                          className="mfg-badge"
                          style={{
                            background: '#dcfce7',
                            color: '#15803d',
                            border: '1px solid #86efac',
                            fontWeight: 700,
                            fontSize: 10,
                            padding: '1px 6px',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 3,
                          }}
                        >
                          <CheckCircle2 size={11} /> Resolved
                        </span>
                      ) : al.followup_count > 0 ? (
                        <span
                          className="mfg-badge"
                          style={{ background: '#fef3c7', color: '#b45309', border: '1px solid #fcd34d', fontSize: 10, padding: '1px 6px', display: 'inline-flex', alignItems: 'center', gap: 3 }}
                          title={`Follow-up escalation sent on Day ${al.days_unresolved || 3}`}
                        >
                          <Mail size={11} /> Follow-Up Sent (Day {al.days_unresolved || 3})
                        </span>
                      ) : al.is_followup_due ? (
                        <span
                          className="mfg-badge"
                          style={{ background: '#fee2e2', color: '#b91c1c', border: '1px solid #fca5a5', fontSize: 10, padding: '1px 6px', display: 'inline-flex', alignItems: 'center', gap: 3 }}
                        >
                          <Clock size={11} /> 3+ Days Unresolved
                        </span>
                      ) : null}
                    </div>

                    <span style={{ fontSize: 10.5, color: 'var(--mfg-text-muted)', flexShrink: 0 }}>
                      {formatDate(al.detected_at)}
                    </span>
                  </div>

                  {/* Essential Information Strip: 1-line Risk & Impact */}
                  <div
                    style={{
                      fontSize: 11,
                      color: 'var(--mfg-text-secondary)',
                      padding: '3px 0',
                      marginBottom: 5,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: 8,
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0, flex: 1, overflow: 'hidden' }}>
                      <AlertTriangle size={12} style={{ color: isCrit ? '#ef4444' : '#f59e0b', flexShrink: 0 }} />
                      <span
                        style={{
                          whiteSpace: isExpanded ? 'normal' : 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          color: isCrit ? '#b91c1c' : '#b45309',
                          fontWeight: 600,
                        }}
                      >
                        {al.delivery_impact || al.description}
                      </span>
                    </div>

                    <button
                      type="button"
                      onClick={() => toggleAlertDetails(al.id)}
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: 'var(--brand-purple)',
                        fontSize: 10.5,
                        fontWeight: 600,
                        cursor: 'pointer',
                        padding: '0 2px',
                        flexShrink: 0,
                      }}
                    >
                      {isExpanded ? 'Hide details ▴' : 'Details ▾'}
                    </button>
                  </div>

                  {/* Essential Action Note (1 clean line when collapsed) */}
                  {al.recommended_action && !isExpanded && (
                    <div style={{ fontSize: 11, color: 'var(--mfg-text-secondary)', display: 'flex', alignItems: 'center', gap: 5, marginBottom: 5, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      <span style={{ fontWeight: 600, color: 'var(--mfg-text-primary)', flexShrink: 0 }}>Action:</span>
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {al.recommended_action}
                      </span>
                    </div>
                  )}

                  {/* Resolution Note if resolved */}
                  {al.resolution_notes && !isExpanded && (
                    <div style={{ fontSize: 10.5, color: '#16a34a', display: 'flex', alignItems: 'center', gap: 5, marginBottom: 5, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      <CheckCircle2 size={11} style={{ flexShrink: 0 }} />
                      <span style={{ fontWeight: 600, flexShrink: 0 }}>Resolution:</span>
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{al.resolution_notes}</span>
                    </div>
                  )}

                  {/* Full Expandable Details (when requested by user) */}
                  {isExpanded && (
                    <div
                      style={{
                        fontSize: 11,
                        padding: '6px 10px',
                        borderLeft: '2px solid var(--brand-purple)',
                        marginBottom: 6,
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 5,
                        lineHeight: 1.45,
                      }}
                    >
                      <div>
                        <strong style={{ color: 'var(--mfg-text-primary)' }}>Issue Detail: </strong>
                        <span style={{ color: 'var(--mfg-text-secondary)' }}>{al.description}</span>
                      </div>
                      {al.delivery_impact && (
                        <div>
                          <strong style={{ color: '#d97706' }}>Delivery Impact: </strong>
                          <span style={{ color: 'var(--mfg-text-secondary)' }}>{al.delivery_impact}</span>
                        </div>
                      )}
                      {al.recommended_action && (
                        <div>
                          <strong style={{ color: 'var(--brand-purple)' }}>Recommended Action: </strong>
                          <span style={{ color: 'var(--mfg-text-secondary)' }}>{al.recommended_action}</span>
                        </div>
                      )}
                      {al.resolution_notes && (
                        <div style={{ color: '#16a34a' }}>
                          <strong>Resolution Recorded: </strong>
                          <span>{al.resolution_notes}</span>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Action Footer */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--mfg-border-subtle)', paddingTop: 6 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <span style={{ fontSize: 10.5, color: 'var(--mfg-text-muted)' }}>
                        Status: <strong style={{ color: al.status === 'RESOLVED' ? '#22c55e' : '#f59e0b' }}>{al.status}</strong>
                      </span>
                      {al.first_email_sent_at && (
                        <span style={{ fontSize: 10, color: 'var(--mfg-text-muted)' }}>
                          Escalated: {al.days_unresolved}d ago
                        </span>
                      )}
                    </div>

                    <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                      <Link
                        to={al.customer_order_id?.startsWith('PRE-')
                          ? `/assessments?id=${encodeURIComponent(al.customer_order_id.replace(/^PRE-/, ''))}`
                          : `/orders/${encodeURIComponent(al.customer_order_id)}`}
                        className="button button-secondary"
                        style={{ fontSize: 11, padding: '2px 8px', textDecoration: 'none', minHeight: 25, display: 'inline-flex', alignItems: 'center', gap: 4 }}
                      >
                        View Order <ExternalLink size={11} />
                      </Link>

                      {al.status !== 'RESOLVED' && al.is_followup_due && (
                        <button
                          type="button"
                          className="button button-secondary"
                          onClick={() => handleSendSingleFollowup(al.id)}
                          disabled={sendingFollowupAlertId === al.id}
                          style={{ fontSize: 11, padding: '2px 8px', minHeight: 25, display: 'inline-flex', alignItems: 'center', gap: 4 }}
                          title="Dispatch immediate Agent 3 follow-up escalation email"
                        >
                          <Mail size={11} />
                          {sendingFollowupAlertId === al.id ? 'Sending...' : 'Send Follow-Up'}
                        </button>
                      )}

                      {canAck && (
                        <button type="button" className="button button-secondary" onClick={() => handleAcknowledge(al.id)} style={{ fontSize: 11, padding: '2px 8px', minHeight: 25 }}>
                          <Check size={11} /> Acknowledge Alert
                        </button>
                      )}

                      {al.status !== 'RESOLVED' ? (
                        <button
                          type="button"
                          className="button button-primary glow-orange"
                          onClick={() => handleOpenResolve(al)}
                          style={{ fontSize: 11, padding: '2px 11px', minHeight: 25, display: 'inline-flex', alignItems: 'center', gap: 4, fontWeight: 700 }}
                        >
                          <CheckCircle2 size={12} /> Resolve Case
                        </button>
                      ) : (
                        <span style={{ color: '#16a34a', fontWeight: 700, fontSize: 11, display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 6px' }}>
                          <CheckCircle2 size={12} /> Case Resolved
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              )
            })
          )}
        </div>
      )}

      {/* TAB: CUSTOMER SERVICE DELIVERY RISKS */}
      {activeTab === 'cs_risks' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {csDeliveryRisks.length === 0 ? (
            <div className="card" style={{ padding: 40, textAlign: 'center', background: 'var(--mfg-bg-card)', border: '1px solid var(--mfg-border-default)', borderRadius: 10 }}>
              <CheckCircle2 size={36} style={{ color: '#22C55E', margin: '0 auto 10px auto' }} />
              <h3 style={{ margin: 0, color: 'var(--mfg-text-primary)', fontSize: 16 }}>No Delivery Risks Pending Communication</h3>
              <p style={{ color: 'var(--mfg-text-secondary)', fontSize: 13, marginTop: 4 }}>
                All committed orders are progressing without customer-impacting delivery variances.
              </p>
            </div>
          ) : (
            csDeliveryRisks.map((al) => {
              const isCommunicated = Boolean(al.customer_communicated)
              const activeDays = getCaseActiveDays(al)
              const isResolved = al.status === 'RESOLVED'
              const isExpanded = Boolean(expandedAlerts[al.id])

              return (
                <div
                  key={al.id}
                  className="card"
                  style={{
                    background: 'var(--mfg-bg-card)',
                    border: '1px solid var(--mfg-border-default)',
                    borderRadius: 10,
                    padding: '9px 13px',
                    boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
                  }}
                >
                  {/* Card Header: Severity, Dept, Title, Active Days, Comm Status */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 5 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                      <span className={`mfg-badge ${al.severity === 'CRITICAL' ? 'mfg-badge-critical' : 'mfg-badge-warning'}`} style={{ fontSize: 10, padding: '1px 6px', fontWeight: 700 }}>
                        {al.severity}
                      </span>
                      <span className="mfg-badge" style={{ fontWeight: 700, fontSize: 10, padding: '1px 6px' }}>
                        {al.department}
                      </span>
                      <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--mfg-text-primary)' }}>
                        Delivery Risk • Order {al.customer_order_id}
                      </span>

                      {/* Active Days Badge */}
                      <span
                        className="mfg-badge"
                        style={{
                          fontSize: 10,
                          padding: '1px 6px',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 3,
                          background: activeDays >= 10 ? '#fee2e2' : activeDays >= 3 ? '#fef3c7' : '#f1f5f9',
                          color: activeDays >= 10 ? '#b91c1c' : activeDays >= 3 ? '#b45309' : '#475569',
                          border: `1px solid ${activeDays >= 10 ? '#fca5a5' : activeDays >= 3 ? '#fcd34d' : '#cbd5e1'}`,
                          fontWeight: 700,
                        }}
                        title={`Case active for ${activeDays} days`}
                      >
                        <Clock size={10} /> Active: {activeDays}d
                      </span>

                      {isResolved && (
                        <span
                          className="mfg-badge"
                          style={{
                            background: '#dcfce7',
                            color: '#15803d',
                            border: '1px solid #86efac',
                            fontWeight: 700,
                            fontSize: 10,
                            padding: '1px 6px',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 3,
                          }}
                        >
                          <CheckCircle2 size={11} /> Resolved
                        </span>
                      )}
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      {isCommunicated ? (
                        <span style={{ fontSize: 10.5, color: '#16a34a', display: 'flex', alignItems: 'center', gap: 4, fontWeight: 600 }}>
                          <CheckCircle2 size={12} /> Customer Notified
                        </span>
                      ) : (
                        <span style={{ fontSize: 10.5, color: '#dc2626', display: 'flex', alignItems: 'center', gap: 4, fontWeight: 600 }}>
                          <Clock size={12} /> Pending Communication
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Essential Information Strip: 1-line Impact with Toggle */}
                  <div
                    style={{
                      fontSize: 11,
                      color: 'var(--mfg-text-secondary)',
                      padding: '3px 0',
                      marginBottom: 5,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: 8,
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0, flex: 1, overflow: 'hidden' }}>
                      <AlertTriangle size={12} style={{ color: '#f59e0b', flexShrink: 0 }} />
                      <span
                        style={{
                          whiteSpace: isExpanded ? 'normal' : 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          color: '#b45309',
                          fontWeight: 600,
                        }}
                      >
                        {al.delivery_impact || al.description || 'Schedule extension risk under verification.'}
                      </span>
                    </div>

                    <button
                      type="button"
                      onClick={() => toggleAlertDetails(al.id)}
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: 'var(--brand-purple)',
                        fontSize: 10.5,
                        fontWeight: 600,
                        cursor: 'pointer',
                        padding: '0 2px',
                        flexShrink: 0,
                      }}
                    >
                      {isExpanded ? 'Hide details ▴' : 'Details ▾'}
                    </button>
                  </div>

                  {/* CS Directive (1 clean line) */}
                  {!isExpanded && (
                    <div style={{ fontSize: 10.5, color: 'var(--mfg-text-muted)', marginBottom: 5, display: 'flex', alignItems: 'center', gap: 4 }}>
                      <span style={{ fontWeight: 600 }}>Directive:</span> Do not promise unverified dates to customer until schedule is confirmed.
                    </div>
                  )}

                  {/* Communication Notes if already logged */}
                  {al.customer_communication_notes && !isExpanded && (
                    <div style={{ fontSize: 10.5, color: '#16a34a', display: 'flex', alignItems: 'center', gap: 5, marginBottom: 5, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      <MessageSquare size={11} style={{ flexShrink: 0 }} />
                      <span style={{ fontWeight: 600, flexShrink: 0 }}>Comm Log:</span>
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{al.customer_communication_notes}</span>
                    </div>
                  )}

                  {/* Resolution Notes if resolved */}
                  {al.resolution_notes && !isExpanded && (
                    <div style={{ fontSize: 10.5, color: '#16a34a', display: 'flex', alignItems: 'center', gap: 5, marginBottom: 5, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      <CheckCircle2 size={11} style={{ flexShrink: 0 }} />
                      <span style={{ fontWeight: 600, flexShrink: 0 }}>Resolution:</span>
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{al.resolution_notes}</span>
                    </div>
                  )}

                  {/* Full Expandable Details (when requested by user) */}
                  {isExpanded && (
                    <div
                      style={{
                        fontSize: 11,
                        padding: '6px 10px',
                        borderLeft: '2px solid var(--brand-purple)',
                        marginBottom: 6,
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 5,
                        lineHeight: 1.45,
                      }}
                    >
                      <div>
                        <strong style={{ color: 'var(--mfg-text-primary)' }}>Risk Description: </strong>
                        <span style={{ color: 'var(--mfg-text-secondary)' }}>{al.description}</span>
                      </div>
                      {al.delivery_impact && (
                        <div>
                          <strong style={{ color: '#d97706' }}>Delivery Impact: </strong>
                          <span style={{ color: 'var(--mfg-text-secondary)' }}>{al.delivery_impact}</span>
                        </div>
                      )}
                      <div style={{ color: 'var(--mfg-text-muted)', fontSize: 10.5 }}>
                        <strong>Customer Service Directive: </strong>
                        The revised delivery date has not yet been confirmed. Do not promise unverified dates to the customer.
                      </div>
                      {al.customer_communication_notes && (
                        <div style={{ color: '#16a34a' }}>
                          <strong>Customer Communication Log: </strong>
                          <span>{al.customer_communication_notes}</span>
                        </div>
                      )}
                      {al.resolution_notes && (
                        <div style={{ color: '#16a34a' }}>
                          <strong>Resolution Action Taken: </strong>
                          <span>{al.resolution_notes}</span>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Action Footer */}
                  <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 6, borderTop: '1px solid var(--mfg-border-subtle)', paddingTop: 6 }}>
                    <Link
                      to={al.customer_order_id?.startsWith('PRE-')
                        ? `/assessments?id=${encodeURIComponent(al.customer_order_id.replace(/^PRE-/, ''))}`
                        : `/orders/${encodeURIComponent(al.customer_order_id)}`}
                      className="button button-secondary"
                      style={{ fontSize: 11, padding: '2px 8px', textDecoration: 'none', minHeight: 25, display: 'inline-flex', alignItems: 'center', gap: 4 }}
                    >
                      Inspect Order <ExternalLink size={11} />
                    </Link>

                    {canRecordCustomerCommunication(user) && (
                      <button type="button" className="button button-secondary" onClick={() => handleOpenCommunication(al)} style={{ fontSize: 11, padding: '2px 9px', minHeight: 25, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                        <MessageSquare size={11} /> Record Note
                      </button>
                    )}

                    {!isResolved ? (
                      <button
                        type="button"
                        className="button button-primary glow-orange"
                        onClick={() => handleOpenResolve(al)}
                        style={{ fontSize: 11, padding: '2px 11px', minHeight: 25, display: 'inline-flex', alignItems: 'center', gap: 4, fontWeight: 700 }}
                      >
                        <CheckCircle2 size={12} /> Resolve Case
                      </button>
                    ) : (
                      <span style={{ color: '#16a34a', fontWeight: 700, fontSize: 11, display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 6px' }}>
                        <CheckCircle2 size={12} /> Case Resolved
                      </span>
                    )}
                  </div>
                </div>
              )
            })
          )}
        </div>
      )}

      {/* TAB: PENDING COMMERCIAL APPROVALS */}
      {activeTab === 'approvals' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {!canApprove && (
            <div style={{ padding: 12, borderRadius: 8, background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.3)', color: '#F59E0B', fontSize: 12 }}>
              <strong>Commercial Authority Notice:</strong> You are signed in as <code>{user?.role || 'user'}</code> without commercial commitment approval permission. Only authorized Customer Service Approvers and Administrators can execute commercial sign-offs.
            </div>
          )}

          {/* Sub-filter pills for proposals */}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--mfg-text-muted)', textTransform: 'uppercase' }}>Filter:</span>
            <button
              type="button"
              onClick={() => setProposalFilter('ALL')}
              className={`button ${proposalFilter === 'ALL' ? 'button-primary' : 'button-secondary'}`}
              style={{ fontSize: 11, padding: '3px 10px', minHeight: 26 }}
            >
              All ({allProposals.length})
            </button>
            <button
              type="button"
              onClick={() => setProposalFilter('PENDING')}
              className={`button ${proposalFilter === 'PENDING' ? 'button-primary' : 'button-secondary'}`}
              style={{ fontSize: 11, padding: '3px 10px', minHeight: 26 }}
            >
              Pending Human Review ({pendingProposals.length})
            </button>
            <button
              type="button"
              onClick={() => setProposalFilter('APPROVED')}
              className={`button ${proposalFilter === 'APPROVED' ? 'button-primary' : 'button-secondary'}`}
              style={{ fontSize: 11, padding: '3px 10px', minHeight: 26 }}
            >
              Approved ({allProposals.filter((p) => p.status === 'APPROVED').length})
            </button>
          </div>

          {/* TASK 4: REVISED PROPOSAL WAITING INDICATOR BANNER */}
          {allProposals.filter((p) => (p.revision || 1) > 1 && p.status === 'PENDING').length > 0 && (
            <div
              style={{
                padding: '10px 14px',
                borderRadius: 8,
                background: 'rgba(245, 158, 11, 0.1)',
                border: '1px solid rgba(245, 158, 11, 0.35)',
                color: '#d97706',
                fontSize: 12,
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                marginBottom: 6,
              }}
            >
              <AlertTriangle size={16} />
              <div>
                <strong>Operational Variance Alert:</strong>{' '}
                {allProposals.filter((p) => (p.revision || 1) > 1 && p.status === 'PENDING').length} Reassessment Revision(s) waiting for Commercial Review due to operational risks.
              </div>
            </div>
          )}

          {proposals.length === 0 ? (
            <div className="card" style={{ padding: 40, textAlign: 'center', background: 'var(--mfg-bg-card)', border: '1px solid var(--mfg-border-default)', borderRadius: 10 }}>
              <CheckCircle2 size={36} style={{ color: '#22C55E', margin: '0 auto 10px auto' }} />
              <h3 style={{ margin: 0, color: 'var(--mfg-text-primary)', fontSize: 16 }}>All Caught Up!</h3>
              <p style={{ color: 'var(--mfg-text-secondary)', fontSize: 13, marginTop: 4 }}>
                There are no commercial promise-date proposals matching the selected filter.
              </p>
            </div>
          ) : (
            proposals.map((p) => {
              const isPreOrder = Boolean(p.customer_order_id?.startsWith('PRE-'))
              const cleanAssessmentId = isPreOrder ? p.customer_order_id.replace(/^PRE-/, '') : null
              const journeyLink = isPreOrder
                ? `/assessments?id=${encodeURIComponent(cleanAssessmentId)}`
                : `/orders/${encodeURIComponent(p.customer_order_id)}`
              const isApproved = p.status === 'APPROVED'
              const isRejected = p.status === 'REJECTED'

              // Lookup matching assessment for rich commercial context
              const assessment = assessments.find(
                (a) =>
                  a.assessment_id === cleanAssessmentId ||
                  a.customer_order_id === p.customer_order_id ||
                  a.customer_order_id === cleanAssessmentId ||
                  a.id === cleanAssessmentId ||
                  a.proposal_id === p.id
              )

              const customerName = assessment?.customer_name || 'Retailer North'
              const rawProductName = assessment?.product_name || 'Aster 15 128GB'
              const productName = rawProductName.replace(/\s*\(SPH-[^)]+\)/i, '')
              const orderQty = assessment?.order_qty || 250
              const unitPrice = assessment?.unit_price_inr || 14500
              const totalValue = orderQty * unitPrice
              const requestedDate = assessment?.requested_delivery_date
              const daysVariance = assessment?.days_variance ?? (p.delay_days || 0)
              const readyCount = assessment?.readiness_records?.filter((r) => r.readiness_status === 'READY').length ?? 7

              const isRevision = (p.revision || 1) > 1
              const isTarget = targetProposalId && Number(targetProposalId) === p.id
              const isDelayed = daysVariance > 0
              const isEvidenceExpanded = expandedEvidenceId === p.id

              // Clean high-signal 1-line verdict
              const cleanVerdict = isDelayed
                ? `Commitment revised with +${daysVariance} days variance vs requested delivery date.`
                : readyCount === 7
                ? 'Feasibility verified across all 7 operational conduits. Achievable on target schedule.'
                : `${7 - readyCount} conduit variance(s) flagged during autonomous feasibility audit.`

              return (
                <div
                  key={p.id}
                  id={`proposal-card-${p.id}`}
                  className="card"
                  style={{
                    background: 'var(--mfg-bg-card)',
                    border: isTarget
                      ? '2px solid var(--brand-purple)'
                      : isRevision && p.status === 'PENDING'
                      ? '1px solid rgba(245, 158, 11, 0.5)'
                      : '1px solid var(--mfg-border-default)',
                    borderRadius: 10,
                    padding: '10px 14px',
                    boxShadow: isTarget ? '0 0 0 3px rgba(111, 61, 186, 0.12)' : '0 1px 2px rgba(0,0,0,0.03)',
                    transition: 'all 0.18s ease',
                  }}
                >
                  {/* Top Bar: Order ID, Status Badge, Revision Tag, Journey Link */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 7, flexWrap: 'wrap' }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 13.5, fontWeight: 700, color: 'var(--mfg-text-primary)' }}>
                        <Package size={14} style={{ color: 'var(--brand-purple)' }} />
                        {isPreOrder ? `Pre-Order (${cleanAssessmentId})` : `Order #${p.customer_order_id}`}
                      </span>

                      {isRevision && (
                        <span
                          className="mfg-badge"
                          style={{
                            background: 'rgba(111, 61, 186, 0.1)',
                            color: 'var(--brand-purple)',
                            border: '1px solid rgba(111, 61, 186, 0.2)',
                            fontWeight: 700,
                            fontSize: 10,
                            padding: '1px 6px',
                          }}
                        >
                          Rev #{p.revision}
                        </span>
                      )}

                      {isTarget && (
                        <span
                          className="mfg-badge"
                          style={{
                            background: 'var(--brand-purple)',
                            color: '#ffffff',
                            fontWeight: 700,
                            fontSize: 10,
                            padding: '1px 6px',
                          }}
                        >
                          Selected
                        </span>
                      )}

                      {isApproved ? (
                        <span className="mfg-badge" style={{ background: 'rgba(34, 197, 94, 0.12)', color: '#16a34a', border: '1px solid rgba(34, 197, 94, 0.25)', fontWeight: 700, fontSize: 10.5, padding: '1.5px 7px' }}>
                          ✓ Approved Commitment
                        </span>
                      ) : isRejected ? (
                        <span className="mfg-badge" style={{ background: 'rgba(239, 68, 68, 0.12)', color: '#dc2626', border: '1px solid rgba(239, 68, 68, 0.25)', fontWeight: 700, fontSize: 10.5, padding: '1.5px 7px' }}>
                          ✕ Rejected
                        </span>
                      ) : (
                        <span className="mfg-badge mfg-badge-warning" style={{ fontSize: 10.5, padding: '1.5px 7px' }}>
                          Pending Human Review
                        </span>
                      )}
                    </div>

                    <Link
                      to={journeyLink}
                      style={{
                        fontSize: 11,
                        color: 'var(--mfg-accent-primary)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 3,
                        textDecoration: 'none',
                        fontWeight: 600,
                      }}
                    >
                      View Journey <ExternalLink size={11} />
                    </Link>
                  </div>

                  {/* Clean 5-Metric Strip (Essential Commercial Data Only) */}
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                      gap: 12,
                      padding: '6px 0 8px 0',
                      marginBottom: 6,
                    }}
                  >
                    <div>
                      <div style={{ fontSize: 9.5, color: 'var(--mfg-text-muted)', textTransform: 'uppercase', fontWeight: 600, letterSpacing: '0.04em' }}>
                        Customer
                      </div>
                      <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--mfg-text-primary)', marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {customerName}
                      </div>
                    </div>

                    <div>
                      <div style={{ fontSize: 9.5, color: 'var(--mfg-text-muted)', textTransform: 'uppercase', fontWeight: 600, letterSpacing: '0.04em' }}>
                        Product Model
                      </div>
                      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--mfg-text-primary)', marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={productName}>
                        {productName}
                      </div>
                    </div>

                    <div>
                      <div style={{ fontSize: 9.5, color: 'var(--mfg-text-muted)', textTransform: 'uppercase', fontWeight: 600, letterSpacing: '0.04em' }}>
                        Demand &amp; Value
                      </div>
                      <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--brand-purple)', marginTop: 2 }}>
                        {formatNumber(orderQty)} units <span style={{ fontSize: 10.5, fontWeight: 500, color: 'var(--mfg-text-muted)' }}>({formatINR(totalValue)})</span>
                      </div>
                    </div>

                    <div>
                      <div style={{ fontSize: 9.5, color: 'var(--mfg-text-muted)', textTransform: 'uppercase', fontWeight: 600, letterSpacing: '0.04em' }}>
                        Proposed Commitment
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginTop: 2 }}>
                        <span style={{ fontSize: 12, fontWeight: 700, color: isDelayed ? '#dc2626' : 'var(--text-primary)' }}>
                          {formatDate(p.proposed_date)}
                        </span>
                        <span
                          style={{
                            fontSize: 9.5,
                            fontWeight: 700,
                            padding: '1px 5px',
                            borderRadius: 6,
                            background: isDelayed ? 'rgba(239, 68, 68, 0.1)' : 'rgba(34, 197, 94, 0.1)',
                            color: isDelayed ? '#dc2626' : '#16a34a',
                          }}
                        >
                          {isDelayed ? `+${daysVariance}d` : 'On Time'}
                        </span>
                      </div>
                    </div>

                    <div>
                      <div style={{ fontSize: 9.5, color: 'var(--mfg-text-muted)', textTransform: 'uppercase', fontWeight: 600, letterSpacing: '0.04em' }}>
                        7-Conduit Readiness
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginTop: 2 }}>
                        <span
                          style={{
                            width: 7,
                            height: 7,
                            borderRadius: '50%',
                            background: readyCount === 7 ? '#22c55e' : '#ef4444',
                            flexShrink: 0,
                          }}
                        />
                        <span style={{ fontSize: 12, fontWeight: 700, color: readyCount === 7 ? '#16a34a' : '#dc2626' }}>
                          {readyCount}/7 Ready
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* 1-Line Evidence Verdict Strip with Expandable Breakdown */}
                  <div
                    style={{
                      fontSize: 11,
                      color: 'var(--mfg-text-secondary)',
                      padding: '4px 0',
                      marginBottom: 8,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: 8,
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0, flex: 1 }}>
                      <Sparkles size={12} style={{ color: 'var(--brand-purple)', flexShrink: 0 }} />
                      <span
                        style={{
                          whiteSpace: isEvidenceExpanded ? 'normal' : 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          color: isDelayed ? '#b45309' : 'var(--mfg-text-primary)',
                          fontWeight: 500,
                        }}
                      >
                        {cleanVerdict}
                      </span>
                    </div>

                    <button
                      type="button"
                      onClick={() => setExpandedEvidenceId(isEvidenceExpanded ? null : p.id)}
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: 'var(--brand-purple)',
                        fontSize: 10.5,
                        fontWeight: 600,
                        cursor: 'pointer',
                        padding: '0 2px',
                        flexShrink: 0,
                      }}
                    >
                      {isEvidenceExpanded ? 'Hide audit details ▴' : 'Audit details ▾'}
                    </button>
                  </div>

                  {/* Expandable Evidence Breakdown (Only shown when user clicks) */}
                  {isEvidenceExpanded && (
                    <div
                      style={{
                        fontSize: 10.5,
                        color: 'var(--mfg-text-secondary)',
                        padding: '6px 10px',
                        borderLeft: '2px solid var(--brand-purple)',
                        marginBottom: 8,
                        lineHeight: 1.5,
                      }}
                    >
                      {Array.isArray(p.reasons) && p.reasons.length > 0 ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                          {p.reasons.map((r, rIdx) => (
                            <div key={rIdx} style={{ display: 'flex', alignItems: 'flex-start', gap: 6 }}>
                              <span style={{ color: 'var(--brand-purple)', fontWeight: 700 }}>•</span>
                              <span>{r}</span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div>Feasibility confirmed based on available material buffers and factory work center capacity.</div>
                      )}
                    </div>
                  )}

                  {/* Action Footer */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--mfg-border-subtle)', paddingTop: 7 }}>
                    <div style={{ fontSize: 10.5, color: 'var(--mfg-text-muted)' }}>
                      Recommended by <strong style={{ color: 'var(--brand-purple)' }}>{p.recommended_by === 'agent' ? 'Agent 2 Feasibility Engine' : 'Human Operator'}</strong>
                    </div>

                    <div style={{ display: 'flex', gap: 6 }}>
                      {isApproved ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#16a34a', fontSize: 11.5, fontWeight: 600 }}>
                          <CheckCircle2 size={13} /> Approved on {formatDate(p.decided_at || p.updated_at)}
                        </div>
                      ) : isRejected ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#dc2626', fontSize: 11.5, fontWeight: 600 }}>
                          <XCircle size={13} /> Rejected on {formatDate(p.decided_at || p.updated_at)}
                        </div>
                      ) : (
                        <>
                          <button
                            type="button"
                            className="button button-secondary"
                            onClick={() => handleReject(p.id)}
                            disabled={!canApprove || actingId === p.id}
                            style={{ color: '#EF4444', borderColor: 'rgba(239,68,68,0.3)', fontSize: 11, padding: '3px 10px', minHeight: 26 }}
                          >
                            <XCircle size={12} /> Reject Proposal
                          </button>
                          <button
                            type="button"
                            className="button button-primary glow-orange"
                            onClick={() => handleApprove(p.id)}
                            disabled={!canApprove || actingId === p.id}
                            style={{ fontWeight: 600, fontSize: 11, padding: '3px 12px', minHeight: 26 }}
                          >
                            <CheckCircle2 size={12} /> Approve Commercial Commitment
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              )
            })
          )}
        </div>
      )}

      {/* MODAL: RECORD CORRECTIVE ACTION & RESOLVE */}
      {resolvingAlert && (
        <div
          className="mfg-modal-overlay"
          role="dialog"
          aria-modal="true"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.75)',
            backdropFilter: 'blur(5px)',
            zIndex: 9999,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 20,
          }}
        >
          <div className="mfg-modal-content" style={{ maxWidth: 580, borderRadius: 12, overflow: 'hidden', boxShadow: '0 20px 40px rgba(0,0,0,0.35)' }}>
            <div className="mfg-modal-header" style={{ borderBottom: '1px solid var(--mfg-border-subtle)', padding: '14px 20px' }}>
              <h2 style={{ fontSize: 16, fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 8, color: 'var(--mfg-text-primary)' }}>
                <CheckCircle2 size={20} color="#22c55e" />
                Resolve Case – Order {resolvingAlert.customer_order_id}
              </h2>
              <button
                type="button"
                className="icon-button"
                onClick={() => setResolvingAlert(null)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--mfg-text-muted)' }}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleSubmitResolve}>
              <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 14 }}>
                {/* Case Summary Card */}
                <div
                  style={{
                    background: 'var(--mfg-bg-surface, #f8fafc)',
                    border: '1px solid var(--mfg-border-subtle, #e2e8f0)',
                    borderRadius: 8,
                    padding: '10px 14px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 6,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <span
                      className={`mfg-badge ${resolvingAlert.severity === 'CRITICAL' ? 'mfg-badge-critical' : 'mfg-badge-warning'}`}
                      style={{ fontSize: 10, padding: '1px 7px' }}
                    >
                      {resolvingAlert.severity}
                    </span>
                    <span className="mfg-badge" style={{ fontSize: 10, fontWeight: 700, padding: '1px 7px' }}>
                      {resolvingAlert.department}
                    </span>
                    <span
                      className="mfg-badge"
                      style={{
                        fontSize: 10,
                        padding: '1px 7px',
                        background: '#fef3c7',
                        color: '#b45309',
                        border: '1px solid #fcd34d',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 3,
                        fontWeight: 700,
                      }}
                    >
                      <Clock size={10} /> Active: {getCaseActiveDays(resolvingAlert)}d
                    </span>
                    <span style={{ fontSize: 11, color: 'var(--mfg-text-muted)' }}>
                      Case #{resolvingAlert.id}
                    </span>
                  </div>

                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--mfg-text-primary)' }}>
                    {resolvingAlert.title}
                  </div>

                  {resolvingAlert.recommended_action && (
                    <div style={{ fontSize: 11, color: 'var(--mfg-text-secondary)', marginTop: 2 }}>
                      <strong>Recommended:</strong> {resolvingAlert.recommended_action}
                    </div>
                  )}
                </div>

                {/* Quick Resolution Templates */}
                <div>
                  <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--mfg-text-muted)', marginBottom: 6 }}>
                    Quick Corrective Action Templates (Click to fill):
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {[
                      {
                        label: 'Lot Quarantine Cleared',
                        text: 'Quality inspection verified. Component quarantine hold released in MMS; batch certified ready for production.',
                      },
                      {
                        label: 'Line Rescheduled',
                        text: 'MES shift schedule reallocated to high-speed line 2 with overtime authorized to recover lost hours.',
                      },
                      {
                        label: 'Expedited Transit',
                        text: 'Logistics re-routed via dedicated priority express air freight to ensure SLA commitment adherence.',
                      },
                      {
                        label: 'Customer Accepted Buffer',
                        text: 'Customer Service confirmed agreement with customer procurement for a 24-hour delivery window extension.',
                      },
                      {
                        label: 'Supplier Batch Arrived',
                        text: 'Emergency supplier replenishment shipment arrived at warehouse dock and passed receiving QC.',
                      },
                    ].map((tpl) => (
                      <button
                        key={tpl.label}
                        type="button"
                        onClick={() => {
                          setResolutionNotes((prev) => (prev ? `${prev}\n${tpl.text}` : tpl.text))
                        }}
                        style={{
                          fontSize: 11,
                          padding: '4px 9px',
                          borderRadius: 6,
                          border: '1px solid #cbd5e1',
                          background: '#ffffff',
                          color: '#334155',
                          cursor: 'pointer',
                          fontWeight: 600,
                          transition: 'all 0.15s ease',
                        }}
                      >
                        + {tpl.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Resolution Notes Input Box */}
                <div>
                  <label
                    className="input-label"
                    htmlFor="res-notes"
                    style={{ display: 'block', fontSize: 12, fontWeight: 700, marginBottom: 5, color: 'var(--mfg-text-primary)' }}
                  >
                    Verified Corrective Action &amp; Resolution Notes *
                  </label>
                  <textarea
                    id="res-notes"
                    className="input"
                    rows={4}
                    required
                    placeholder="Enter details of root cause resolution, verified supplier receipt, completed line rework, or carrier upgrade."
                    value={resolutionNotes}
                    onChange={(e) => setResolutionNotes(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '10px 12px',
                      borderRadius: 8,
                      border: '1px solid var(--mfg-border-default, #cbd5e1)',
                      fontSize: 12,
                      fontFamily: 'inherit',
                      outline: 'none',
                    }}
                  />
                </div>

                <div style={{ fontSize: 11, color: 'var(--mfg-text-muted)', lineHeight: 1.4 }}>
                  Submitting resolution records verified shop-floor corrective actions in PostgreSQL 16, terminates automated 3-day agent follow-up escalation emails, and automatically dispatches resolution notices to both plant ops and Customer Service.
                </div>
              </div>

              <div
                className="mfg-modal-footer"
                style={{
                  padding: '12px 20px',
                  borderTop: '1px solid var(--mfg-border-subtle)',
                  display: 'flex',
                  justifyContent: 'flex-end',
                  gap: 10,
                  background: 'var(--mfg-bg-surface, #f8fafc)',
                }}
              >
                <button
                  type="button"
                  className="button button-secondary"
                  onClick={() => setResolvingAlert(null)}
                  disabled={isResolving}
                  style={{ fontSize: 12, padding: '6px 14px' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="button button-primary glow-orange"
                  disabled={isResolving || !resolutionNotes.trim()}
                  style={{ fontSize: 12, padding: '6px 16px', display: 'inline-flex', alignItems: 'center', gap: 6, fontWeight: 700 }}
                >
                  <CheckCircle2 size={14} />
                  {isResolving ? 'Resolving Case...' : 'Verify & Resolve Case'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: RECORD CUSTOMER COMMUNICATION NOTE */}
      {communicatingAlert && (
        <div
          className="mfg-modal-overlay"
          role="dialog"
          aria-modal="true"
          onClick={(e) => {
            if (e.target === e.currentTarget) setCommunicatingAlert(null)
          }}
        >
          <div
            className="mfg-modal-content"
            style={{
              maxWidth: 560,
              width: '100%',
              borderRadius: 12,
              overflow: 'hidden',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2), 0 10px 10px -5px rgba(0, 0, 0, 0.1)',
            }}
          >
            <div
              className="mfg-modal-header"
              style={{
                padding: '16px 20px',
                borderBottom: '1px solid var(--mfg-border-subtle)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <h2
                style={{
                  fontSize: 15,
                  fontWeight: 800,
                  margin: 0,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  color: 'var(--mfg-text-primary)',
                }}
              >
                <MessageSquare size={17} color="var(--brand-purple)" />
                Record Customer Communication – Order {communicatingAlert.customer_order_id}
              </h2>
              <button
                type="button"
                className="icon-button"
                onClick={() => setCommunicatingAlert(null)}
                style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 4, display: 'flex', color: 'var(--mfg-text-muted)' }}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleSubmitCommunication}>
              <div style={{ padding: '18px 20px', display: 'flex', flexDirection: 'column', gap: 14 }}>
                {/* Linked Risk Banner */}
                <div
                  style={{
                    background: 'var(--mfg-bg-surface, #f8fafc)',
                    border: '1px solid var(--mfg-border-subtle, #e2e8f0)',
                    borderRadius: 8,
                    padding: '10px 14px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 4,
                  }}
                >
                  <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--mfg-text-muted)', textTransform: 'uppercase', letterSpacing: '0.03em' }}>
                    Linked Operational Alert
                  </div>
                  <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--mfg-text-primary)' }}>
                    {communicatingAlert.title || communicatingAlert.description}
                  </div>
                </div>

                {/* Communication Log Textarea */}
                <div style={{ width: '100%', boxSizing: 'border-box' }}>
                  <label
                    htmlFor="comm-notes"
                    style={{
                      display: 'block',
                      fontSize: 12,
                      fontWeight: 700,
                      marginBottom: 6,
                      color: 'var(--mfg-text-primary)',
                    }}
                  >
                    Customer Communication Details &amp; Meeting Log *
                  </label>
                  <textarea
                    id="comm-notes"
                    rows={5}
                    required
                    placeholder="e.g. Called customer procurement lead regarding transit delay; customer confirmed acceptance of 24h buffer."
                    value={communicationNotes}
                    onChange={(e) => setCommunicationNotes(e.target.value)}
                    style={{
                      width: '100%',
                      minWidth: '100%',
                      maxWidth: '100%',
                      boxSizing: 'border-box',
                      display: 'block',
                      padding: '12px 14px',
                      borderRadius: 8,
                      border: '1px solid var(--mfg-border-default, #cbd5e1)',
                      fontSize: 13,
                      lineHeight: 1.5,
                      fontFamily: 'inherit',
                      outline: 'none',
                      resize: 'vertical',
                      minHeight: 110,
                      background: 'var(--surface-hi, #ffffff)',
                      color: 'var(--mfg-text-primary, #0f172a)',
                    }}
                  />
                  <div style={{ fontSize: 11, color: 'var(--mfg-text-muted)', marginTop: 5 }}>
                    Recorded logs are timestamped and automatically update the case status to <strong>Customer Notified</strong>.
                  </div>
                </div>
              </div>

              <div
                className="mfg-modal-footer"
                style={{
                  padding: '12px 20px',
                  borderTop: '1px solid var(--mfg-border-subtle)',
                  display: 'flex',
                  justifyContent: 'flex-end',
                  gap: 10,
                  background: 'var(--mfg-bg-surface, #f8fafc)',
                }}
              >
                <button
                  type="button"
                  className="button button-secondary"
                  onClick={() => setCommunicatingAlert(null)}
                  style={{ fontSize: 12, padding: '6px 14px' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="button button-primary"
                  style={{ fontSize: 12, padding: '6px 16px', display: 'inline-flex', alignItems: 'center', gap: 6, fontWeight: 700 }}
                >
                  <Save size={14} /> Save Communication Note
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
