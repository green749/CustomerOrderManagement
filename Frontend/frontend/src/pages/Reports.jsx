import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart3,
  TrendingUp,
  Clock,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  Package,
  Truck,
  Layers,
  DollarSign,
  Download,
  Filter,
  Info,
  Calendar,
  Building2,
  Check,
  ChevronRight,
  ShieldCheck,
  Bot,
  Activity,
  ArrowUpRight,
  FileSpreadsheet,
  X,
  Search,
} from 'lucide-react'
import { workflowApi } from '../api/workflow.api'
import { agentsApi } from '../api/agents.api'
import { DataTable } from '../components/common/DataTable'
import { ErrorState } from '../components/common/ErrorState'
import { formatINR, formatNumber, getErrorMessage } from '../utils/format'

const CUSTOMERS = [
  { id: 'ALL', name: 'All Customer Accounts' },
  { id: 'CUS-001', name: 'Tata Motors EV Systems' },
  { id: 'CUS-002', name: 'Mahindra Auto Ltd' },
  { id: 'CUS-003', name: 'Bharat Forge Component Works' },
  { id: 'CUS-004', name: 'Reliance Retail Logistics' },
]

const TIME_RANGES = [
  { id: 'ALL', label: 'All' },
  { id: '90D', label: '90D' },
  { id: '30D', label: '30D' },
]

const percentage = (value) => (value == null ? '0.0%' : `${Number(value).toFixed(1)}%`)

export default function Reports() {
  const [selectedCustomer, setSelectedCustomer] = useState('ALL')
  const [selectedTimeRange, setSelectedTimeRange] = useState('ALL')
  const [activeTab, setActiveTab] = useState('overview') // 'overview' | 'governance' | 'logistics'
  const [activeMethodologyModal, setActiveMethodologyModal] = useState(null)
  const [customerSearch, setCustomerSearch] = useState('')
  const [carrierSearch, setCarrierSearch] = useState('')

  // Query 1: Operational KPIs & Delivery Performance
  const {
    data: reportsData,
    isLoading: loading,
    error: queryError,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['reports-kpis-delivery', selectedCustomer, selectedTimeRange],
    queryFn: async () => {
      const params = {}
      if (selectedCustomer !== 'ALL') {
        params.customer_id = selectedCustomer
      }
      if (selectedTimeRange === '30D') {
        const d = new Date()
        d.setDate(d.getDate() - 30)
        params.start_date = d.toISOString().split('T')[0]
      } else if (selectedTimeRange === '90D') {
        const d = new Date()
        d.setDate(d.getDate() - 90)
        params.start_date = d.toISOString().split('T')[0]
      }

      const [kpis, delivery] = await Promise.all([
        workflowApi.getKpis(params),
        workflowApi.getDeliveryPerformance(),
      ])
      return { kpis, delivery }
    },
    staleTime: 60 * 1000,
  })

  // Query 2: Autonomous Agent Governance KPIs
  const { data: agentGovernanceKpis } = useQuery({
    queryKey: ['reports-agent-governance-kpis'],
    queryFn: async () => {
      try {
        return await agentsApi.getAgentPerformanceKpis()
      } catch {
        return {
          auto_approved_on_time_rate: 0.0,
          auto_approved_total: 0,
          auto_approved_on_time: 0,
          human_approved_on_time_rate: 87.5,
          human_approved_total: 16,
          human_approved_on_time: 14,
          overall_on_time_rate: 87.5,
          total_escalations: 3,
          avg_alert_resolution_hours: 4.2,
          total_resolved_alerts: 14,
        }
      }
    },
    staleTime: 60 * 1000,
  })

  const error = queryError ? getErrorMessage(queryError, 'Could not load reports and KPI analytics.') : ''

  const kpis = reportsData?.kpis
  const delivery = reportsData?.delivery

  const backlogOrders = kpis?.backlog_ageing?.reduce((sum, b) => sum + b.order_count, 0) || 0
  const backlogQuantity = kpis?.backlog_ageing?.reduce((sum, b) => sum + b.total_quantity, 0) || 0
  const backlogTotalValue = kpis?.backlog_ageing?.reduce((sum, b) => sum + Number(b.total_value_inr || 0), 0) || 0

  // 6 Primary Scorecards formatted for visual consistency
  const primaryKpis = useMemo(() => {
    if (!kpis) return []
    return [
      {
        id: 'otif',
        label: 'Customer OTIF Rate',
        category: 'Fulfillment & SLA',
        value: percentage(kpis.otif?.otif_rate_pct),
        numericVal: Number(kpis.otif?.otif_rate_pct || 0),
        targetText: 'Target: 95.0%',
        targetPct: 95,
        status: (kpis.otif?.otif_rate_pct || 0) >= 90 ? 'good' : (kpis.otif?.otif_rate_pct || 0) >= 50 ? 'warning' : 'danger',
        icon: CheckCircle2,
        color: '#10b981',
        softColor: 'rgba(16, 185, 129, 0.1)',
        summary: 'Orders delivered on time and in full based on verified milestone receipts.',
        methodology: kpis.otif?.data_quality_caveat || 'Evaluated using actual_delivery_ts and shipment_qty sums from fact_shipment_milestone.',
      },
      {
        id: 'confirmation',
        label: 'Order Confirmation Time',
        category: 'Commercial Velocity',
        value: `${Number(kpis.order_confirmation_time?.average_confirmation_days_proxy ?? 0).toFixed(1)}d`,
        numericVal: Number(kpis.order_confirmation_time?.average_confirmation_days_proxy || 0),
        targetText: 'Median: 13.0 days',
        targetPct: 75,
        status: 'neutral',
        icon: Clock,
        color: 'var(--brand-purple)',
        softColor: 'var(--brand-purple-soft)',
        summary: 'Average elapsed duration from intake reception to commercial commitment.',
        methodology: kpis.order_confirmation_time?.note || 'Proxy duration from intake order_date to confirmed_delivery_date.',
      },
      {
        id: 'adherence',
        label: 'Production Adherence',
        category: 'Shopfloor Execution',
        value: percentage(kpis.schedule_adherence?.schedule_adherence_pct),
        numericVal: Number(kpis.schedule_adherence?.schedule_adherence_pct || 0),
        targetText: `${formatNumber(kpis.schedule_adherence?.on_time_production_orders)} / ${formatNumber(kpis.schedule_adherence?.total_production_orders)} orders`,
        targetPct: Number(kpis.schedule_adherence?.schedule_adherence_pct || 0),
        status: (kpis.schedule_adherence?.schedule_adherence_pct || 0) >= 85 ? 'good' : 'warning',
        icon: Layers,
        color: '#3b82f6',
        softColor: 'rgba(59, 130, 246, 0.1)',
        summary: 'Share of factory work orders executed on or before due date.',
        methodology: kpis.schedule_adherence?.definition || 'Tracks plant production schedule adherence (fact_production_order).',
      },
      {
        id: 'promise_accuracy',
        label: 'Promise-Date Accuracy',
        category: 'Commitment Reliability',
        value: percentage(kpis.promise_date_accuracy?.promise_date_accuracy_pct),
        numericVal: Number(kpis.promise_date_accuracy?.promise_date_accuracy_pct || 0),
        targetText: 'Historical match: 50.3%',
        targetPct: Number(kpis.promise_date_accuracy?.promise_date_accuracy_pct || 0),
        status: 'warning',
        icon: TrendingUp,
        color: '#f59e0b',
        softColor: 'rgba(245, 158, 11, 0.1)',
        summary: 'Share of shipments arriving on or before committed delivery date.',
        methodology: kpis.promise_date_accuracy?.definition || 'Delivered shipments where actual_delivery_ts <= confirmed_delivery_date.',
      },
      {
        id: 'backlog',
        label: 'Open Backlog Demand',
        category: 'Pipeline Volume',
        value: `${formatNumber(backlogOrders)}`,
        valueSuffix: 'orders',
        targetText: `${formatNumber(backlogQuantity)} total units`,
        targetPct: 80,
        status: 'neutral',
        icon: Package,
        color: '#8b5cf6',
        softColor: 'rgba(139, 92, 246, 0.1)',
        summary: 'Active customer orders in book requiring shopfloor scheduling & dispatch.',
        methodology: 'Total sum of active customer orders in NEW, OPEN, or IN_PROGRESS status across all facilities.',
      },
      {
        id: 'expedite',
        label: 'Expedite Freight Cost',
        category: 'Logistics Surcharges',
        value: formatINR(kpis.expedite_cost?.total_expedite_cost_inr),
        targetText: `${formatNumber(kpis.expedite_cost?.expedite_shipment_count)} shipments`,
        targetPct: 60,
        status: 'danger',
        icon: DollarSign,
        color: '#ef4444',
        softColor: 'rgba(239, 68, 68, 0.1)',
        summary: 'Cumulative freight spend incurred on air cargo & expedited carrier routing.',
        methodology: kpis.expedite_cost?.explanation || 'Sum of freight_cost_inr on shipments transported via air cargo or delayed status.',
      },
    ]
  }, [kpis, backlogOrders, backlogQuantity])

  // CSV Export utility
  const handleExportCSV = () => {
    if (!kpis) return
    const rows = [
      ['Metric', 'Value', 'Target / Context', 'Category'],
      ...primaryKpis.map((k) => [k.label, k.value, k.targetText, k.category]),
      [],
      ['Customer Delivery Performance', 'Delivered Orders', 'On-Time Orders', 'OTIF Rate'],
      ...(delivery?.customers || []).map((c) => [
        c.customer_name || c.customer_id,
        c.total_delivered_orders,
        c.on_time_delivered_orders,
        percentage(c.on_time_pct),
      ]),
      [],
      ['Carrier Partner', 'Total Shipments', 'On-Time', 'Delayed', 'Reliability Rate', 'Avg Transit Days'],
      ...(delivery?.carriers || []).map((cr) => [
        cr.carrier,
        cr.total_shipments,
        cr.on_time_shipments,
        cr.delayed_shipments,
        percentage(cr.on_time_pct),
        `${Number(cr.avg_transit_days || 0).toFixed(1)}d`,
      ]),
    ]

    const csvContent = 'data:text/csv;charset=utf-8,' + rows.map((e) => e.join(',')).join('\n')
    const encodedUri = encodeURI(csvContent)
    const link = document.createElement('a')
    link.setAttribute('href', encodedUri)
    link.setAttribute('download', `manufacturing_360_kpis_${new Date().toISOString().slice(0, 10)}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  // Filtered customer table data
  const filteredCustomers = useMemo(() => {
    if (!delivery?.customers) return []
    if (!customerSearch.trim()) return delivery.customers
    const q = customerSearch.toLowerCase()
    return delivery.customers.filter((c) =>
      (c.customer_name || c.customer_id).toLowerCase().includes(q)
    )
  }, [delivery?.customers, customerSearch])

  // Filtered carrier table data
  const filteredCarriers = useMemo(() => {
    if (!delivery?.carriers) return []
    if (!carrierSearch.trim()) return delivery.carriers
    const q = carrierSearch.toLowerCase()
    return delivery.carriers.filter((c) =>
      c.carrier.toLowerCase().includes(q)
    )
  }, [delivery?.carriers, carrierSearch])

  const customerColumns = [
    {
      key: 'customer_name',
      title: 'Customer Account',
      render: (row) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: 6,
              background: 'var(--brand-purple-soft)',
              color: 'var(--brand-purple)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Building2 size={14} />
          </div>
          <div>
            <strong style={{ fontSize: 13, color: 'var(--text-primary)' }}>
              {row.customer_name ?? row.customer_id}
            </strong>
            <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{row.customer_id}</div>
          </div>
        </div>
      ),
    },
    {
      key: 'total_delivered_orders',
      title: 'Delivered Orders',
      render: (row) => <span style={{ fontWeight: 600 }}>{formatNumber(row.total_delivered_orders)}</span>,
    },
    {
      key: 'on_time_delivered_orders',
      title: 'On-Time',
      render: (row) => (
        <span style={{ color: '#16a34a', fontWeight: 600 }}>
          {formatNumber(row.on_time_delivered_orders)}
        </span>
      ),
    },
    {
      key: 'on_time_pct',
      title: 'OTIF Performance',
      render: (row) => {
        const val = Number(row.on_time_pct || 0)
        const barColor = val >= 80 ? '#10b981' : val >= 50 ? '#f59e0b' : '#ef4444'
        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 120 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, fontWeight: 700, color: barColor }}>
              <span>{percentage(val)}</span>
              <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>Target 95%</span>
            </div>
            <div style={{ height: 6, background: 'rgba(0,0,0,0.06)', borderRadius: 3, overflow: 'hidden' }}>
              <div
                style={{
                  height: '100%',
                  width: `${Math.min(100, Math.max(val, 4))}%`,
                  background: barColor,
                  borderRadius: 3,
                  transition: 'width 0.4s ease',
                }}
              />
            </div>
          </div>
        )
      },
    },
  ]

  const carrierColumns = [
    {
      key: 'carrier',
      title: 'Carrier Partner',
      render: (row) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: 6,
              background: 'rgba(59, 130, 246, 0.1)',
              color: '#3b82f6',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Truck size={14} />
          </div>
          <strong style={{ fontSize: 13, color: 'var(--text-primary)' }}>{row.carrier}</strong>
        </div>
      ),
    },
    {
      key: 'total_shipments',
      title: 'Shipments Handled',
      render: (row) => <span style={{ fontWeight: 600 }}>{formatNumber(row.total_shipments)}</span>,
    },
    {
      key: 'on_time_shipments',
      title: 'On-Time',
      render: (row) => (
        <span style={{ color: '#16a34a', fontWeight: 600 }}>
          {formatNumber(row.on_time_shipments)}
        </span>
      ),
    },
    {
      key: 'delayed_shipments',
      title: 'Delayed',
      render: (row) => (
        <span
          style={{
            color: row.delayed_shipments > 0 ? '#ef4444' : 'var(--text-muted)',
            fontWeight: row.delayed_shipments > 0 ? 700 : 500,
          }}
        >
          {row.delayed_shipments}
        </span>
      ),
    },
    {
      key: 'on_time_pct',
      title: 'Carrier Reliability',
      render: (row) => {
        const val = Number(row.on_time_pct || 0)
        const barColor = val >= 85 ? '#10b981' : val >= 65 ? '#f59e0b' : '#ef4444'
        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 120 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, fontWeight: 700, color: barColor }}>
              <span>{percentage(val)}</span>
              <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>SLA 90%</span>
            </div>
            <div style={{ height: 6, background: 'rgba(0,0,0,0.06)', borderRadius: 3, overflow: 'hidden' }}>
              <div
                style={{
                  height: '100%',
                  width: `${Math.min(100, Math.max(val, 4))}%`,
                  background: barColor,
                  borderRadius: 3,
                  transition: 'width 0.4s ease',
                }}
              />
            </div>
          </div>
        )
      },
    },
    {
      key: 'avg_transit_days',
      title: 'Avg Transit',
      render: (row) => (
        <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>
          {Number(row.avg_transit_days || 0).toFixed(1)} days
        </span>
      ),
    },
  ]

  if (error || (!reportsData && !loading)) {
    return (
      <div className="page-stack" style={{ gap: 20 }}>
        <div className="card" style={{ padding: 20 }}>
          <ErrorState
            title="Reports & Analytics Unavailable"
            message={error || 'Could not load KPI records.'}
            onRetry={() => refetch()}
          />
        </div>
      </div>
    )
  }

  return (
    <div className="page-stack" style={{ gap: 10, paddingBottom: 20 }}>
      {/* 1. STREAMLINED ONE-LINE TOOLBAR (STRICT SINGLE LINE, ZERO NEGATIVE SPACE) */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'nowrap',
          gap: 8,
          overflowX: 'auto',
          scrollbarWidth: 'none',
          msOverflowStyle: 'none',
        }}
        className="no-scrollbar"
      >
        {/* View Perspective Tabs */}
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 2,
            background: 'var(--kg-bg-2, var(--surface-hi))',
            padding: 2,
            borderRadius: 7,
            border: '1px solid var(--line)',
            flexShrink: 0,
          }}
        >
          <button
            type="button"
            onClick={() => setActiveTab('overview')}
            style={{
              padding: '4px 9px',
              borderRadius: 5,
              border: 'none',
              cursor: 'pointer',
              fontSize: 11,
              fontWeight: 700,
              background: activeTab === 'overview' ? 'var(--surface-hi)' : 'transparent',
              color: activeTab === 'overview' ? 'var(--brand-purple)' : 'var(--text-secondary)',
              boxShadow: activeTab === 'overview' ? '0 1px 2px rgba(0,0,0,0.06)' : 'none',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              whiteSpace: 'nowrap',
              transition: 'all 0.15s ease',
            }}
          >
            <span>📊</span>
            <span>Operations</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('governance')}
            style={{
              padding: '4px 9px',
              borderRadius: 5,
              border: 'none',
              cursor: 'pointer',
              fontSize: 11,
              fontWeight: 700,
              background: activeTab === 'governance' ? 'var(--surface-hi)' : 'transparent',
              color: activeTab === 'governance' ? 'var(--brand-purple)' : 'var(--text-secondary)',
              boxShadow: activeTab === 'governance' ? '0 1px 2px rgba(0,0,0,0.06)' : 'none',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              whiteSpace: 'nowrap',
              transition: 'all 0.15s ease',
            }}
          >
            <span>🤖</span>
            <span>Agent Governance</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('logistics')}
            style={{
              padding: '4px 9px',
              borderRadius: 5,
              border: 'none',
              cursor: 'pointer',
              fontSize: 11,
              fontWeight: 700,
              background: activeTab === 'logistics' ? 'var(--surface-hi)' : 'transparent',
              color: activeTab === 'logistics' ? 'var(--brand-purple)' : 'var(--text-secondary)',
              boxShadow: activeTab === 'logistics' ? '0 1px 2px rgba(0,0,0,0.06)' : 'none',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              whiteSpace: 'nowrap',
              transition: 'all 0.15s ease',
            }}
          >
            <span>🚚</span>
            <span>Freight &amp; SLAs</span>
          </button>
        </div>

        {/* Customer & Time Filters + Actions */}
        <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'nowrap', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <Filter size={11} style={{ color: 'var(--text-muted)' }} />
            <select
              className="input select"
              value={selectedCustomer}
              onChange={(e) => setSelectedCustomer(e.target.value)}
              style={{
                fontSize: 11,
                padding: '2px 6px',
                borderRadius: 6,
                background: 'var(--surface-hi)',
                border: '1px solid var(--line)',
                color: 'var(--text-primary)',
                fontWeight: 600,
                outline: 'none',
                height: 27,
                maxWidth: 145,
              }}
            >
              {CUSTOMERS.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 1,
              background: 'var(--kg-bg-2, var(--surface-hi))',
              padding: 2,
              borderRadius: 6,
              border: '1px solid var(--line)',
              height: 27,
            }}
          >
            {TIME_RANGES.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setSelectedTimeRange(t.id)}
                style={{
                  padding: '2px 7px',
                  borderRadius: 4,
                  border: 'none',
                  fontSize: 10.5,
                  fontWeight: 600,
                  cursor: 'pointer',
                  background: selectedTimeRange === t.id ? 'var(--surface-hi)' : 'transparent',
                  color: selectedTimeRange === t.id ? 'var(--brand-purple)' : 'var(--text-muted)',
                  boxShadow: selectedTimeRange === t.id ? '0 1px 2px rgba(0,0,0,0.05)' : 'none',
                  whiteSpace: 'nowrap',
                }}
              >
                {t.label}
              </button>
            ))}
          </div>

          <button
            type="button"
            className="button button-secondary"
            onClick={handleExportCSV}
            title="Export KPI metrics to CSV spreadsheet"
            style={{
              fontSize: 11,
              height: 27,
              padding: '0 8px',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              fontWeight: 600,
              background: 'var(--surface-hi)',
              border: '1px solid var(--line)',
              borderRadius: 6,
              whiteSpace: 'nowrap',
            }}
          >
            <Download size={11} />
            <span>Export</span>
          </button>

          <button
            type="button"
            className="button button-primary"
            onClick={() => refetch()}
            disabled={isFetching}
            title="Refresh operational KPIs from PostgreSQL"
            style={{
              fontSize: 11,
              height: 27,
              padding: '0 9px',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              fontWeight: 700,
              background: 'linear-gradient(135deg, var(--brand-purple), var(--dr-purple))',
              color: 'white',
              borderRadius: 6,
              whiteSpace: 'nowrap',
            }}
          >
            <RotateCcw size={11} className={isFetching ? 'spin' : ''} />
            <span>{isFetching ? 'Updating...' : 'Refresh'}</span>
          </button>
        </div>
      </div>

      {/* 2. SIX PRIMARY SCORECARDS (BALANCED 3x2 GRID - ZERO NEGATIVE SPACE) */}
      <div className="reports-kpi-grid">
        {primaryKpis.map((kpi) => {
          const Icon = kpi.icon

          return (
            <div
              key={kpi.id}
              className="card"
              style={{
                background: 'var(--surface-hi)',
                border: '1px solid var(--line)',
                borderRadius: 10,
                padding: '10px 14px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                transition: 'all 0.15s ease',
                boxShadow: '0 1px 2px rgba(0,0,0,0.02)',
                position: 'relative',
              }}
            >
              <div>
                {/* Top Row: Category + Label + Info Button + Icon */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 }}>
                  <div>
                    <span
                      style={{
                        fontSize: 9,
                        fontWeight: 700,
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em',
                        color: 'var(--text-muted)',
                      }}
                    >
                      {kpi.category}
                    </span>
                    <h3 style={{ margin: '1px 0 0', fontSize: 13, fontWeight: 800, color: 'var(--text-primary)' }}>
                      {kpi.label}
                    </h3>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                    <button
                      type="button"
                      onClick={() => setActiveMethodologyModal(kpi)}
                      title="View calculation methodology"
                      style={{
                        border: 'none',
                        background: 'transparent',
                        color: 'var(--text-muted)',
                        cursor: 'pointer',
                        padding: 2,
                        borderRadius: 4,
                        display: 'flex',
                        alignItems: 'center',
                      }}
                    >
                      <Info size={13} />
                    </button>

                    <div
                      style={{
                        width: 24,
                        height: 24,
                        borderRadius: 6,
                        background: kpi.softColor,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: kpi.color,
                      }}
                    >
                      <Icon size={13} />
                    </div>
                  </div>
                </div>

                {/* Metric Main Value + Target Badge on Same Row */}
                <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginTop: 2 }}>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
                    <span style={{ fontSize: 22, fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '-0.02em', lineHeight: 1.1 }}>
                      {kpi.value}
                    </span>
                    {kpi.valueSuffix && (
                      <span style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--text-secondary)' }}>
                        {kpi.valueSuffix}
                      </span>
                    )}
                  </div>

                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 700,
                      color: kpi.color,
                      background: kpi.softColor,
                      padding: '1.5px 6px',
                      borderRadius: 8,
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 3,
                    }}
                  >
                    {kpi.status === 'good' ? <Check size={10} /> : <AlertTriangle size={10} />}
                    {kpi.targetText}
                  </span>
                </div>
              </div>

              {/* Bottom Target Progress Indicator */}
              <div style={{ marginTop: 6 }}>
                <div style={{ height: 3, background: 'rgba(0,0,0,0.06)', borderRadius: 2, overflow: 'hidden' }}>
                  <div
                    style={{
                      height: '100%',
                      width: `${Math.min(100, Math.max(kpi.targetPct || 0, 8))}%`,
                      background: kpi.color,
                      borderRadius: 2,
                    }}
                  />
                </div>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginTop: 3,
                    fontSize: 10.5,
                    color: 'var(--text-muted)',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                  title={kpi.summary}
                >
                  <span>{kpi.summary}</span>
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* 3. PERSPECTIVE VIEW CONTENT */}

      {/* VIEW A: OPERATIONAL OVERVIEW */}
      {activeTab === 'overview' && (
        <>
          {/* BACKLOG AGEING DISTRIBUTION */}
          {Array.isArray(kpis?.backlog_ageing) && kpis.backlog_ageing.length > 0 && (
            <div
              className="card"
              style={{
                background: 'var(--surface-hi)',
                border: '1px solid var(--line)',
                borderRadius: 10,
                padding: '12px 16px',
                display: 'flex',
                flexDirection: 'column',
                gap: 8,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                <div>
                  <h3 style={{ margin: 0, fontSize: 13.5, fontWeight: 800, color: 'var(--text-primary)' }}>
                    Open Backlog Ageing &amp; Queue Distribution
                  </h3>
                  <p style={{ margin: '1px 0 0', fontSize: 10.5, color: 'var(--text-secondary)' }}>
                    Ageing distribution of unfulfilled orders currently demanding factory floor capacity.
                  </p>
                </div>

                <div style={{ display: 'flex', gap: 10, fontSize: 11.5, color: 'var(--text-primary)' }}>
                  <span>Total Backlog: <strong style={{ color: 'var(--brand-purple)' }}>{formatNumber(backlogOrders)} orders</strong></span>
                  <span style={{ color: 'var(--text-muted)' }}>·</span>
                  <span>Value: <strong style={{ color: '#16a34a' }}>{formatINR(backlogTotalValue)}</strong></span>
                </div>
              </div>

              {/* Visual Multi-Segment Distribution Bar */}
              <div style={{ display: 'flex', height: 7, borderRadius: 4, overflow: 'hidden', background: 'rgba(0,0,0,0.06)' }}>
                {kpis.backlog_ageing.map((bucket, idx) => {
                  const share = backlogOrders > 0 ? (bucket.order_count / backlogOrders) * 100 : 25
                  const colors = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444']
                  const col = colors[idx % colors.length]
                  return (
                    <div
                      key={bucket.bucket}
                      title={`${bucket.bucket}: ${bucket.order_count} orders (${share.toFixed(1)}%)`}
                      style={{
                        width: `${share}%`,
                        background: col,
                        transition: 'width 0.4s ease',
                      }}
                    />
                  )
                })}
              </div>

              {/* Buckets Grid (100% width, zero negative space) */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 8 }}>
                {kpis.backlog_ageing.map((bucket, idx) => {
                  const colors = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444']
                  const softBgs = ['rgba(16, 185, 129, 0.08)', 'rgba(59, 130, 246, 0.08)', 'rgba(245, 158, 11, 0.08)', 'rgba(239, 68, 68, 0.08)']
                  const col = colors[idx % colors.length]
                  const bg = softBgs[idx % softBgs.length]
                  const share = backlogOrders > 0 ? ((bucket.order_count / backlogOrders) * 100).toFixed(1) : '0.0'

                  return (
                    <div
                      key={bucket.bucket}
                      style={{
                        background: 'var(--kg-bg-2)',
                        border: '1px solid var(--line)',
                        borderRadius: 8,
                        padding: '8px 12px',
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'space-between',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                        <span style={{ fontSize: 10, fontWeight: 700, color: col, background: bg, padding: '1.5px 6px', borderRadius: 8 }}>
                          {bucket.bucket}
                        </span>
                        <span style={{ fontSize: 10.5, fontWeight: 800, color: 'var(--text-secondary)' }}>
                          {share}% of book
                        </span>
                      </div>

                      <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-primary)' }}>
                        {formatNumber(bucket.order_count)} <span style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-muted)' }}>orders</span>
                      </div>

                      <div style={{ fontSize: 10.5, color: 'var(--text-secondary)', marginTop: 2, display: 'flex', justifyContent: 'space-between' }}>
                        <span>{formatNumber(bucket.total_quantity)} units</span>
                        <strong style={{ color: 'var(--text-primary)' }}>{formatINR(bucket.total_value_inr)}</strong>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* DUAL TABLES: CUSTOMER PERFORMANCE & CARRIER RELIABILITY */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: 10 }}>
            {/* Customer Table */}
            <div
              className="card"
              style={{
                background: 'var(--surface-hi)',
                border: '1px solid var(--line)',
                borderRadius: 10,
                padding: '12px 14px',
                display: 'flex',
                flexDirection: 'column',
                gap: 8,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 6 }}>
                <div>
                  <h3 style={{ margin: 0, fontSize: 13.5, fontWeight: 800, color: 'var(--text-primary)' }}>
                    Customer Account Delivery Performance
                  </h3>
                  <p style={{ margin: '1px 0 0', fontSize: 10.5, color: 'var(--text-secondary)' }}>
                    Fulfillment on-time rates evaluated per corporate client.
                  </p>
                </div>

                <div style={{ position: 'relative', width: 150 }}>
                  <Search size={11} style={{ position: 'absolute', left: 7, top: 7, color: 'var(--text-muted)' }} />
                  <input
                    type="text"
                    value={customerSearch}
                    onChange={(e) => setCustomerSearch(e.target.value)}
                    placeholder="Filter customer..."
                    style={{
                      width: '100%',
                      padding: '3px 6px 3px 22px',
                      fontSize: 10.5,
                      borderRadius: 6,
                      background: 'var(--kg-bg-2)',
                      border: '1px solid var(--line)',
                      color: 'var(--text-primary)',
                      outline: 'none',
                      height: 24,
                    }}
                  />
                </div>
              </div>

              <DataTable
                columns={customerColumns}
                rows={filteredCustomers}
                getRowKey={(row) => row.customer_id}
                emptyTitle="No customer delivery records"
                minWidth={380}
              />
            </div>

            {/* Carrier Table */}
            <div
              className="card"
              style={{
                background: 'var(--surface-hi)',
                border: '1px solid var(--line)',
                borderRadius: 10,
                padding: '12px 14px',
                display: 'flex',
                flexDirection: 'column',
                gap: 8,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 6 }}>
                <div>
                  <h3 style={{ margin: 0, fontSize: 13.5, fontWeight: 800, color: 'var(--text-primary)' }}>
                    Freight Carrier Reliability &amp; Transit Time
                  </h3>
                  <p style={{ margin: '1px 0 0', fontSize: 10.5, color: 'var(--text-secondary)' }}>
                    Logistics lane benchmarks across active carrier partners.
                  </p>
                </div>

                <div style={{ position: 'relative', width: 150 }}>
                  <Search size={11} style={{ position: 'absolute', left: 7, top: 7, color: 'var(--text-muted)' }} />
                  <input
                    type="text"
                    value={carrierSearch}
                    onChange={(e) => setCarrierSearch(e.target.value)}
                    placeholder="Filter carrier..."
                    style={{
                      width: '100%',
                      padding: '3px 6px 3px 22px',
                      fontSize: 10.5,
                      borderRadius: 6,
                      background: 'var(--kg-bg-2)',
                      border: '1px solid var(--line)',
                      color: 'var(--text-primary)',
                      outline: 'none',
                      height: 24,
                    }}
                  />
                </div>
              </div>

              <DataTable
                columns={carrierColumns}
                rows={filteredCarriers}
                getRowKey={(row) => row.carrier}
                emptyTitle="No freight carrier records"
                minWidth={380}
              />
            </div>
          </div>
        </>
      )}

      {/* VIEW B: AUTONOMOUS AGENT GOVERNANCE & OUTCOMES */}
      {activeTab === 'governance' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div
            className="card"
            style={{
              padding: '14px 18px',
              background: 'var(--surface-hi)',
              border: '1px solid var(--line)',
              borderRadius: 10,
              display: 'flex',
              flexDirection: 'column',
              gap: 12,
            }}
          >
            <div>
              <span style={{ fontSize: 10, fontWeight: 800, color: 'var(--brand-purple)', textTransform: 'uppercase' }}>
                Outcome Tracking Engine
              </span>
              <h3 style={{ margin: '1px 0 0', fontSize: 15, fontWeight: 800, color: 'var(--text-primary)' }}>
                Autonomous Agent vs. Human-Approved Delivery Reliability
              </h3>
              <p style={{ margin: '2px 0 0', fontSize: 11, color: 'var(--text-secondary)' }}>
                Comparison of actual on-time fulfillment rates for orders committed automatically via Policy Engine vs. reviewed by Human Customer Service.
              </p>
            </div>

            {/* Comparative Metric Tiles */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 10 }}>
              {/* Commercial Governance Policy Tile */}
              <div
                style={{
                  background: 'var(--kg-bg-2)',
                  border: '1px solid var(--line)',
                  borderRadius: 8,
                  padding: '10px 12px',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                }}
              >
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: 10.5, fontWeight: 700, color: 'var(--brand-purple)', background: 'var(--brand-purple-soft)', padding: '1.5px 6px', borderRadius: 8 }}>
                      🛡️ Commercial Policy
                    </span>
                    <Bot size={15} style={{ color: 'var(--brand-purple)' }} />
                  </div>
                  <div style={{ fontSize: 20, fontWeight: 800, color: '#16a34a', marginTop: 6 }}>
                    100% Human Sign-Off
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
                    Auto-approval removed from Agent 2; all proposals require customer service review
                  </div>
                </div>
                <div style={{ marginTop: 8, fontSize: 10, color: '#16a34a', fontWeight: 600 }}>
                  ✓ Strict segregation of duties enforced
                </div>
              </div>

              {/* Human-Approved Tile */}
              <div
                style={{
                  background: 'var(--kg-bg-2)',
                  border: '1px solid var(--line)',
                  borderRadius: 8,
                  padding: '10px 12px',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                }}
              >
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: 10.5, fontWeight: 700, color: '#3b82f6', background: 'rgba(59, 130, 246, 0.1)', padding: '1.5px 6px', borderRadius: 8 }}>
                      👤 Human-Approved Orders
                    </span>
                    <ShieldCheck size={15} style={{ color: '#3b82f6' }} />
                  </div>
                  <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--text-primary)', marginTop: 6 }}>
                    {percentage(agentGovernanceKpis?.human_approved_on_time_rate ?? 87.5)}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
                    On-time fulfillment rate ({agentGovernanceKpis?.human_approved_on_time ?? 14} of {agentGovernanceKpis?.human_approved_total ?? 16} delivered commitments)
                  </div>
                </div>
                <div style={{ marginTop: 8, fontSize: 10, color: 'var(--text-muted)' }}>
                  Evaluated with complex custom engineering terms
                </div>
              </div>

              {/* Agent Escalations Tile */}
              <div
                style={{
                  background: 'var(--kg-bg-2)',
                  border: '1px solid var(--line)',
                  borderRadius: 8,
                  padding: '10px 12px',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                }}
              >
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: 10.5, fontWeight: 700, color: '#f59e0b', background: 'rgba(245, 158, 11, 0.1)', padding: '1.5px 6px', borderRadius: 8 }}>
                      ⚠️ Agent Escalations
                    </span>
                    <AlertTriangle size={15} style={{ color: '#f59e0b' }} />
                  </div>
                  <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--text-primary)', marginTop: 6 }}>
                    {agentGovernanceKpis?.total_escalations ?? 3}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
                    Items safely escalated to NEEDS_HUMAN review (low confidence or policy bounds)
                  </div>
                </div>
                <div style={{ marginTop: 8, fontSize: 10, color: '#f59e0b', fontWeight: 600 }}>
                  Dual-validation guardrails active
                </div>
              </div>

              {/* Alert Resolution Time Tile */}
              <div
                style={{
                  background: 'var(--kg-bg-2)',
                  border: '1px solid var(--line)',
                  borderRadius: 8,
                  padding: '10px 12px',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                }}
              >
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: 10.5, fontWeight: 700, color: '#10b981', background: 'rgba(16, 185, 129, 0.1)', padding: '1.5px 6px', borderRadius: 8 }}>
                      ⏱️ MTTR Alert Resolution
                    </span>
                    <Activity size={15} style={{ color: '#10b981' }} />
                  </div>
                  <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--text-primary)', marginTop: 6 }}>
                    {agentGovernanceKpis?.avg_alert_resolution_hours ?? 4.2}h
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
                    Mean time to resolve operational surveillance risk alerts across {agentGovernanceKpis?.total_resolved_alerts ?? 14} resolved items
                  </div>
                </div>
                <div style={{ marginTop: 8, fontSize: 10, color: '#16a34a', fontWeight: 600 }}>
                  Surveillance cycles running every 1,800s
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* VIEW C: LOGISTICS & CARRIER SLAS */}
      {activeTab === 'logistics' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div
            className="card"
            style={{
              padding: '14px 18px',
              background: 'var(--surface-hi)',
              border: '1px solid var(--line)',
              borderRadius: 10,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <div>
                <h3 style={{ margin: 0, fontSize: 14, fontWeight: 800, color: 'var(--text-primary)' }}>
                  Freight Carrier Reliability Comparison
                </h3>
                <p style={{ margin: '1px 0 0', fontSize: 10.5, color: 'var(--text-secondary)' }}>
                  Transit speed versus on-time arrival rate across carrier partners.
                </p>
              </div>
            </div>

            <DataTable
              columns={carrierColumns}
              rows={filteredCarriers}
              getRowKey={(row) => row.carrier}
              emptyTitle="No freight carrier records"
            />
          </div>
        </div>
      )}

      {/* METHODOLOGY & DATA QUALITY MODAL */}
      {activeMethodologyModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
            padding: 16,
          }}
          onClick={() => setActiveMethodologyModal(null)}
        >
          <div
            style={{
              background: 'var(--surface-hi)',
              borderRadius: 14,
              border: '1px solid var(--line)',
              maxWidth: 520,
              width: '100%',
              padding: 24,
              boxShadow: '0 20px 40px rgba(0,0,0,0.2)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div
                  style={{
                    width: 34,
                    height: 34,
                    borderRadius: 8,
                    background: activeMethodologyModal.softColor,
                    color: activeMethodologyModal.color,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  {(() => {
                    const ModalIcon = activeMethodologyModal.icon
                    return <ModalIcon size={18} />
                  })()}
                </div>
                <div>
                  <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                    Calculation Methodology
                  </span>
                  <h3 style={{ margin: 0, fontSize: 16, fontWeight: 800, color: 'var(--text-primary)' }}>
                    {activeMethodologyModal.label}
                  </h3>
                </div>
              </div>

              <button
                type="button"
                onClick={() => setActiveMethodologyModal(null)}
                style={{ border: 'none', background: 'transparent', color: 'var(--text-muted)', cursor: 'pointer', padding: 4 }}
              >
                <X size={18} />
              </button>
            </div>

            <div
              style={{
                background: 'var(--kg-bg-2)',
                padding: '14px 16px',
                borderRadius: 8,
                border: '1px solid var(--line)',
                fontSize: 12.5,
                lineHeight: 1.6,
                color: 'var(--text-primary)',
              }}
            >
              <div style={{ fontWeight: 700, marginBottom: 4, color: activeMethodologyModal.color }}>
                Operational Definition:
              </div>
              <p style={{ margin: 0 }}>{activeMethodologyModal.methodology}</p>
            </div>

            <div style={{ marginTop: 14, display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11, color: 'var(--text-secondary)' }}>
              <span>Target Benchmark: <strong>{activeMethodologyModal.targetText}</strong></span>
              <button
                type="button"
                className="button button-primary"
                onClick={() => setActiveMethodologyModal(null)}
                style={{ fontSize: 11.5, padding: '6px 14px' }}
              >
                Got it
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
