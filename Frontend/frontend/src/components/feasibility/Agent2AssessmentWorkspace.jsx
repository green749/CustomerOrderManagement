import React, { useState, useEffect, useRef, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Play,
  Cpu,
  Layers,
  Factory,
  Warehouse,
  ShieldAlert,
  Truck,
  GitCommit,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  HelpCircle,
  Info,
  Clock,
  Calendar,
  Building2,
  Package,
  TrendingUp,
  FileCheck2,
  ArrowRight,
  ShieldCheck,
  ChevronDown,
  ChevronUp,
  RotateCcw,
  Sparkles,
  Slash,
} from 'lucide-react'
import { agentsApi } from '../../api/agents.api'
import { workflowApi } from '../../api/workflow.api'
import { formatDate, formatNumber } from '../../utils/format'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'
import { canManageApprovals } from '../../utils/permissions'

const DEPARTMENT_ORDER = ['ERP', 'MMS', 'MES', 'WMS', 'QMS', 'TMS', 'PLM']

const DEPT_META = {
  ERP: {
    name: 'ERP / Commercial SD',
    fullName: 'Enterprise Resource Planning & Sales Distribution',
    icon: FileCheck2,
    defaultChecked: 'Customer active status, credit rating, commercial contract pricing, duplicate purchase order check.',
  },
  MMS: {
    name: 'MMS / Material Planning',
    fullName: 'Material Management & Inventory Planning',
    icon: Layers,
    defaultChecked: 'Bill of Materials (BOM) explosion, on-hand component stock, ATP material shortage calculation.',
  },
  MES: {
    name: 'MES / Plant Production',
    fullName: 'Manufacturing Execution & Production Scheduling',
    icon: Factory,
    defaultChecked: 'Line capacity availability, active work order queues, plant daily throughput (CTP check).',
  },
  WMS: {
    name: 'WMS / Finished Goods',
    fullName: 'Warehouse Management & Dispatch Logistics',
    icon: Warehouse,
    defaultChecked: 'Finished goods storage staging, packaging specification readiness, dispatch bay slots.',
  },
  QMS: {
    name: 'QMS / Quality Assurance',
    fullName: 'Quality Management & Compliance Inspection',
    icon: ShieldAlert,
    defaultChecked: 'Product quality hold flags, quarantine audits, lot release requirements, historical scrap rate.',
  },
  TMS: {
    name: 'TMS / Transportation',
    fullName: 'Transport Management & Carrier Logistics',
    icon: Truck,
    defaultChecked: 'Shipping lane transit lead times, freight carrier booking buffer, regional transit window.',
  },
  PLM: {
    name: 'PLM / Engineering',
    fullName: 'Product Lifecycle & Engineering Revision',
    icon: GitCommit,
    defaultChecked: 'Engineering revision match, engineering freeze audit, hardware BOM configuration compatibility.',
  },
}

export function Agent2AssessmentWorkspace({
  assessmentId,
  selectedAssessmentId,
  pendingOrderPayload,
  onApprovalTransition,
  onAssessmentSelect,
  onAssessmentCreated,
}) {
  const queryClient = useQueryClient()
  const effectiveId = assessmentId || selectedAssessmentId
  const { user } = useAuth()
  const { toast } = useToast()
  const isApprover = canManageApprovals(user)
  const [expandedDept, setExpandedDept] = useState(null)
  const [decisionNote, setDecisionNote] = useState('')
  const [acting, setActing] = useState(false)
  const [approvalResult, setApprovalResult] = useState(null)
  const [showReasoning, setShowReasoning] = useState(false)

  const [searchParams, setSearchParams] = useSearchParams()
  const isPendingIntake = Boolean(pendingOrderPayload)
  const isAutoRun = searchParams.get('autoRun') === 'true' || searchParams.get('runNewOrder') === 'true' || isPendingIntake

  const [customAssessment, setCustomAssessment] = useState(null)
  const [triggerError, setTriggerError] = useState(null)

  // Reset customAssessment if effectiveId explicitly switches to another assessment
  const prevEffectiveIdRef = useRef(effectiveId)
  useEffect(() => {
    if (
      prevEffectiveIdRef.current &&
      effectiveId &&
      prevEffectiveIdRef.current !== effectiveId &&
      customAssessment?.assessment_id !== effectiveId
    ) {
      setCustomAssessment(null)
    }
    prevEffectiveIdRef.current = effectiveId
  }, [effectiveId, customAssessment])

  // ==========================================================================
  // AGENT 2 PIPELINE EXECUTION STATE
  // ==========================================================================
  const [expandedTraceSteps, setExpandedTraceSteps] = useState({})
  const [isScanningPipeline, setIsScanningPipeline] = useState(() => Boolean(isPendingIntake))
  const [flowCompleted, setFlowCompleted] = useState(() => !isPendingIntake)
  const [activeScanningDept, setActiveScanningDept] = useState(() => (isPendingIntake ? 'ERP' : null))
  const [flowArrowIdx, setFlowArrowIdx] = useState(-1)
  const [scannedDepts, setScannedDepts] = useState({})
  const [liveDeptRecords, setLiveDeptRecords] = useState({})
  const [liveAgentStage, setLiveAgentStage] = useState(null)

  const {
    data: queriedAssessment = null,
    isLoading: loading,
    error: queryError,
    refetch: loadAssessment,
  } = useQuery({
    queryKey: ['assessment-detail', effectiveId],
    queryFn: () => agentsApi.getAssessment(effectiveId),
    enabled: Boolean(effectiveId),
    staleTime: 60 * 1000,
  })

  // Initial skeleton assessment when arriving with pending order before backend completes
  const initialPendingAssessment = useMemo(() => {
    if (!pendingOrderPayload) return null
    return {
      assessment_id: 'PRE-ASM-NEW',
      customer_order_id: pendingOrderPayload.product_config?.po_number || 'PRE-ASM-NEW',
      customer_id: pendingOrderPayload.customer_id,
      customer_name: pendingOrderPayload.customer_name || pendingOrderPayload.customer_id,
      product_id: pendingOrderPayload.product_id,
      product_name: pendingOrderPayload.product_name || pendingOrderPayload.product_id,
      order_qty: pendingOrderPayload.order_qty,
      unit_price_inr: pendingOrderPayload.unit_price_inr || null,
      requested_delivery_date: pendingOrderPayload.requested_delivery_date,
      estimated_delivery_date: null,
      achievable_delivery_date: null,
      days_variance: null,
      verdict: null,
      overall_status: 'ANALYZING',
      confidence_level: 'ANALYZING',
      confidence_score: 'ANALYZING',
      result_source: null,
      agent_status: 'running',
      readiness_records: [],
    }
  }, [pendingOrderPayload])

  const assessment = customAssessment || queriedAssessment || initialPendingAssessment

  const evaluatedMap = useMemo(() => {
    if (isScanningPipeline) {
      return scannedDepts || {}
    }
    const map = {}
    if (assessment) {
      const evalList =
        assessment.departments_evaluated ||
        (assessment.readiness_records && assessment.readiness_records.length > 0
          ? assessment.readiness_records.map((r) => r.department)
          : null)
      if (evalList && evalList.length > 0) {
        evalList.forEach((code) => {
          map[code] = true
        })
      } else if (assessment.overall_status && assessment.overall_status !== 'ANALYZING') {
        DEPARTMENT_ORDER.forEach((code) => {
          map[code] = true
        })
      }
    }
    return map
  }, [assessment, isScanningPipeline, scannedDepts])

  // ==========================================================================
  // REAL BACKEND-DRIVEN SSE STREAMING PIPELINE RUNNER (SEQUENTIAL ONE-BY-ONE)
  // ==========================================================================
  const runSequentialDepartmentFlow = async (streamCallFn) => {
    if (!streamCallFn) return
    setTriggerError(null)
    setIsScanningPipeline(true)
    setFlowCompleted(false)
    setScannedDepts({})
    setLiveDeptRecords({})
    setLiveAgentStage(null)
    setFlowArrowIdx(-1)
    setActiveScanningDept(DEPARTMENT_ORDER[0])

    // Sequential display queue: reveals each REAL backend dept_done result one card at a time
    // (ERP -> MMS -> MES -> WMS -> QMS -> TMS -> PLM) so fast/prefetched departments never pop all at once.
    let displayChain = Promise.resolve()
    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
    const enqueue = (fn) => {
      displayChain = displayChain.then(fn).catch(() => {})
      return displayChain
    }

    const handleStreamEvent = (evt) => {
      if (!evt || !evt.event) return
      if (evt.event === 'dept_done' && evt.department) {
        const deptCode = evt.department
        const deptRecord = evt.record
        const idx = DEPARTMENT_ORDER.indexOf(deptCode)
        enqueue(async () => {
          setActiveScanningDept(deptCode)
          await sleep(1500)
          setScannedDepts((prev) => ({ ...prev, [deptCode]: true }))
          if (deptRecord) {
            setLiveDeptRecords((prev) => ({ ...prev, [deptCode]: deptRecord }))
          }
          if (idx >= 0 && idx < DEPARTMENT_ORDER.length - 1) {
            setFlowArrowIdx(idx)
            await sleep(500)
            setActiveScanningDept(DEPARTMENT_ORDER[idx + 1])
          } else {
            setFlowArrowIdx(idx)
            await sleep(500)
            setActiveScanningDept(null)
          }
        })
      } else if (evt.event === 'agent_start') {
        const msg = evt.message || 'Domo AI Agent 2 reasoning & tool-calling...'
        enqueue(async () => {
          setActiveScanningDept(null)
          setFlowArrowIdx(DEPARTMENT_ORDER.length)
          setLiveAgentStage(msg)
        })
      } else if (evt.event === 'agent_step') {
        const msg = `Domo AI Agent Step ${evt.step || ''}: ${evt.tool || 'tool'} (${evt.status || 'running'})`
        enqueue(async () => {
          setActiveScanningDept(null)
          setLiveAgentStage(msg)
        })
      }
    }

    try {
      const resolvedData = await streamCallFn(handleStreamEvent)
      // Wait for all queued one-by-one card transitions to finish cleanly
      await displayChain
      if (resolvedData) {
        setCustomAssessment(resolvedData)
        const evalList = resolvedData.departments_evaluated || DEPARTMENT_ORDER
        const verifiedMap = {}
        evalList.forEach((code) => { verifiedMap[code] = true })
        setScannedDepts(verifiedMap)
        queryClient.setQueryData(['assessment-detail', resolvedData.assessment_id], resolvedData)
        queryClient.invalidateQueries({ queryKey: ['assessments-list'], refetchType: 'none' })

        // Update address bar silently without triggering React Router reload or route changes
        if (resolvedData.assessment_id) {
          try {
            window.history.replaceState(
              null,
              '',
              `/assessments?id=${encodeURIComponent(resolvedData.assessment_id)}`
            )
          } catch (e) {}
        }

        if (onAssessmentCreated) {
          onAssessmentCreated(resolvedData)
        }
      }

      setIsScanningPipeline(false)
      setActiveScanningDept(null)
      setLiveAgentStage(null)
      setFlowArrowIdx(-1)
      setFlowCompleted(true)

      try {
        sessionStorage.removeItem('pending_agent2_intake')
      } catch (e) {}

      // Clean query params from URL silently
      try {
        const url = new URL(window.location.href)
        url.searchParams.delete('autoRun')
        url.searchParams.delete('runNewOrder')
        window.history.replaceState(null, '', url.pathname + (url.search ? url.search : ''))
      } catch (e) {}

      const finalStatus = resolvedData?.overall_status || assessment?.overall_status || 'Unknown'
      toast.success(
        `Agent 2 Feasibility Assessment Complete! Status: ${finalStatus}`,
        { title: 'Feasibility Evaluated' }
      )
    } catch (err) {
      console.error('Agent 2 assessment trigger error:', err)
      setIsScanningPipeline(false)
      setActiveScanningDept(null)
      setLiveAgentStage(null)
      const msg = err.response?.data?.detail || err.message || 'Agent 2 feasibility assessment failed.'
      setTriggerError(msg)
      toast.error(`Agent 2 Feasibility Assessment failed: ${msg}`, { title: 'Assessment Error' })
    }
  }

  const triggerAgent2Flow = () => {
    if (!pendingOrderPayload) return
    return runSequentialDepartmentFlow((onEvent) => agentsApi.assessNewOrderStream(pendingOrderPayload, onEvent))
  }

  const handleRunFeasibilityFlow = () => {
    if (isScanningPipeline || !effectiveId) return
    return runSequentialDepartmentFlow((onEvent) => agentsApi.reassessOrderStream(effectiveId, onEvent))
  }

  // Trigger Agent 2 execution upon arrival with pending order intake
  const pendingTriggerRef = useRef(false)
  const handleRetryPendingFlow = () => {
    pendingTriggerRef.current = false
    triggerAgent2Flow()
  }

  useEffect(() => {
    if (pendingOrderPayload && !pendingTriggerRef.current) {
      pendingTriggerRef.current = true
      triggerAgent2Flow()
    }
  }, [pendingOrderPayload])

  // Clean ?autoRun=true on mount without replaying fake animations
  const autoRunDoneRef = useRef(false)
  useEffect(() => {
    if (isAutoRun && !autoRunDoneRef.current) {
      autoRunDoneRef.current = true
      try {
        const url = new URL(window.location.href)
        url.searchParams.delete('autoRun')
        url.searchParams.delete('runNewOrder')
        window.history.replaceState(null, '', url.pathname + (url.search ? url.search : ''))
      } catch (e) {}
    }
  }, [isAutoRun])
  const error = queryError ? (queryError.response?.data?.detail || queryError.message || 'Failed to load assessment.') : ''

  const propStatus = approvalResult?.status || assessment?.proposal?.status || 'PENDING'
  const isApprovedProposal = propStatus === 'APPROVED'
  const isRejectedProposal = propStatus === 'REJECTED'
  const isDecided = isApprovedProposal || isRejectedProposal

  const handleApprove = async () => {
    if (!assessment?.proposal_id || acting) return
    setActing(true)
    const toastId = toast.success(
      `Commercial commitment approved for ${assessment.assessment_id}. Order monitoring activated.`,
      { title: 'Commercial Commitment Approved!' }
    )
    try {
      const res = await workflowApi.approveProposal(assessment.proposal_id, decisionNote || 'Approved via Agent 2 Feasibility Workspace')
      setApprovalResult({ status: 'APPROVED', date: res.proposed_date, approver: user?.full_name || user?.email })
      if (onApprovalTransition) {
        onApprovalTransition({ assessment, proposal: res })
      }
    } catch (err) {
      if (toastId) toast.dismiss(toastId)
      toast.error(`Approval failed: ${err.response?.data?.detail || err.message}`, { title: 'Approval Failed' })
    } finally {
      setActing(false)
    }
  }

  const handleReject = async () => {
    if (!assessment?.proposal_id || acting) return
    setActing(true)
    const toastId = toast.info(
      `Commitment proposal for ${assessment.assessment_id} has been rejected.`,
      { title: 'Proposal Rejected' }
    )
    try {
      const res = await workflowApi.rejectProposal(assessment.proposal_id, decisionNote || 'Rejected via Agent 2 Feasibility Workspace')
      setApprovalResult({ status: 'REJECTED', date: res.proposed_date, approver: user?.full_name || user?.email })
    } catch (err) {
      if (toastId) toast.dismiss(toastId)
      toast.error(`Rejection failed: ${err.response?.data?.detail || err.message}`, { title: 'Rejection Failed' })
    } finally {
      setActing(false)
    }
  }

  if (loading && !assessment && !pendingOrderPayload && !customAssessment) {
    return (
      <div className="card" style={{ padding: 40, textAlign: 'center' }}>
        <Cpu size={32} color="#f58a3a" className="animate-spin" style={{ margin: '0 auto 16px' }} />
        <h3 style={{ fontSize: 16, fontWeight: 700 }}>Evaluating Feasibility Across 7 Departments…</h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: 12 }}>
          Agent 2 is auditing ERP, MMS, MES, WMS, QMS, TMS, and PLM evidence.
        </p>
      </div>
    )
  }

  if ((error || !assessment) && !pendingOrderPayload && !customAssessment) {
    return (
      <div className="card" style={{ padding: 24, borderColor: '#ff6b81' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, color: '#ff6b81' }}>
          <XCircle size={22} />
          <div>
            <strong>Unable to load assessment</strong>
            <p style={{ fontSize: 12, margin: '4px 0 0', color: 'var(--text-secondary)' }}>{error}</p>
          </div>
        </div>
        <button type="button" className="button button-secondary" onClick={loadAssessment} style={{ marginTop: 16 }}>
          <RotateCcw size={14} /> Retry Assessment Fetch
        </button>
      </div>
    )
  }

  // Map 7 departments from readiness_records
  const records = assessment.readiness_records || []
  const deptsEvaluated = assessment.departments_evaluated || []
  const stoppedEarly = Boolean(assessment.stopped_early)
  const stopReason = assessment.stop_reason

  const departments = DEPARTMENT_ORDER.map((code) => {
    const record = (isScanningPipeline && liveDeptRecords[code]) || records.find((r) => r.department === code) || {}
    const meta = DEPT_META[code] || { name: code, icon: HelpCircle, defaultChecked: '' }
    let status = record.readiness_status
    if (!status) {
      if (isScanningPipeline || assessment.overall_status === 'ANALYZING' || triggerError) {
        status = 'ANALYZING'
      } else if (stoppedEarly && !deptsEvaluated.includes(code)) {
        status = 'NOT_EVALUATED'
      } else {
        status = 'READY'
      }
    } else if (stoppedEarly && !deptsEvaluated.includes(code)) {
      status = 'NOT_EVALUATED'
    }

    const reason = record.reason_for_issue || (status === 'NOT_EVALUATED' ? (stopReason ? `Not evaluated: stopped at ${stopReason}` : 'Not evaluated') : null)

    return {
      code,
      meta,
      status,
      evidence: record.available_evidence || {},
      issue: record.identified_issue,
      reason: reason,
      action: record.required_action,
      role: record.responsible_role,
      delayDays: record.estimated_delay_days,
      missingInfo: record.missing_info,
      dataSource: record.data_source,
    }
  })

  const readyCount = departments.filter((d) => d.status === 'READY').length
  const partialCount = departments.filter((d) => ['PARTIAL', 'PARTIALLY_READY', 'PARTIALLY READY'].includes(d.status)).length
  const atRiskCount = departments.filter((d) => d.status === 'AT_RISK').length
  const blockedCount = departments.filter((d) => ['NOT_READY', 'BLOCKED', 'INSUFFICIENT_DATA', 'MISSING_DATA'].includes(d.status)).length

  const getStatusBadge = (status) => {
    switch (status) {
      case 'ANALYZING':
        return (
          <span className="mfg-badge" style={{ background: 'rgba(111, 61, 186, 0.12)', color: 'var(--brand-purple)', border: '1px solid rgba(111, 61, 186, 0.3)', fontWeight: 700 }} title="Analyzing evidence across departments">
            <Sparkles size={11} className="animate-spin" /> ANALYZING
          </span>
        )
      case 'NOT_EVALUATED':
        return (
          <span className="mfg-badge" style={{ background: 'rgba(100, 116, 139, 0.1)', color: '#64748b', border: '1px solid rgba(100, 116, 139, 0.3)' }} title="Department skipped due to early blocker">
            <Slash size={11} /> NOT EVALUATED
          </span>
        )
      case 'FEASIBLE':
      case 'READY':
        return (
          <span className="mfg-badge mfg-badge-ready" title="Feasible and ready">
            <CheckCircle2 size={11} /> {status === 'FEASIBLE' ? 'FEASIBLE' : 'READY'}
          </span>
        )
      case 'PARTIAL':
      case 'PARTIALLY_READY':
      case 'PARTIALLY READY':
        return (
          <span className="mfg-badge mfg-badge-info" title="Partially ready - some adjustments required">
            <Info size={11} /> PARTIAL
          </span>
        )
      case 'AT_RISK':
        return (
          <span className="mfg-badge mfg-badge-at-risk" title="At risk - schedule or capacity deviation">
            <AlertTriangle size={11} /> AT RISK
          </span>
        )
      case 'NOT_READY':
      case 'BLOCKED':
        return (
          <span className="mfg-badge mfg-badge-blocked" title="Blocked - critical blocker identified">
            <XCircle size={11} /> BLOCKED
          </span>
        )
      case 'INSUFFICIENT_DATA':
      case 'MISSING_DATA':
        return (
          <span className="mfg-badge mfg-badge-neutral" title="No data - evidence records not found">
            <HelpCircle size={11} /> NO DATA
          </span>
        )
      default:
        return (
          <span className="mfg-badge mfg-badge-info">
            {status ? status.replace(/_/g, ' ') : 'PENDING'}
          </span>
        )
    }
  }

  return (
    <div className="page-stack" style={{ gap: 20 }}>
      {/* ERROR BANNER IF AGENT 2 ASSESSMENT FAILED */}
      {triggerError && (
        <div className="card" style={{ padding: 18, borderColor: '#ef4444', background: 'rgba(239, 68, 68, 0.06)', borderRadius: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: '#dc2626' }}>
              <AlertTriangle size={20} />
              <div>
                <div style={{ fontWeight: 700, fontSize: 13 }}>Agent 2 Feasibility Assessment Encountered an Issue</div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>{triggerError}</div>
              </div>
            </div>
            <button
              type="button"
              className="button button-primary"
              onClick={handleRetryPendingFlow}
              style={{ padding: '7px 16px', fontSize: 12, display: 'inline-flex', alignItems: 'center', gap: 6 }}
            >
              <RotateCcw size={13} /> Retry Assessment
            </button>
          </div>
        </div>
      )}

      {/* 1. VISUAL LIFECYCLE PROGRESSION BANNER */}
      <div className="card" style={{ background: 'var(--surface-hi)', border: '1px solid var(--line)', padding: 18 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <div className="eyebrow" style={{ color: 'var(--brand-orange)' }}>
              AGENT 2 INTERACTIVE WORKSPACE · {assessment.assessment_id}
            </div>
            <h2 style={{ fontSize: 18, fontWeight: 800, margin: '4px 0 0', display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-primary)' }}>
              <Cpu size={20} color="var(--brand-orange)" />
              Multi-Department Feasibility Assessment &amp; Commitment Plan
            </h2>
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
            {isScanningPipeline || assessment.agent_status === 'running' || assessment.overall_status === 'ANALYZING' ? (
              <span
                className="mfg-badge animate-pulse"
                style={{
                  background: 'rgba(111, 61, 186, 0.12)',
                  color: 'var(--brand-purple)',
                  border: '1px solid rgba(111, 61, 186, 0.35)',
                  fontWeight: 700,
                  fontSize: 11,
                  padding: '3px 10px',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 5,
                }}
                title="Domo AI Agent 2 is actively evaluating departments and calling tools"
              >
                <Cpu size={12} /> AI Agent Running (Domo, tool-calling)
              </span>
            ) : assessment.result_source === 'AGENT' ? (
              <span
                className="mfg-badge"
                style={{
                  background: 'rgba(34, 197, 94, 0.12)',
                  color: '#16a34a',
                  border: '1px solid rgba(34, 197, 94, 0.35)',
                  fontWeight: 700,
                  fontSize: 11,
                  padding: '3px 10px',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 5,
                }}
                title="Feasibility evaluated by real Domo LLM agent via tool calls"
              >
                <Cpu size={12} /> AI Agent (Domo, tool-calling)
              </span>
            ) : (
              <span
                className="mfg-badge"
                style={{
                  background: 'rgba(245, 158, 11, 0.12)',
                  color: '#d97706',
                  border: '1px solid rgba(245, 158, 11, 0.35)',
                  fontWeight: 700,
                  fontSize: 11,
                  padding: '3px 10px',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 5,
                }}
                title="Feasibility calculated via deterministic rules"
              >
                <FileCheck2 size={12} /> {assessment.result_source === 'RULES' ? 'Deterministic Rules Mode' : 'Rule-based reference (AI agent unavailable)'}
              </span>
            )}
            <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Overall Feasibility:</span>
            {getStatusBadge(assessment.overall_status)}
          </div>
        </div>

        {/* Delivery Verdict Banner */}
        {assessment.verdict && (
          <div
            style={{
              marginTop: 10,
              padding: '8px 14px',
              borderRadius: 8,
              background:
                assessment.verdict === 'ON_TIME'
                  ? 'rgba(34, 197, 94, 0.08)'
                  : assessment.verdict === 'DELAYED'
                  ? 'rgba(239, 68, 68, 0.08)'
                  : 'rgba(245, 158, 11, 0.08)',
              border: `1px solid ${
                assessment.verdict === 'ON_TIME'
                  ? 'rgba(34, 197, 94, 0.3)'
                  : assessment.verdict === 'DELAYED'
                  ? 'rgba(239, 68, 68, 0.3)'
                  : 'rgba(245, 158, 11, 0.3)'
              }`,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              fontSize: 12,
              fontWeight: 600,
              color:
                assessment.verdict === 'ON_TIME'
                  ? '#15803d'
                  : assessment.verdict === 'DELAYED'
                  ? '#b91c1c'
                  : '#b45309',
            }}
          >
            {assessment.verdict === 'ON_TIME' ? (
              <CheckCircle2 size={15} />
            ) : (
              <AlertTriangle size={15} />
            )}
            <span>
              Delivery Verdict:{' '}
              <strong>
                {assessment.verdict === 'ON_TIME'
                  ? 'WILL MEET PROMISED DATE'
                  : assessment.verdict === 'DELAYED'
                  ? `DELAYED BY ${assessment.delay_days || assessment.days_variance || 0} DAYS`
                  : 'AT RISK OF DELAY'}
              </strong>
              {assessment.revised_estimated_date && (
                <span style={{ marginLeft: 8, fontWeight: 500 }}>
                  (Revised Target: {formatDate(assessment.revised_estimated_date)})
                </span>
              )}
            </span>
          </div>
        )}

        {/* Agent Disagreement Notice */}
        {assessment.agent_disagreement && (
          <div
            style={{
              padding: '10px 14px',
              background: 'rgba(245, 158, 11, 0.1)',
              border: '1px solid #f59e0b',
              borderRadius: 8,
              color: '#b45309',
              fontSize: 12,
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              marginTop: 10,
            }}
          >
            <AlertTriangle size={16} style={{ color: '#d97706', flexShrink: 0 }} />
            <span>
              {assessment.agent_status === 'success' ? (
                <>
                  <strong>Agent Disagreement Notice:</strong> The AI Agent proposal diverged from the deterministic rule baseline (date variance &gt; 2 days or status divergence). Per safety governance, confidence is capped at MEDIUM and routed for human commercial review.
                </>
              ) : (
                <>
                  <strong>Rules Fallback Notice:</strong> Agent evaluation was not adopted ({assessment.agent_status || 'validation failed'}). Rule engine baseline was applied and routed for human review.
                </>
              )}
            </span>
          </div>
        )}

        {/* Central Visual Path: CUSTOMER ORDER -> AGENT 2 -> 7 DEPARTMENTS -> FEASIBILITY RESULT -> HUMAN APPROVAL */}
        <div style={{ margin: '16px 0 0', padding: '12px 16px', background: 'var(--kg-bg-2)', borderRadius: 10, border: '1px solid var(--line)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, fontSize: 11 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-primary)', fontWeight: 600 }}>
            <Package size={14} color="var(--brand-blue)" />
            <span>Order #{assessment.customer_order_id || 'NEW'}</span>
          </div>
          <ArrowRight size={14} color="var(--text-muted)" />
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--brand-orange)', fontWeight: 700 }}>
            <Cpu size={14} />
            <span>Agent 2 Intake</span>
          </div>
          <ArrowRight size={14} color="var(--text-muted)" />
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 700, color: '#10b981' }}>
            <Factory size={14} />
            <span>7 Departments Audited ({readyCount}/7 Ready)</span>
          </div>
          <ArrowRight size={14} color="var(--text-muted)" />
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--brand-purple)', fontWeight: 600 }}>
            <Calendar size={14} />
            <span>Feasible Delivery Plan</span>
          </div>
          <ArrowRight size={14} color="var(--text-muted)" />
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: isApprovedProposal ? '#10b981' : assessment.proposal_id ? 'var(--brand-purple)' : 'var(--text-secondary)', fontWeight: 600 }}>
            <ShieldCheck size={14} />
            <span>CS Review {assessment.proposal_id ? `(#${assessment.proposal_id})` : ''} {isApprovedProposal ? '✓ Approved' : ''}</span>
          </div>
        </div>
      </div>

      {/* 2. ORDER CONTEXT HEADER */}
      <div className="card" style={{ padding: 18 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 14 }}>
          <div>
            <span style={{ fontSize: 10, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Customer</span>
            <div style={{ fontSize: 13, fontWeight: 700 }}>
              {assessment.customer_name ? `${assessment.customer_name} (${assessment.customer_id})` : assessment.customer_id}
            </div>
          </div>
          <div>
            <span style={{ fontSize: 10, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Product Model</span>
            <div style={{ fontSize: 13, fontWeight: 700 }}>
              {assessment.product_name ? `${assessment.product_name} (${assessment.product_id})` : assessment.product_id}
            </div>
          </div>
          <div>
            <span style={{ fontSize: 10, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Order Demand</span>
            <div style={{ fontSize: 13, fontWeight: 700 }}>{formatNumber(assessment.order_qty)} Units</div>
          </div>
          <div>
            <span style={{ fontSize: 10, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Requested Delivery</span>
            <div style={{ fontSize: 13, fontWeight: 700 }}>{formatDate(assessment.requested_delivery_date)}</div>
          </div>
          <div>
            <span style={{ fontSize: 10, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Confidence Level</span>
            <div style={{
              fontSize: 13,
              fontWeight: 700,
              color:
                assessment.confidence_level === 'HIGH'
                  ? '#16a34a'
                  : assessment.confidence_level === 'MEDIUM'
                  ? '#d97706'
                  : assessment.confidence_level === 'LOW'
                  ? '#dc2626'
                  : 'var(--brand-orange)',
            }}>
              {assessment.confidence_level}
            </div>
          </div>
        </div>
      </div>

      {/* 3. SEVEN DEPARTMENT ASSESSMENT PANELS */}
      <div>
        {/* Dynamic Keyframes for Flow Laser & Active Pulse */}
        <style>{`
          @keyframes flowLaser {
            0% { left: 0%; opacity: 0.3; }
            50% { opacity: 1; }
            100% { left: 100%; opacity: 0.3; }
          }
          @keyframes pulseScanBorder {
            0% { box-shadow: 0 0 0 0 rgba(111, 61, 186, 0.5); border-color: var(--brand-purple); }
            50% { box-shadow: 0 0 0 8px rgba(111, 61, 186, 0.12); border-color: #a78bfa; }
            100% { box-shadow: 0 0 0 0 rgba(111, 61, 186, 0); border-color: var(--brand-purple); }
          }
          .scanning-pulse {
            animation: pulseScanBorder 0.85s infinite ease-in-out !important;
          }
        `}</style>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14, flexWrap: 'wrap', gap: 10 }}>
          <h3 style={{ fontSize: 14, fontWeight: 800, margin: 0, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--brand-orange)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <Factory size={16} /> Seven-Department Execution &amp; Evidence Audit
          </h3>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, background: 'var(--kg-bg-2)', padding: '5px 12px', borderRadius: 8, border: '1px solid var(--line)' }}>
              <span style={{ color: '#16a34a', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#16a34a' }} />
                {readyCount} Ready
              </span>
              {(partialCount > 0 || atRiskCount > 0) && (
                <>
                  <span style={{ color: 'var(--text-muted)' }}>·</span>
                  <span style={{ color: '#d97706', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#d97706' }} />
                    {partialCount + atRiskCount} At Risk / Partial
                  </span>
                </>
              )}
              <span style={{ color: 'var(--text-muted)' }}>·</span>
              <span style={{ color: '#dc2626', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#dc2626' }} />
                {blockedCount} Blocked / No Data
              </span>
            </div>

            <button
              type="button"
              onClick={handleRunFeasibilityFlow}
              disabled={isScanningPipeline}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '6px 14px',
                fontSize: 12,
                fontWeight: 700,
                borderRadius: 8,
                background: 'linear-gradient(135deg, var(--brand-purple), var(--dr-purple))',
                color: 'white',
                border: 'none',
                cursor: isScanningPipeline ? 'wait' : 'pointer',
                boxShadow: '0 2px 8px rgba(111, 61, 186, 0.25)',
                transition: 'all 0.15s ease',
              }}
            >
              <Play size={13} fill="currentColor" />
              {isScanningPipeline ? 'Scanning Flow...' : 'Run Feasibility Flow'}
            </button>
          </div>
        </div>

        {/* CONNECTED CONDUIT PIPELINE (CARDS & FLOWING ARROW MARKS) */}
        <div
          className="card"
          style={{
            background: 'var(--surface-hi)',
            border: '1px solid var(--line)',
            borderRadius: 14,
            padding: '16px 14px',
            marginBottom: 16,
            boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
          }}
        >
          {isScanningPipeline && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '6px 12px',
                marginBottom: 12,
                background: 'var(--brand-purple-soft)',
                border: '1px solid rgba(111, 61, 186, 0.2)',
                borderRadius: 8,
                fontSize: 11.5,
              }}
            >
              <span style={{ color: 'var(--brand-purple)', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <Sparkles size={13} />
                {liveAgentStage
                  ? liveAgentStage
                  : activeScanningDept
                  ? `Auditing ${activeScanningDept} Department Telemetry...`
                  : 'Auditing 7 Conduits...'}
              </span>
              <span style={{ color: 'var(--text-muted)' }}>Sequential Feasibility Verification</span>
            </div>
          )}

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 2,
              overflowX: 'auto',
              scrollbarWidth: 'none',
            }}
          >
            {departments.map((dept, index) => {
              const Icon = dept.meta.icon
              const isCurrentScanning = activeScanningDept === dept.code
              const isScanned = Boolean(evaluatedMap[dept.code])
              const isConnecting = flowArrowIdx === index
              const isPassed = isScanned && (flowArrowIdx > index || (!isScanningPipeline && Object.keys(evaluatedMap).length > 0))
              const isReady = dept.status === 'READY' || dept.status === 'FEASIBLE'
              const isBlocked = dept.status === 'BLOCKED' || dept.status === 'NOT_READY'
              const isAtRisk = dept.status === 'AT_RISK' || dept.status === 'PARTIAL' || dept.status === 'PARTIALLY_READY'
              const isSelected = expandedDept === dept.code

              return (
                <React.Fragment key={dept.code}>
                  {/* Conduit Card */}
                  <div
                    onClick={() => setExpandedDept(isSelected ? null : dept.code)}
                    className={`card ${isCurrentScanning ? 'scanning-pulse' : ''}`}
                    style={{
                      flex: 1,
                      minWidth: 96,
                      background: isCurrentScanning
                        ? 'var(--brand-purple-soft)'
                        : isSelected
                        ? 'var(--brand-orange-soft, rgba(245, 138, 58, 0.1))'
                        : isScanned && isReady
                        ? 'rgba(34, 197, 94, 0.04)'
                        : isScanned && isBlocked
                        ? 'rgba(239, 68, 68, 0.04)'
                        : isScanned && isAtRisk
                        ? 'rgba(245, 158, 11, 0.04)'
                        : 'transparent',
                      border: isCurrentScanning
                        ? '2px solid var(--brand-purple)'
                        : isSelected
                        ? '2px solid var(--brand-orange)'
                        : isScanned && isReady
                        ? '1px solid rgba(34, 197, 94, 0.45)'
                        : isScanned && isBlocked
                        ? '1px solid rgba(239, 68, 68, 0.45)'
                        : isScanned && isAtRisk
                        ? '1px solid rgba(245, 158, 11, 0.45)'
                        : '1px solid var(--line)',
                      borderRadius: 10,
                      padding: '12px 6px',
                      textAlign: 'center',
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      cursor: 'pointer',
                      transition: 'all 0.22s ease',
                      boxShadow: isCurrentScanning
                        ? '0 4px 14px rgba(111, 61, 186, 0.22)'
                        : isSelected
                        ? '0 3px 10px rgba(245, 138, 58, 0.18)'
                        : 'none',
                    }}
                    title={`Click to inspect ${dept.code} evidence audit details`}
                  >
                    {/* Department Icon */}
                    <div
                      style={{
                        width: 30,
                        height: 30,
                        borderRadius: 8,
                        background: isCurrentScanning
                          ? 'var(--brand-purple)'
                          : isScanned && isReady
                          ? 'rgba(34, 197, 94, 0.14)'
                          : isScanned && isBlocked
                          ? 'rgba(239, 68, 68, 0.14)'
                          : isScanned && isAtRisk
                          ? 'rgba(245, 158, 11, 0.14)'
                          : 'rgba(0, 0, 0, 0.04)',
                        color: isCurrentScanning
                          ? 'white'
                          : isScanned && isReady
                          ? '#16a34a'
                          : isScanned && isBlocked
                          ? '#dc2626'
                          : isScanned && isAtRisk
                          ? '#d97706'
                          : 'var(--text-muted)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        marginBottom: 6,
                        transition: 'all 0.2s ease',
                      }}
                    >
                      <Icon size={15} />
                    </div>

                    {/* Department Code */}
                    <div style={{ fontSize: 13, fontWeight: 800, color: 'var(--text-primary)' }}>
                      {dept.code}
                    </div>

                    {/* Sub-name */}
                    <div
                      style={{
                        fontSize: 9.5,
                        color: 'var(--text-muted)',
                        margin: '2px 0 6px',
                        maxWidth: 95,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                      title={dept.meta.name}
                    >
                      {dept.meta.name.split('/')[1]?.trim() || dept.meta.name}
                    </div>

                    {/* Status Pill */}
                    <div>
                      {isCurrentScanning ? (
                        <span
                          style={{
                            fontSize: 9.5,
                            fontWeight: 700,
                            padding: '2px 7px',
                            borderRadius: 10,
                            background: 'rgba(111, 61, 186, 0.14)',
                            color: 'var(--brand-purple)',
                          }}
                          className="animate-pulse"
                        >
                          ● Scanning
                        </span>
                      ) : isScanned ? (
                        getStatusBadge(dept.status)
                      ) : (
                        <span
                          style={{
                            fontSize: 9.5,
                            fontWeight: 600,
                            padding: '2px 7px',
                            borderRadius: 10,
                            background: 'rgba(0,0,0,0.04)',
                            color: 'var(--text-muted)',
                          }}
                        >
                          ● Queued
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Proper Flow Arrow Mark Between Cards */}
                  {index < departments.length - 1 && (
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        position: 'relative',
                        width: 26,
                        flexShrink: 0,
                        height: 40,
                        margin: '0 1px',
                      }}
                      title={`Conduit Flow: ${dept.code} → ${departments[index + 1]?.code}`}
                    >
                      <svg
                        width="26"
                        height="18"
                        viewBox="0 0 26 18"
                        fill="none"
                        style={{ overflow: 'visible' }}
                      >
                        <defs>
                          <linearGradient id={`flowArrowGradA2-${index}`} x1="0%" y1="0%" x2="100%" y2="0%">
                            <stop offset="0%" stopColor="#8b5cf6" />
                            <stop offset="100%" stopColor="#3b82f6" />
                          </linearGradient>
                        </defs>

                        {/* Crisp Right Arrow */}
                        <path
                          d="M 2 9 H 20 M 14 4 L 21 9 L 14 14"
                          stroke={
                            isConnecting
                              ? `url(#flowArrowGradA2-${index})`
                              : isPassed
                              ? 'var(--brand-purple)'
                              : 'var(--line)'
                          }
                          strokeWidth={isConnecting ? '2.8' : '2.2'}
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          style={{
                            transition: 'all 0.25s ease',
                            filter: isConnecting ? 'drop-shadow(0 0 6px rgba(139, 92, 246, 0.75))' : 'none',
                          }}
                        />

                        {/* Laser Beam Pulse traveling along arrow */}
                        {isConnecting && (
                          <circle
                            cx="11"
                            cy="9"
                            r="2.8"
                            fill="#c084fc"
                            style={{
                              animation: 'flowLaser 0.5s infinite linear',
                              filter: 'drop-shadow(0 0 5px #a855f7)',
                            }}
                          />
                        )}
                      </svg>
                    </div>
                  )}
                </React.Fragment>
              )
            })}
          </div>
        </div>

        <div className="seven-dept-grid">
          {departments.map((dept) => {
            const Icon = dept.meta.icon
            const isExpanded = expandedDept === dept.code
            const isDeptScanned = Boolean(evaluatedMap[dept.code])
            const isDeptScanning = activeScanningDept === dept.code

            return (
              <div
                key={dept.code}
                className={`dept-card ${isDeptScanning ? 'scanning-pulse' : ''}`}
                style={{
                  transition: 'all 0.3s ease',
                  opacity: (!isDeptScanned && isScanningPipeline && !isDeptScanning) ? 0.45 : 1,
                  border: isDeptScanning
                    ? '2px solid var(--brand-purple)'
                    : isExpanded
                    ? '2px solid var(--brand-orange)'
                    : undefined,
                }}
              >
                <div className="dept-card-header">
                  <div className="dept-header-top-row">
                    <div className="dept-header-identity">
                      <div className="dept-icon-box" style={{ background: isDeptScanning ? 'var(--brand-purple)' : undefined, color: isDeptScanning ? 'white' : undefined }}>
                        <Icon size={16} />
                      </div>
                      <span className="dept-code-tag">{dept.code}</span>
                    </div>
                    <div className="dept-badge-container">
                      {isDeptScanning ? (
                        <span
                          style={{
                            fontSize: 9.5,
                            fontWeight: 700,
                            padding: '2px 7px',
                            borderRadius: 10,
                            background: 'rgba(111, 61, 186, 0.14)',
                            color: 'var(--brand-purple)',
                          }}
                          className="animate-pulse"
                        >
                          ● Scanning
                        </span>
                      ) : isDeptScanned || !isScanningPipeline ? (
                        getStatusBadge(dept.status)
                      ) : (
                        <span
                          style={{
                            fontSize: 9.5,
                            fontWeight: 600,
                            padding: '2px 7px',
                            borderRadius: 10,
                            background: 'rgba(0,0,0,0.04)',
                            color: 'var(--text-muted)',
                          }}
                        >
                          ● Queued
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="dept-title-container">
                    <div className="dept-name">{dept.meta.name}</div>
                    <div className="dept-sub">{dept.meta.fullName || `${dept.code} Department`}</div>
                  </div>
                </div>

                <div className="dept-body">
                  <div>
                    <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)' }}>CHECKED:</span>
                    <p style={{ margin: '2px 0 0', fontSize: 11, color: 'var(--text-primary)' }}>
                      {dept.meta.defaultChecked}
                    </p>
                  </div>

                  {dept.evidence && Object.keys(dept.evidence).length > 0 && (
                    <div className="dept-evidence-box">
                      <span style={{ fontWeight: 700, color: '#78acf5' }}>EVIDENCE: </span>
                      {Object.entries(dept.evidence).map(([k, v]) => `${k.replaceAll('_', ' ')}: ${String(v)}`).join(' · ')}
                    </div>
                  )}

                  {dept.issue && (
                    <div className="dept-blocker-box">
                      <strong>BLOCKER: </strong>{dept.issue}
                      {dept.reason && <div style={{ marginTop: 2, opacity: 0.9 }}>Reason: {dept.reason}</div>}
                    </div>
                  )}

                  {dept.action && (
                    <div className="dept-action-box">
                      <strong>ACTION: </strong>{dept.action}
                      {dept.role && <span style={{ display: 'block', fontSize: 10, opacity: 0.85 }}>Role: {dept.role}</span>}
                    </div>
                  )}

                  {dept.delayDays != null && dept.delayDays > 0 && (
                    <div style={{ fontSize: 11, fontWeight: 700, color: '#f58a3a' }}>
                      Delivery Impact: +{dept.delayDays} calendar days
                    </div>
                  )}

                  <button
                    type="button"
                    className="text-button"
                    style={{ fontSize: 10, marginTop: 'auto', alignSelf: 'flex-start', display: 'flex', alignItems: 'center', gap: 4 }}
                    onClick={() => setExpandedDept(isExpanded ? null : dept.code)}
                  >
                    {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                    {isExpanded ? 'Hide Technical Audit' : 'Inspect Audit Records'}
                  </button>

                  {isExpanded && (
                    <div style={{ padding: 10, background: 'rgba(10,14,23,0.8)', borderRadius: 6, fontSize: 10, marginTop: 6, border: '1px solid var(--line)' }}>
                      <div><strong>Data Source:</strong> {dept.dataSource || 'Production Operational Schema'}</div>
                      <div><strong>Responsible Role:</strong> {dept.role || 'Manufacturing Operations'}</div>
                      {dept.missingInfo && <div><strong>Missing Information:</strong> {dept.missingInfo}</div>}
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* 4. RESULTS SECTION: SHOWN DOWN BELOW AFTER ALL CARDS FINISH */}
      {isScanningPipeline && !flowCompleted ? (
        <div
          className="card"
          style={{
            padding: '36px 24px',
            background: 'var(--surface-hi)',
            border: '1px solid var(--line)',
            borderRadius: 14,
            textAlign: 'center',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 16,
          }}
        >
          <div
            style={{
              width: 52,
              height: 52,
              borderRadius: '50%',
              background: 'var(--brand-purple-soft)',
              color: 'var(--brand-purple)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 0 8px rgba(111, 61, 186, 0.1)',
            }}
          >
            <Sparkles size={26} className="animate-spin" />
          </div>

          <div style={{ maxWidth: 480 }}>
            <div style={{ fontSize: 16, fontWeight: 800, color: 'var(--text-primary)' }}>
              {liveAgentStage
                ? liveAgentStage
                : `Auditing Conduit ${Math.min(Object.keys(evaluatedMap).length + 1, 7)} of 7: ${activeScanningDept || 'Synthesizing Feasibility'}`}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>
              {liveAgentStage
                ? 'All 7 department conduits verified. Domo AI Agent 2 is reasoning over live telemetry and generating the commitment proposal.'
                : 'Evaluating operational telemetry and manufacturing readiness. Results and achievable delivery date will be revealed once all 7 conduits and AI Agent synthesis complete.'}
            </div>
          </div>

          {/* Sequential Conduit Progress Bar */}
          <div style={{ width: '100%', maxWidth: 400, background: 'var(--kg-bg-2)', height: 8, borderRadius: 4, overflow: 'hidden', border: '1px solid var(--line)' }}>
            <div
              style={{
                height: '100%',
                width: `${(Object.keys(evaluatedMap).length / 7) * 100}%`,
                background: 'linear-gradient(90deg, var(--brand-purple), #3b82f6)',
                transition: 'width 0.4s ease',
              }}
            />
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600 }}>
            {Object.keys(evaluatedMap).length} of 7 Conduits Verified
          </div>
        </div>
      ) : (
        <>
          {/* 4. FEASIBILITY REPORT & DELIVERY TIMELINE COMPARISON */}
          <div className="card" style={{ padding: 22, background: 'var(--surface-hi)', border: '1px solid var(--line)' }}>
            <h3 style={{ fontSize: 14, fontWeight: 800, margin: '0 0 16px', textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--brand-orange)', display: 'flex', alignItems: 'center', gap: 8 }}>
              <TrendingUp size={16} /> Feasibility Report &amp; Delivery Timeline
            </h3>

            {/* Triple Date Comparison Banner */}
            <div className="delivery-comparison-banner">
              <div className="comparison-point">
                <span className="comparison-label">1. Customer Requested Date</span>
                <div className="comparison-date" style={{ color: 'var(--brand-blue)' }}>
                  {formatDate(assessment.requested_delivery_date)}
                </div>
                <small style={{ fontSize: 10, color: 'var(--text-secondary)' }}>Intake PO Specification</small>
              </div>

              <div className="comparison-arrow-box" title="Variance buffer">
                <ArrowRight size={16} />
              </div>

              <div className="comparison-point">
                <span className="comparison-label">2. Agent 2 Achievable Date</span>
                <div className="comparison-date" style={{ color: (assessment?.days_variance || 0) > 0 ? 'var(--brand-orange)' : '#10b981' }}>
                  {formatDate(
                    assessment?.estimated_delivery_date ||
                    assessment?.achievable_delivery_date ||
                    assessment?.requested_delivery_date ||
                    pendingOrderPayload?.requested_delivery_date
                  )}
                </div>
                <small style={{ fontSize: 10, color: 'var(--text-secondary)', fontWeight: 600 }}>
                  Calculated Variance:{' '}
                  {assessment?.days_variance != null
                    ? assessment.days_variance > 0
                      ? `+${assessment.days_variance} days delay`
                      : assessment.days_variance === 0
                      ? 'On Schedule'
                      : `${Math.abs(assessment.days_variance)} days buffer (Ahead)`
                    : 'On Schedule'}
                </small>
              </div>

              <div className="comparison-arrow-box" title="Approval stage">
                <ArrowRight size={16} />
              </div>

              <div className="comparison-point">
                <span className="comparison-label">3. Customer Service Committed Date</span>
                <div className="comparison-date" style={{ color: approvalResult?.status === 'APPROVED' ? '#10b981' : 'var(--brand-orange)' }}>
                  {approvalResult?.status === 'APPROVED' ? formatDate(approvalResult.date) : 'PENDING CS APPROVAL'}
                </div>
                <small style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
                  {approvalResult?.status === 'APPROVED' ? `Confirmed by ${approvalResult.approver}` : 'Requires Commercial Authority'}
                </small>
              </div>
            </div>

            {/* Summary Details */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16, marginTop: 16 }}>
              <div style={{ background: 'var(--kg-bg-2)', padding: 14, borderRadius: 10, border: '1px solid rgba(228, 92, 114, 0.25)' }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: '#dc2626', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <AlertTriangle size={14} /> CRITICAL BLOCKERS ({assessment.result_source === 'AGENT' ? 'DOMO AI AGENT' : 'RULE ENGINE'})
                </span>
                <ul style={{ margin: '8px 0 0', paddingLeft: 18, fontSize: 11, color: 'var(--text-primary)', lineHeight: 1.6 }}>
                  {assessment.blockers_summary && assessment.blockers_summary.length > 0 ? (
                    assessment.blockers_summary.map((b, i) => <li key={i}>{b}</li>)
                  ) : (
                    <li style={{ color: '#10b981' }}>No critical production blockers identified.</li>
                  )}
                </ul>
              </div>

              <div style={{ background: 'var(--kg-bg-2)', padding: 14, borderRadius: 10, border: '1px solid rgba(245, 138, 58, 0.25)' }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--brand-orange)', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Sparkles size={14} /> CORRECTIVE ACTIONS RECOMMENDED ({assessment.result_source === 'AGENT' ? 'DOMO AI AGENT' : 'RULE ENGINE'})
                </span>
                <ul style={{ margin: '8px 0 0', paddingLeft: 18, fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                  {assessment.corrective_actions_summary && assessment.corrective_actions_summary.length > 0 ? (
                    assessment.corrective_actions_summary.map((a, i) => <li key={i}>{a}</li>)
                  ) : (
                    <li style={{ color: '#10b981' }}>Standard manufacturing schedule adherence maintained.</li>
                  )}
                </ul>
              </div>
            </div>
          </div>

          {/* 5. AGENT REASONING & TOOL-CALLING EXECUTION TRACE */}
          <div className="card" style={{ padding: 18, background: 'var(--surface-hi)', border: '1px solid var(--line)' }}>
            <div
              onClick={() => setShowReasoning(!showReasoning)}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                cursor: 'pointer',
                userSelect: 'none',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Cpu size={16} color="var(--brand-purple)" />
                <h3 style={{ fontSize: 13.5, fontWeight: 800, margin: 0, color: 'var(--text-primary)' }}>
                  Agent 2 Reasoning &amp; Tool-Calling Execution Trace
                </h3>
                <span
                  className="mfg-badge"
                  style={{
                    fontSize: 10,
                    color:
                      assessment.agent_status === 'success' || assessment.result_source === 'AGENT'
                        ? '#16a34a'
                        : assessment.agent_status === 'rate_limit_paused'
                        ? '#dc2626'
                        : assessment.result_source === 'RULES' || assessment.agent_status === 'rules_mode'
                        ? '#2563eb'
                        : '#d97706',
                    background:
                      assessment.agent_status === 'success' || assessment.result_source === 'AGENT'
                        ? 'rgba(34, 197, 94, 0.12)'
                        : assessment.agent_status === 'rate_limit_paused'
                        ? 'rgba(239, 68, 68, 0.12)'
                        : assessment.result_source === 'RULES' || assessment.agent_status === 'rules_mode'
                        ? 'rgba(59, 130, 246, 0.12)'
                        : 'rgba(245, 158, 11, 0.12)',
                  }}
                >
                  {assessment.agent_status === 'success' || assessment.result_source === 'AGENT'
                    ? 'AI Agent (Domo LLM Tool-Calling Active)'
                    : assessment.agent_status === 'rate_limit_paused'
                    ? 'Rate Limited'
                    : assessment.result_source === 'RULES' || assessment.agent_status === 'rules_mode'
                    ? 'Rules Mode'
                    : `Rules Fallback (${assessment.agent_status || 'validation failed'})`}
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-muted)' }}>
                <span>{showReasoning ? 'Hide Trace' : 'View Trace'}</span>
                {showReasoning ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </div>
            </div>

            {showReasoning && (
              <div style={{ marginTop: 14, paddingTop: 14, borderTop: '1px solid var(--line)' }}>
                {Array.isArray(assessment.agent_reasoning) && assessment.agent_reasoning.length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    {assessment.agent_reasoning.map((step, idx) => {
                      const toolName = step.tool || step.action
                      const toolInput = step.input || step.action_input
                      const toolOutput = step.output || step.observation
                      const isErr = step.status === 'error' || Boolean(toolOutput && typeof toolOutput === 'object' && toolOutput.error)
                      const isExpanded = expandedTraceSteps[idx]

                      return (
                        <div
                          key={idx}
                          style={{
                            padding: '12px 14px',
                            background: isErr ? 'rgba(239, 68, 68, 0.05)' : 'var(--kg-bg-2)',
                            borderRadius: 8,
                            border: `1px solid ${isErr ? '#ef4444' : 'var(--line)'}`,
                            fontSize: 12,
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                            <span style={{ fontWeight: 700, color: isErr ? '#dc2626' : 'var(--brand-purple)' }}>
                              Step {step.step || idx + 1} {isErr && <span style={{ color: '#dc2626', fontSize: 11, fontWeight: 700 }}>(Failed)</span>}
                            </span>
                            {toolName && (
                              <span
                                style={{
                                  fontFamily: 'monospace',
                                  fontSize: 11,
                                  padding: '2px 8px',
                                  borderRadius: 6,
                                  background: isErr ? 'rgba(239, 68, 68, 0.12)' : 'rgba(111, 61, 186, 0.12)',
                                  color: isErr ? '#dc2626' : 'var(--brand-purple)',
                                  fontWeight: 700,
                                }}
                              >
                                Tool: {toolName}
                              </span>
                            )}
                          </div>
                          {step.thought && (
                            <p style={{ margin: '4px 0 8px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                              <strong>Thought:</strong> {step.thought}
                            </p>
                          )}
                          {toolInput && (
                            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>
                              <strong>Arguments:</strong> <code>{typeof toolInput === 'object' ? JSON.stringify(toolInput) : String(toolInput)}</code>
                            </div>
                          )}
                          {toolOutput && (
                            <div
                              style={{
                                padding: '6px 10px',
                                background: isErr ? 'rgba(239, 68, 68, 0.08)' : 'rgba(0,0,0,0.03)',
                                borderRadius: 6,
                                fontSize: 11,
                                color: isErr ? '#b91c1c' : 'var(--text-primary)',
                                maxHeight: isExpanded ? 'none' : 120,
                                overflowY: isExpanded ? 'visible' : 'auto',
                              }}
                            >
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                                <strong>Observation:</strong>
                                {JSON.stringify(toolOutput).length > 200 && (
                                  <button
                                    type="button"
                                    onClick={() => setExpandedTraceSteps((prev) => ({ ...prev, [idx]: !prev[idx] }))}
                                    style={{
                                      background: 'none',
                                      border: 'none',
                                      color: 'var(--brand-purple)',
                                      cursor: 'pointer',
                                      fontSize: 10,
                                      fontWeight: 600,
                                    }}
                                  >
                                    {isExpanded ? 'Collapse' : 'Expand full output'}
                                  </button>
                                )}
                              </div>
                              <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'inherit' }}>
                                {typeof toolOutput === 'object' ? JSON.stringify(toolOutput, null, 2) : String(toolOutput)}
                              </pre>
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                ) : (
                  <div style={{ padding: '14px 16px', background: 'var(--kg-bg-2)', borderRadius: 8, fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}>
                    Agent loop did not run for this decision (rule-based evaluation).
                  </div>
                )}
              </div>
            )}
          </div>
        </>
      )}


      {/* 6. HUMAN APPROVAL STAGE */}
      {assessment.proposal_id && (
        <div className="governance-card">
          <div className="governance-header">
            <div>
              <div className="eyebrow" style={{ color: 'var(--brand-orange)' }}>
                HUMAN GOVERNANCE WORKFLOW · PROPOSAL #{assessment.proposal_id}
              </div>
              <h3 className="governance-title">
                <ShieldCheck size={20} color="var(--brand-orange)" />
                Commercial Commitment Review &amp; Segregation of Duties
              </h3>
            </div>
            <div>
              {isApprovedProposal ? (
                <span className="mfg-badge mfg-badge-ready">COMMERCIALLY APPROVED</span>
              ) : isRejectedProposal ? (
                <span className="mfg-badge mfg-badge-critical">PROPOSAL REJECTED</span>
              ) : (
                <span className="mfg-badge mfg-badge-warning">PENDING HUMAN DECISION</span>
              )}
            </div>
          </div>

          <p className="governance-desc">
            Agent 2 has prepared a formal promise date proposal based on the 7-department evidence above.
            Under enterprise governance rules (Use Case 18), commercial commitments, pricing, and delivery changes must be confirmed by authorized Customer Service or Management personnel.
          </p>

          {assessment.proposal?.reasons && assessment.proposal.reasons.length > 0 && (
            <div style={{ margin: '14px 0', padding: 12, background: 'var(--kg-bg-2)', borderRadius: 8, border: '1px solid rgba(245, 138, 58, 0.3)' }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--brand-orange)', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
                <Sparkles size={13} /> {assessment.result_source === 'AGENT' ? 'DOMO AI AGENT' : 'RULE ENGINE'} PROPOSAL JUSTIFICATION &amp; RECOMMENDATIONS
              </div>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 11, color: 'var(--text-primary)', lineHeight: 1.6 }}>
                {assessment.proposal.reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          )}

          {isDecided ? (
            <div style={{ padding: 16, background: isApprovedProposal ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)', border: `1px solid ${isApprovedProposal ? '#10b981' : '#ef4444'}`, borderRadius: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
              <div>
                <strong style={{ color: isApprovedProposal ? '#059669' : '#dc2626', fontSize: 14 }}>
                  Proposal #{assessment.proposal_id} {isApprovedProposal ? 'APPROVED' : 'REJECTED'}
                </strong>
                <p style={{ margin: '4px 0 0', fontSize: 11, color: 'var(--text-secondary)' }}>
                  Confirmed Date: {formatDate(approvalResult?.date || assessment.proposal?.proposed_date)} · Decided by: {approvalResult?.approver || assessment.proposal?.decider?.full_name || assessment.proposal?.decider?.email || 'Commercial Management'}
                </p>
              </div>
              {isApprovedProposal && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--brand-orange)', fontWeight: 700, fontSize: 12 }}>
                  <Cpu size={16} /> Agent 3 Surveillance Activated
                </div>
              )}
            </div>
          ) : isApprover ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <input
                className="input"
                type="text"
                placeholder="Optional commercial decision note (e.g. Approved with customer buffer agreement)"
                value={decisionNote}
                onChange={(e) => setDecisionNote(e.target.value)}
                disabled={acting}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  borderRadius: 8,
                  border: '1px solid var(--line)',
                  background: 'var(--kg-bg-2)',
                  color: 'var(--text-primary)',
                  fontSize: 13,
                }}
              />
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, flexWrap: 'wrap' }}>
                <button
                  type="button"
                  className="button button-secondary"
                  onClick={handleReject}
                  disabled={acting}
                  style={{ color: '#ef4444', borderColor: 'rgba(239,68,68,0.4)', display: 'flex', alignItems: 'center', gap: 6 }}
                >
                  <XCircle size={15} /> Reject Proposal
                </button>
                <button
                  type="button"
                  className="button button-primary glow-orange"
                  onClick={handleApprove}
                  disabled={acting}
                  style={{ minWidth: 220, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, fontWeight: 700 }}
                >
                  <CheckCircle2 size={16} /> Approve Commercial Commitment
                </button>
              </div>
            </div>
          ) : (
            <div style={{ padding: 12, background: 'var(--kg-bg-2)', border: '1px solid var(--line)', borderRadius: 8, fontSize: 11, color: 'var(--text-secondary)' }}>
              Note: You are logged in with <strong>{user?.role || 'user'}</strong> role. Only Managers and Administrators possess commercial authority to approve commitment proposals.
            </div>
          )}
        </div>
      )}
    </div>
  )
}

