import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  FilePlus2,
  Cpu,
  Layers,
  ShieldCheck,
  BellRing,
  Truck,
  CheckCircle2,
  Sparkles,
  Bot,
  ArrowRight,
  TrendingUp,
} from 'lucide-react'
import { agentsApi } from '../../api/agents.api'
import { workflowApi } from '../../api/workflow.api'
import { ordersApi } from '../../api/orders.api'

export function LifecycleVisualizer({ onOpenIntake, activeStage = 1 }) {
  const [metrics, setMetrics] = useState({
    assessmentsCount: 0,
    pendingApprovalsCount: 0,
    monitoredCount: 0,
    openAlertsCount: 0,
    deliveredCount: 0,
    loading: true,
  })

  useEffect(() => {
    let active = true
    Promise.allSettled([
      agentsApi.listAssessments({ limit: 100 }),
      workflowApi.listProposals({ status: 'PENDING' }),
      agentsApi.listMonitoringRecords({ status: 'ACTIVE', limit: 100 }),
      agentsApi.getAlertsSummary(),
      ordersApi.list({ status: 'DELIVERED', page: 1, page_size: 1 }),
    ]).then(([assessmentsRes, proposalsRes, monitoringRes, alertsRes, deliveredRes]) => {
      if (!active) return
      setMetrics({
        assessmentsCount: assessmentsRes.status === 'fulfilled' && Array.isArray(assessmentsRes.value) ? assessmentsRes.value.length : 0,
        pendingApprovalsCount: proposalsRes.status === 'fulfilled' && Array.isArray(proposalsRes.value) ? proposalsRes.value.length : 0,
        monitoredCount: monitoringRes.status === 'fulfilled' && Array.isArray(monitoringRes.value) ? monitoringRes.value.length : 0,
        openAlertsCount: alertsRes.status === 'fulfilled' && alertsRes.value?.total_open != null ? alertsRes.value.total_open : 0,
        deliveredCount: deliveredRes.status === 'fulfilled' && typeof deliveredRes.value?.total === 'number' ? deliveredRes.value.total : 0,
        loading: false,
      })
    })
    return () => { active = false }
  }, [])

  const stages = [
    {
      num: '01',
      title: 'Order Intake',
      agent: 'Sales / Portal',
      desc: 'Schedules & POs',
      metric: onOpenIntake ? 'New Order' : 'Active',
      onClick: onOpenIntake,
      icon: FilePlus2,
      active: activeStage === 1,
    },
    {
      num: '02',
      title: 'Agent 2 Feasibility',
      agent: 'Agent 2',
      desc: '7-Dept Audit',
      metric: `${metrics.assessmentsCount} evaluated`,
      to: '/allocation',
      icon: Cpu,
      active: activeStage === 2,
    },
    {
      num: '03',
      title: 'Commitment Plan',
      agent: 'Agent 2',
      desc: 'ATP/CTP Schedule',
      metric: 'Achievable Date',
      to: '/allocation',
      icon: Layers,
      active: activeStage === 3,
    },
    {
      num: '04',
      title: 'Commercial Approval',
      agent: 'Human In Loop',
      desc: 'Customer Service Review',
      metric: `${metrics.pendingApprovalsCount} pending`,
      to: '/approvals',
      icon: ShieldCheck,
      active: activeStage === 4,
    },
    {
      num: '05',
      title: 'Active Surveillance',
      agent: 'Agent 3',
      desc: 'Durable Leased Daemon',
      metric: `${metrics.monitoredCount} monitored`,
      to: '/alerts',
      icon: Bot,
      active: activeStage === 5,
    },
    {
      num: '06',
      title: 'Risk Alerts & Routing',
      agent: 'Agent 3',
      desc: 'MMS, MES, QMS, TMS',
      metric: `${metrics.openAlertsCount} active risks`,
      to: '/alerts',
      icon: BellRing,
      active: activeStage === 6,
    },
    {
      num: '07',
      title: 'Delivery Closure',
      agent: 'Fulfillment',
      desc: 'Milestones & Release',
      metric: `${metrics.deliveredCount} delivered`,
      to: '/orders?status=DELIVERED',
      icon: CheckCircle2,
      active: activeStage === 7,
    },
  ]

  return (
    <div className="lifecycle-visualizer-card">
      <div className="lifecycle-header">
        <div>
          <div className="eyebrow" style={{ color: 'var(--brand-orange)' }}>
            <span className="eyebrow-dot" style={{ background: 'var(--brand-orange)' }} />
            MANUFACTURING 360 · AUTONOMOUS AGENT ORCHESTRATION
          </div>
          <h2>
            <TrendingUp size={18} color="var(--brand-orange)" />
            Visible Three-Agent Order Lifecycle
          </h2>
        </div>

        <div className="lifecycle-agent1-banner">
          <Sparkles size={15} color="#c4b5fd" />
          <span><strong>Agent 1 (Intelligence Layer):</strong> Conversational Order Lookup &amp; Grounded QA Active Throughout</span>
          <Link to="/assistant" style={{ marginLeft: 6, color: '#fff', textDecoration: 'underline' }}>
            Open Agent 1 →
          </Link>
        </div>
      </div>

      <div className="lifecycle-stages-flow">
        {stages.map((stage) => {
          const Icon = stage.icon
          const content = (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="stage-step-num">{stage.num}</span>
                <Icon size={16} color={stage.active ? '#f58a3a' : 'var(--text-secondary)'} />
              </div>
              <div className="stage-step-title">{stage.title}</div>
              <div className="stage-step-desc">{stage.desc}</div>
              <div className="stage-step-metric">
                {stage.onClick ? (
                  <span style={{ cursor: 'pointer', textDecoration: 'underline' }}>{stage.metric}</span>
                ) : (
                  stage.metric
                )}
              </div>
            </>
          )

          if (stage.onClick) {
            return (
              <button
                type="button"
                key={stage.num}
                onClick={stage.onClick}
                className={`lifecycle-stage-step ${stage.active ? 'active' : ''}`}
                style={{ cursor: 'pointer', background: 'transparent' }}
              >
                {content}
              </button>
            )
          }

          return (
            <Link
              key={stage.num}
              to={stage.to}
              className={`lifecycle-stage-step ${stage.active ? 'active' : ''}`}
            >
              {content}
            </Link>
          )
        })}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11, color: 'var(--text-secondary)', flexWrap: 'wrap', gap: 8 }}>
        <div>
          Sequence: <strong>Intake</strong> → <strong>Agent 2 Assessment (7 Departments)</strong> → <strong>Promise Date Proposal</strong> → <strong>CS Approval</strong> → <strong>Agent 3 Monitoring</strong> → <strong>Delivery</strong>
        </div>
        {onOpenIntake && (
          <button
            type="button"
            className="button button-primary"
            onClick={onOpenIntake}
            style={{ fontSize: 11, padding: '4px 12px', minHeight: 28 }}
          >
            <FilePlus2 size={13} /> + Create New Customer Order
          </button>
        )}
      </div>
    </div>
  )
}

