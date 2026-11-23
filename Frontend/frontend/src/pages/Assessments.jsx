import { useState, useEffect, useMemo } from 'react'
import { useSearchParams, useLocation, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Cpu,
  Plus,
  Search,
  Filter,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Clock,
  Layers,
  ChevronRight,
  ChevronLeft,
  ArrowLeft,
  ArrowRight,
  RotateCcw,
  Factory,
  ExternalLink,
  Calendar,
  Package,
  Building2,
  X,
  FileCheck2,
} from 'lucide-react'
import { agentsApi } from '../api/agents.api'
import { Agent2AssessmentWorkspace } from '../components/feasibility/Agent2AssessmentWorkspace'
import { CreateOrderIntakeModal } from '../components/orders/CreateOrderIntakeModal'
import { formatDate, formatNumber } from '../utils/format'

const PAGE_SIZE = 15

function getCustomerLabel(item) {
  if (!item) return 'Customer'
  if (typeof item === 'string') return item
  return item.customer_name || item.customer_id || 'Customer'
}

function getProductLabel(item) {
  if (!item) return 'Product'
  if (typeof item === 'string') return item
  return item.product_name || item.product_id || 'Product'
}

export default function Assessments() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const location = useLocation()
  const rawUrlId = searchParams.get('id')
  const urlId = rawUrlId ? rawUrlId.replace(/^PRE-/, '') : null
  const runNewOrder = searchParams.get('runNewOrder') === 'true'

  // Retrieve pending new order payload from navigation state or sessionStorage
  const [pendingPayload, setPendingPayload] = useState(() => {
    if (runNewOrder) {
      if (location.state?.newOrderPayload) return location.state.newOrderPayload
      try {
        const stored = sessionStorage.getItem('pending_agent2_intake')
        if (stored) return JSON.parse(stored)
      } catch (e) { }
    }
    return null
  })

  const [selectedId, setSelectedId] = useState(urlId || null)
  const [filterFeasibility, setFilterFeasibility] = useState('ALL') // ALL, FEASIBLE, AT_RISK, NOT_FEASIBLE
  const [filterProposal, setFilterProposal] = useState('ALL') // ALL, PENDING, APPROVED, REJECTED
  const [searchQuery, setSearchQuery] = useState('')
  const [currentPage, setCurrentPage] = useState(1)
  const [isModalOpen, setIsModalOpen] = useState(false)

  // Fetch assessments from backend
  const {
    data: assessments = [],
    isLoading: loading,
    isRefetching,
    refetch: loadAssessments,
  } = useQuery({
    queryKey: ['assessments-list'],
    queryFn: async () => {
      const data = await agentsApi.listAssessments({ limit: 500 })
      return Array.isArray(data) ? data : (data?.items || [])
    },
    staleTime: 5 * 1000,
    refetchOnMount: 'always',
  })

  // Fetch authoritative backend KPI summary counts across the entire DB table
  const {
    data: summaryData = null,
    isLoading: summaryLoading,
    refetch: loadSummary,
  } = useQuery({
    queryKey: ['assessments-summary'],
    queryFn: () => agentsApi.getAssessmentsSummary(),
    staleTime: 5 * 1000,
    refetchOnMount: 'always',
  })

  const handleRefreshAll = () => {
    loadAssessments()
    loadSummary()
  }

  // Synchronize selection whenever the URL id query param changes
  useEffect(() => {
    if (urlId) {
      const match = assessments.find(
        (a) => a.assessment_id === urlId || a.customer_order_id === urlId || a.customer_order_id === `PRE-${urlId}`
      )
      setSelectedId(match ? match.assessment_id : urlId)
    } else {
      setSelectedId(null)
    }
  }, [urlId, assessments])

  const handleSelectAssessment = (id) => {
    setPendingPayload(null)
    setSelectedId(id)
    setSearchParams({ id })
  }

  const handleBackToTable = () => {
    setSelectedId(null)
    setPendingPayload(null)
    try {
      sessionStorage.removeItem('pending_agent2_intake')
    } catch (e) { }
    setSearchParams({})
  }

  // Filter assessments
  const filteredAssessments = useMemo(() => {
    return assessments.filter((a) => {
      const status = (a.overall_status || a.overall_feasibility || '').toUpperCase()
      const proposalStatus = (a.proposal?.status || (a.proposal_id ? 'PENDING' : 'NONE')).toUpperCase()

      // Feasibility filter
      if (filterFeasibility !== 'ALL') {
        if (filterFeasibility === 'AT_RISK') {
          if (status !== 'AT_RISK' && status !== 'FEASIBLE_WITH_RISKS' && status !== 'PARTIALLY_READY') {
            return false
          }
        } else if (filterFeasibility === 'NOT_FEASIBLE') {
          if (status !== 'NOT_FEASIBLE' && status !== 'BLOCKED') {
            return false
          }
        } else if (status !== filterFeasibility) {
          return false
        }
      }

      // Proposal governance filter
      if (filterProposal !== 'ALL') {
        if (proposalStatus !== filterProposal) {
          return false
        }
      }

      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().replace('order #', '').replace('order ', '').trim()
        const qHyphen = q.replaceAll(' ', '-')
        const matchOrderId = a.customer_order_id && (a.customer_order_id.toLowerCase().includes(q) || a.customer_order_id.toLowerCase().includes(qHyphen))
        const matchAsmId = a.assessment_id && (a.assessment_id.toLowerCase().includes(q) || a.assessment_id.toLowerCase().includes(qHyphen))
        const matchCust = (a.customer_name && a.customer_name.toLowerCase().includes(q)) || (a.customer_id && a.customer_id.toLowerCase().includes(q))
        const matchProd = (a.product_name && a.product_name.toLowerCase().includes(q)) || (a.product_id && a.product_id.toLowerCase().includes(q))
        if (!matchOrderId && !matchAsmId && !matchCust && !matchProd) {
          return false
        }
      }

      return true
    })
  }, [assessments, filterFeasibility, filterProposal, searchQuery])

  // Pagination calculation
  const totalPages = Math.ceil(filteredAssessments.length / PAGE_SIZE) || 1
  const paginatedAssessments = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE
    return filteredAssessments.slice(start, start + PAGE_SIZE)
  }, [filteredAssessments, currentPage])

  // Authoritative KPI stats strictly from backend GET /api/assessments/summary
  const stats = useMemo(() => {
    if (!summaryData) {
      return { total: null, feasible: null, atRisk: null, pendingProposal: null }
    }
    return {
      total: summaryData.total ?? 0,
      feasible: summaryData.feasible ?? 0,
      atRisk: summaryData.at_risk ?? 0,
      pendingProposal: summaryData.pending_approvals ?? 0,
    }
  }, [summaryData])

  // Current assessment index in full list for prev/next switcher
  const currentIndex = useMemo(() => {
    if (!selectedId) return -1
    return assessments.findIndex(
      (a) => a.assessment_id === selectedId || a.customer_order_id === selectedId || a.customer_order_id === `PRE-${selectedId}`
    )
  }, [selectedId, assessments])

  const handlePrevAssessment = () => {
    if (currentIndex > 0) {
      handleSelectAssessment(assessments[currentIndex - 1].assessment_id)
    }
  }

  const handleNextAssessment = () => {
    if (currentIndex >= 0 && currentIndex < assessments.length - 1) {
      handleSelectAssessment(assessments[currentIndex + 1].assessment_id)
    }
  }

  const getFeasibilityBadge = (status) => {
    const s = (status || '').toUpperCase()
    switch (s) {
      case 'FEASIBLE':
        return (
          <span style={{
            background: 'rgba(34, 197, 94, 0.12)',
            color: '#16a34a',
            padding: '4px 10px',
            borderRadius: 12,
            fontSize: 11,
            fontWeight: 700,
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            border: '1px solid rgba(34, 197, 94, 0.25)',
          }}>
            <CheckCircle2 size={12} /> FEASIBLE
          </span>
        )
      case 'FEASIBLE_WITH_RISKS':
      case 'AT_RISK':
      case 'PARTIALLY_READY':
        return (
          <span style={{
            background: 'rgba(245, 158, 11, 0.12)',
            color: '#d97706',
            padding: '4px 10px',
            borderRadius: 12,
            fontSize: 11,
            fontWeight: 700,
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            border: '1px solid rgba(245, 158, 11, 0.25)',
          }}>
            <AlertTriangle size={12} /> AT RISK
          </span>
        )
      case 'NOT_FEASIBLE':
      case 'BLOCKED':
        return (
          <span style={{
            background: 'rgba(239, 68, 68, 0.12)',
            color: '#dc2626',
            padding: '4px 10px',
            borderRadius: 12,
            fontSize: 11,
            fontWeight: 700,
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            border: '1px solid rgba(239, 68, 68, 0.25)',
          }}>
            <XCircle size={12} /> NOT FEASIBLE
          </span>
        )
      default:
        return (
          <span style={{
            background: 'rgba(100, 116, 139, 0.12)',
            color: 'var(--text-secondary)',
            padding: '4px 10px',
            borderRadius: 12,
            fontSize: 11,
            fontWeight: 700,
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
          }}>
            <Clock size={12} /> {status || 'EVALUATING'}
          </span>
        )
    }
  }

  const getProposalBadge = (proposal) => {
    const status = (proposal?.status || '').toUpperCase()
    if (status === 'APPROVED') {
      return (
        <span style={{
          background: 'rgba(34, 197, 94, 0.12)',
          color: '#16a34a',
          padding: '3px 8px',
          borderRadius: 8,
          fontSize: 11,
          fontWeight: 700,
          border: '1px solid rgba(34, 197, 94, 0.25)',
        }}>
          ✓ Human Approved
        </span>
      )
    }
    if (status === 'REJECTED') {
      return (
        <span style={{
          background: 'rgba(239, 68, 68, 0.12)',
          color: '#dc2626',
          padding: '3px 8px',
          borderRadius: 8,
          fontSize: 11,
          fontWeight: 700,
          border: '1px solid rgba(239, 68, 68, 0.25)',
        }}>
          REJECTED
        </span>
      )
    }
    if (status === 'PENDING') {
      return (
        <span style={{
          background: 'rgba(245, 138, 58, 0.12)',
          color: '#ea580c',
          padding: '3px 8px',
          borderRadius: 8,
          fontSize: 11,
          fontWeight: 700,
          border: '1px solid rgba(245, 138, 58, 0.25)',
        }}>
          PENDING DECISION
        </span>
      )
    }
    return (
      <span style={{ color: 'var(--text-muted)', fontSize: 11, fontStyle: 'italic' }}>
        No Proposal
      </span>
    )
  }

  // Calculate 7-department readiness score strictly from backend readiness_records
  const getReadinessScore = (item) => {
    const records = item.readiness_records || []
    const ready = records.filter((r) => (r.readiness_status || '').toUpperCase() === 'READY').length
    return { ready, total: records.length || 7 }
  }

  // ==========================================
  // VIEW 1: DETAIL VIEW (SHOW 7 STAGES RESULT)
  // ==========================================
  if (selectedId || pendingPayload) {
    const currentAssessment = assessments.find(
      (a) => a.assessment_id === selectedId || a.customer_order_id === selectedId || a.customer_order_id === `PRE-${selectedId}`
    )
    const orderTitle = currentAssessment?.customer_order_id || currentAssessment?.assessment_id || selectedId || (pendingPayload?.product_config?.po_number || 'PRE-ASM-NEW')

    return (
      <div className="page-stack">
        {/* DETAIL TOPBAR WITH BACK BUTTON & PREV/NEXT SWITCHER */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 12,
            padding: '12px 18px',
            background: 'var(--surface-hi)',
            border: '1px solid var(--line)',
            borderRadius: 12,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <button
              type="button"
              onClick={handleBackToTable}
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
              <ArrowLeft size={14} /> Back to Assessments Table
            </button>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
                Order: <span style={{ fontFamily: 'monospace', color: 'var(--brand-purple)' }}>{orderTitle}</span>
              </span>
              {currentAssessment && getFeasibilityBadge(currentAssessment.overall_status || currentAssessment.overall_feasibility)}
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {assessments.length > 0 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'var(--kg-bg-2)', padding: '3px 8px', borderRadius: 8, border: '1px solid var(--line)' }}>
                <button
                  type="button"
                  className="button button-secondary"
                  onClick={handlePrevAssessment}
                  disabled={currentIndex <= 0}
                  title="Previous Assessment"
                  style={{ padding: '4px 8px', fontSize: 11 }}
                >
                  <ChevronLeft size={13} />
                </button>
                <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)' }}>
                  {currentIndex + 1} of {assessments.length}
                </span>
                <button
                  type="button"
                  className="button button-secondary"
                  onClick={handleNextAssessment}
                  disabled={currentIndex >= assessments.length - 1}
                  title="Next Assessment"
                  style={{ padding: '4px 8px', fontSize: 11 }}
                >
                  <ChevronRight size={13} />
                </button>
              </div>
            )}

            <button
              type="button"
              className="button button-secondary"
              onClick={handleRefreshAll}
              disabled={isRefetching}
              style={{ fontSize: 12, padding: '7px 12px', display: 'flex', alignItems: 'center', gap: 6 }}
              title="Refresh assessment details"
            >
              <RotateCcw size={13} className={isRefetching ? 'spin' : ''} />
              Refresh
            </button>
          </div>
        </div>

        {/* FULL-WIDTH 7-STAGE FEASIBILITY WORKSPACE */}
        <Agent2AssessmentWorkspace
          key="agent-2-assessment-workspace"
          assessmentId={selectedId}
          selectedAssessmentId={selectedId}
          pendingOrderPayload={pendingPayload}
          onApprovalTransition={() => handleRefreshAll()}
          onAssessmentCreated={(newAss) => {
            if (newAss?.assessment_id) {
              queryClient.setQueryData(['assessment-detail', newAss.assessment_id], newAss)
              queryClient.invalidateQueries({ queryKey: ['assessments-list'], refetchType: 'none' })
              queryClient.invalidateQueries({ queryKey: ['assessments-summary'] })
            }
          }}
          onAssessmentSelect={(newId) => handleSelectAssessment(newId)}
        />
      </div>
    )
  }

  // ==========================================
  // VIEW 2: COMPREHENSIVE ASSESSMENTS TABLE
  // ==========================================
  return (
    <div className="page-stack">
      {/* KPI STATS ROW (Authoritative backend SQL counts via GET /api/assessments/summary) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 14 }}>
        <div className="card" style={{ padding: '16px 20px', background: 'var(--surface-hi)', border: '1px solid var(--line)', borderRadius: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Total Assessments
          </div>
          <div style={{ fontSize: 26, fontWeight: 800, color: 'var(--text-primary)', marginTop: 4 }}>
            {summaryLoading ? '—' : formatNumber(stats.total ?? 0)}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
            Evaluated by Agent 2 engine
          </div>
        </div>

        <div className="card" style={{ padding: '16px 20px', background: 'var(--surface-hi)', border: '1px solid var(--line)', borderRadius: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Feasible Commitments
          </div>
          <div style={{ fontSize: 26, fontWeight: 800, color: '#16a34a', marginTop: 4 }}>
            {summaryLoading ? '—' : formatNumber(stats.feasible ?? 0)}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
            Zero-risk plant readiness
          </div>
        </div>

        <div className="card" style={{ padding: '16px 20px', background: 'var(--surface-hi)', border: '1px solid var(--line)', borderRadius: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            At Risk / Expedited
          </div>
          <div style={{ fontSize: 26, fontWeight: 800, color: '#ea580c', marginTop: 4 }}>
            {summaryLoading ? '—' : formatNumber(stats.atRisk ?? 0)}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
            Requires buffer or MES expedite
          </div>
        </div>

        <div className="card" style={{ padding: '16px 20px', background: 'var(--surface-hi)', border: '1px solid var(--line)', borderRadius: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Pending CS Approvals
          </div>
          <div style={{ fontSize: 26, fontWeight: 800, color: 'var(--brand-purple)', marginTop: 4 }}>
            {summaryLoading ? '—' : formatNumber(stats.pendingProposal ?? 0)}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
            Awaiting human commercial decision
          </div>
        </div>
      </div>

      {/* COMPREHENSIVE ASSESSMENTS TABLE WITH INTEGRATED ONE-LINE TOOLBAR */}
      <div className="card" style={{ padding: 0, overflow: 'hidden', background: 'var(--surface-hi)', border: '1px solid var(--line)', borderRadius: 12 }}>
        {/* INTEGRATED ONE-LINE TOOLBAR */}
        <div
          style={{
            padding: '10px 16px',
            borderBottom: '1px solid var(--line)',
            background: 'var(--surface-hi)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 10,
            flexWrap: 'nowrap',
            overflowX: 'auto',
          }}
        >
          {/* Left Controls: Search + Feasibility Tabs + Governance Select */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 1, minWidth: 0 }}>
            {/* SEARCH INPUT */}
            <div style={{ position: 'relative', width: 220, minWidth: 160, flexShrink: 1 }}>
              <Search size={13} style={{ position: 'absolute', left: 10, top: 9.5, color: 'var(--text-muted)' }} />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value)
                  setCurrentPage(1)
                }}
                placeholder="Search orders, customers…"
                style={{
                  width: '100%',
                  height: 32,
                  padding: '6px 10px 6px 30px',
                  background: 'var(--kg-bg-2, var(--surface-hi))',
                  border: '1px solid var(--line)',
                  borderRadius: 6,
                  color: 'var(--text-primary)',
                  fontSize: 11.5,
                  outline: 'none',
                }}
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  style={{
                    position: 'absolute',
                    right: 8,
                    top: 8,
                    background: 'none',
                    border: 'none',
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                    padding: 0,
                  }}
                >
                  <X size={13} />
                </button>
              )}
            </div>

            {/* FEASIBILITY TABS */}
            <div
              style={{
                display: 'inline-flex',
                background: 'var(--kg-bg-2)',
                padding: 2,
                borderRadius: 6,
                border: '1px solid var(--line)',
                gap: 2,
                flexShrink: 0,
                height: 32,
                alignItems: 'center',
              }}
            >
              {[
                { key: 'ALL', label: 'All Feasibility' },
                { key: 'FEASIBLE', label: 'Feasible' },
                { key: 'AT_RISK', label: 'At Risk' },
                { key: 'NOT_FEASIBLE', label: 'Not Feasible' },
              ].map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => {
                    setFilterFeasibility(item.key)
                    setCurrentPage(1)
                  }}
                  style={{
                    padding: '4px 9px',
                    borderRadius: 4,
                    border: 'none',
                    fontSize: 11,
                    fontWeight: 600,
                    cursor: 'pointer',
                    background: filterFeasibility === item.key ? 'var(--brand-purple)' : 'transparent',
                    color: filterFeasibility === item.key ? 'white' : 'var(--text-secondary)',
                    transition: 'all 0.15s ease',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {item.label}
                </button>
              ))}
            </div>

            {/* PROPOSAL GOVERNANCE SELECT */}
            <select
              value={filterProposal}
              onChange={(e) => {
                setFilterProposal(e.target.value)
                setCurrentPage(1)
              }}
              style={{
                height: 32,
                padding: '0 10px',
                borderRadius: 6,
                border: '1px solid var(--line)',
                background: 'var(--kg-bg-2, var(--surface-hi))',
                color: 'var(--text-primary)',
                fontSize: 11.5,
                fontWeight: 600,
                outline: 'none',
                cursor: 'pointer',
                flexShrink: 0,
              }}
            >
              <option value="ALL">All Governance Proposals</option>
              <option value="PENDING">Pending Commercial Decision</option>
              <option value="APPROVED">Approved Commercial Commitments</option>
              <option value="REJECTED">Rejected Proposals</option>
            </select>
          </div>

          {/* Right Controls: Refresh + New Feasibility Check */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
            <button
              type="button"
              className="button button-secondary"
              onClick={handleRefreshAll}
              disabled={isRefetching}
              style={{
                height: 32,
                fontSize: 11.5,
                padding: '0 11px',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
                borderRadius: 6,
                border: '1px solid var(--line)',
                background: 'var(--surface-hi)',
              }}
              title="Refresh assessments table"
            >
              <RotateCcw size={13} className={isRefetching ? 'spin' : ''} /> Refresh
            </button>

            <button
              type="button"
              className="button button-primary glow-orange"
              onClick={() => navigate('/orders/new')}
              style={{
                height: 32,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
                fontWeight: 600,
                padding: '0 13px',
                fontSize: 11.5,
                background: 'linear-gradient(135deg, var(--brand-orange), #ea580c)',
                color: 'white',
                borderRadius: 6,
                boxShadow: '0 2px 6px rgba(245, 138, 58, 0.25)',
                whiteSpace: 'nowrap',
              }}
            >
              <Plus size={14} />  New Feasibility Check
            </button>
          </div>
        </div>

        <div className="table-scroll" style={{ overflowX: 'auto', overflowY: 'auto', width: '100%', border: 'none', borderRadius: 0, scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
          <table className="orders-table" style={{ width: '100%', borderCollapse: 'collapse', minWidth: 1050 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--line)', background: 'var(--kg-bg-2)' }}>
                <th style={{ padding: '14px 18px', textAlign: 'left', fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Order / Assessment ID
                </th>
                <th style={{ padding: '14px 18px', textAlign: 'left', fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Customer
                </th>
                <th style={{ padding: '14px 18px', textAlign: 'left', fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Product Model
                </th>
                <th style={{ padding: '14px 18px', textAlign: 'left', fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Demand
                </th>
                <th style={{ padding: '14px 18px', textAlign: 'left', fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Requested Date
                </th>
                <th style={{ padding: '14px 18px', textAlign: 'left', fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Feasible Plan
                </th>
                <th style={{ padding: '14px 18px', textAlign: 'left', fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Feasibility Health
                </th>
                <th style={{ padding: '14px 18px', textAlign: 'left', fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Commercial Proposal
                </th>
                <th style={{ padding: '14px 18px', textAlign: 'left', fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  7 Stages Readiness
                </th>
                <th style={{ padding: '14px 18px', textAlign: 'center', fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  7 Stages Result
                </th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={10} style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)' }}>
                    Loading Agent 2 order feasibility assessments…
                  </td>
                </tr>
              ) : paginatedAssessments.length === 0 ? (
                <tr>
                  <td colSpan={10} style={{ padding: 48, textAlign: 'center', color: 'var(--text-secondary)' }}>
                    <Cpu size={32} style={{ color: 'var(--text-muted)', marginBottom: 8, opacity: 0.6 }} />
                    <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>No assessments match your current filters</div>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                      Try clearing search or adjusting the feasibility filter.
                    </div>
                  </td>
                </tr>
              ) : (
                paginatedAssessments.map((a) => {
                  const score = getReadinessScore(a)
                  const displayOrderId = a.customer_order_id || a.assessment_id
                  const isAllReady = score.ready === 7

                  return (
                    <tr
                      key={a.assessment_id}
                      onClick={() => handleSelectAssessment(a.assessment_id)}
                      style={{
                        borderBottom: '1px solid var(--line)',
                        cursor: 'pointer',
                        transition: 'background-color 0.15s ease',
                      }}
                      className="assessment-table-row"
                    >
                      {/* ORDER / ASSESSMENT ID */}
                      <td style={{ padding: '14px 18px' }}>
                        <div style={{ fontFamily: 'monospace', fontWeight: 800, fontSize: 13, color: 'var(--brand-purple)' }}>
                          {displayOrderId}
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                          {a.assessment_id}
                        </div>
                      </td>

                      {/* CUSTOMER */}
                      <td style={{ padding: '14px 18px' }}>
                        <div style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: 13 }}>
                          {getCustomerLabel(a)}
                        </div>
                        {a.customer_id && (
                          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                            {a.customer_id}
                          </div>
                        )}
                      </td>

                      {/* PRODUCT */}
                      <td style={{ padding: '14px 18px' }}>
                        <div style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: 13 }}>
                          {getProductLabel(a)}
                        </div>
                        {a.product_id && (
                          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                            {a.product_id}
                          </div>
                        )}
                      </td>

                      {/* DEMAND */}
                      <td style={{ padding: '14px 18px' }}>
                        <span style={{ fontWeight: 800, color: 'var(--text-primary)', fontSize: 13 }}>
                          {formatNumber(a.order_qty)}
                        </span>{' '}
                        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>units</span>
                      </td>

                      {/* REQUESTED DATE */}
                      <td style={{ padding: '14px 18px', fontSize: 12, color: 'var(--text-secondary)' }}>
                        {formatDate(a.requested_delivery_date)}
                      </td>

                      {/* FEASIBLE PLAN */}
                      <td style={{ padding: '14px 18px' }}>
                        <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)' }}>
                          {formatDate(a.estimated_delivery_date || a.requested_delivery_date)}
                        </div>
                        {a.days_variance != null && a.days_variance > 0 ? (
                          <span style={{ fontSize: 10, color: '#d97706', fontWeight: 700 }}>
                            +{a.days_variance} days delay
                          </span>
                        ) : (
                          <span style={{ fontSize: 10, color: '#16a34a', fontWeight: 700 }}>
                            On schedule
                          </span>
                        )}
                      </td>

                      {/* FEASIBILITY HEALTH */}
                      <td style={{ padding: '14px 18px' }}>
                        {getFeasibilityBadge(a.overall_status || a.overall_feasibility)}
                      </td>

                      {/* COMMERCIAL PROPOSAL */}
                      <td style={{ padding: '14px 18px' }}>
                        {getProposalBadge(a.proposal)}
                      </td>

                      {/* 7 STAGES READINESS */}
                      <td style={{ padding: '14px 18px' }}>
                        <span
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 6,
                            padding: '3px 9px',
                            borderRadius: 10,
                            fontSize: 11,
                            fontWeight: 700,
                            background: isAllReady ? 'rgba(34, 197, 94, 0.12)' : 'rgba(245, 138, 58, 0.12)',
                            color: isAllReady ? '#16a34a' : '#ea580c',
                            border: isAllReady ? '1px solid rgba(34, 197, 94, 0.25)' : '1px solid rgba(245, 138, 58, 0.25)',
                          }}
                        >
                          <Factory size={11} /> {score.ready}/{score.total} Ready
                        </span>
                      </td>

                      {/* ACTION: VIEW 7 STAGES RESULT */}
                      <td style={{ padding: '14px 18px', textAlign: 'center' }}>
                        <button
                          type="button"
                          className="button button-primary"
                          onClick={(e) => {
                            e.stopPropagation()
                            handleSelectAssessment(a.assessment_id)
                          }}
                          style={{
                            fontSize: 11,
                            padding: '6px 14px',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 5,
                            fontWeight: 700,
                            background: 'linear-gradient(135deg, var(--brand-purple), var(--dr-purple))',
                            color: 'white',
                            borderRadius: 6,
                            boxShadow: '0 2px 4px rgba(111, 61, 186, 0.2)',
                          }}
                          title="View complete seven-department audit evidence and proposal"
                        >
                          <span>View 7 Stages</span>
                          <ArrowRight size={12} />
                        </button>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>

        {/* TABLE FOOTER & PAGINATION */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '12px 18px',
            borderTop: '1px solid var(--line)',
            background: 'var(--kg-bg-2)',
            flexWrap: 'wrap',
            gap: 10,
            fontSize: 12,
            color: 'var(--text-secondary)',
          }}
        >
          <div>
            Showing <strong>{Math.min((currentPage - 1) * PAGE_SIZE + 1, filteredAssessments.length)}</strong> to{' '}
            <strong>{Math.min(currentPage * PAGE_SIZE, filteredAssessments.length)}</strong> of{' '}
            <strong>{filteredAssessments.length}</strong> assessments
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <button
              type="button"
              className="button button-secondary"
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage <= 1}
              style={{ padding: '4px 8px', fontSize: 11 }}
            >
              <ChevronLeft size={14} />
            </button>
            <span>
              Page <strong>{currentPage}</strong> of <strong>{totalPages}</strong>
            </span>
            <button
              type="button"
              className="button button-secondary"
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage >= totalPages}
              style={{ padding: '4px 8px', fontSize: 11 }}
            >
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      </div>

      {/* CREATE ORDER MODAL */}
      <CreateOrderIntakeModal
        isOpen={isModalOpen}
        open={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onAssessmentCreated={(result) => {
          setIsModalOpen(false)
          loadAssessments()
          if (result?.assessment_id) {
            setSelectedId(result.assessment_id)
            setSearchParams({ id: result.assessment_id, autoRun: 'true' })
          }
        }}
        onCreated={(result) => {
          setIsModalOpen(false)
          loadAssessments()
          if (result?.assessment_id) {
            setSelectedId(result.assessment_id)
            setSearchParams({ id: result.assessment_id, autoRun: 'true' })
          }
        }}
      />
    </div>
  )
}
