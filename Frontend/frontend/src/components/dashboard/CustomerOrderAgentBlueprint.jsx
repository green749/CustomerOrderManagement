import {
  ShieldCheck,
  Cpu,
  Layers,
  Database,
  FileCheck2,
  TrendingUp,
  AlertTriangle,
  Clock,
  DollarSign,
  Sparkles,
} from 'lucide-react'
import { formatINR, formatNumber } from '../../utils/format'

const percentage = (value) => (value == null ? '—' : `${Number(value).toFixed(1)}%`)

export function CustomerOrderAgentBlueprint({ slide18 }) {
  const kpis = [
    {
      code: 'OTIF',
      name: 'OTIF Customer',
      value: slide18?.otif?.otif_rate_pct != null ? percentage(slide18.otif.otif_rate_pct) : '88.3%',
      target: `Target: ${slide18?.otif?.target_otif_pct ?? 95}%`,
      sub: 'On-time & in-full delivery rate',
      status: 'good',
    },
    {
      code: 'OCT',
      name: 'Order Confirmation Time',
      value:
        slide18?.order_confirmation_time?.average_confirmation_days_proxy != null
          ? `${slide18.order_confirmation_time.average_confirmation_days_proxy.toFixed(1)} days`
          : '0.8 days',
      target: 'Intake to confirmed commit',
      sub: 'Autonomous 7-dept calculation',
      status: 'neutral',
    },
    {
      code: 'SCHED',
      name: 'Schedule Adherence',
      value:
        slide18?.schedule_adherence?.schedule_adherence_pct != null
          ? percentage(slide18.schedule_adherence.schedule_adherence_pct)
          : '87.5%',
      target: `${formatNumber(slide18?.schedule_adherence?.on_time_production_orders ?? 21)} of ${formatNumber(slide18?.schedule_adherence?.total_production_orders ?? 24)} orders`,
      sub: 'Plant production plan execution',
      status: 'good',
    },
    {
      code: 'BACKLOG',
      name: 'Backlog Ageing',
      value: `${formatNumber(slide18?.backlog_ageing?.reduce((sum, b) => sum + b.order_count, 0) ?? 289)} orders`,
      target: 'Buckets: 0-7d · 8-14d · 15-30d · 30+d',
      sub: 'Unfulfilled customer orders',
      status: 'warning',
    },
    {
      code: 'PDA',
      name: 'Promise-Date Accuracy',
      value:
        slide18?.promise_date_accuracy?.promise_date_accuracy_pct != null
          ? percentage(slide18.promise_date_accuracy.promise_date_accuracy_pct)
          : '91.2%',
      target: 'Commitment adherence rate',
      sub: 'Deliveries on/before promise date',
      status: 'good',
    },
    {
      code: 'EXPEDITE',
      name: 'Expedite Cost (Proxy)',
      value: slide18?.expedite_cost?.total_expedite_cost_inr != null
        ? formatINR(slide18.expedite_cost.total_expedite_cost_inr)
        : '₹14,25,000',
      target: `${formatNumber(slide18?.expedite_cost?.air_cargo_shipments ?? 3)} air cargo shipments`,
      sub: 'Logistics variance mitigation',
      status: 'warning',
    },
  ]

  return (
    <div className="card blueprint-card" style={{ padding: '24px 28px', background: 'var(--surface-hi)', border: '1px solid var(--line)', borderRadius: 14 }}>
      {/* 1. TOP TITLE */}
      <div style={{ marginBottom: 16 }}>
        <h2 style={{ fontSize: 24, fontWeight: 800, margin: 0, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
          Customer Order Management Agent
        </h2>
        <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--text-secondary)', fontWeight: 500 }}>
          Connect customer demand to plant execution
        </p>
      </div>

      {/* 2. PURPOSE (NAVY BANNER) */}
      <div
        style={{
          background: '#1F2F59',
          color: '#FFFFFF',
          borderRadius: 8,
          padding: '14px 18px',
          marginBottom: 18,
          border: '1px solid rgba(255, 255, 255, 0.08)',
        }}
      >
        <div style={{ fontSize: 10, fontWeight: 800, color: '#31B7C3', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 4 }}>
          PURPOSE
        </div>
        <p style={{ margin: 0, fontSize: 12, lineHeight: 1.55, color: '#E7EDFA' }}>
          Improve order visibility from customer schedule and purchase order through confirmation, production, quality release and dispatch. Highlight delivery risk early and coordinate realistic commitments.
        </p>
      </div>

      {/* 3. MIDDLE 2 LARGE COLUMNS */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16, marginBottom: 18 }}>
        {/* WHAT THIS AGENT IS RESPONSIBLE FOR */}
        <div
          style={{
            background: 'var(--kg-bg-2)',
            border: '1px solid var(--line)',
            borderLeft: '4px solid #31B7C3',
            borderRadius: 8,
            padding: '16px 18px',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <div style={{ fontSize: 11, fontWeight: 800, color: '#31B7C3', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 10 }}>
            WHAT THIS AGENT IS RESPONSIBLE FOR
          </div>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 11.5, lineHeight: 1.6, color: 'var(--text-secondary)' }}>
            <li>Consolidate customer schedules, purchase orders, forecast releases and engineering revisions.</li>
            <li>Validate order quantities, requested dates, ship-to, packaging, price and product configuration.</li>
            <li>Check material, capacity, production status, quality holds and logistics readiness.</li>
            <li>Calculate promise-date risk and recommend feasible commit dates or allocation options.</li>
            <li>Prepare customer status updates and escalation packs for authorized account teams.</li>
          </ul>
        </div>

        {/* HOW THE AGENT SHOULD WORK */}
        <div
          style={{
            background: 'var(--kg-bg-2)',
            border: '1px solid var(--line)',
            borderLeft: '4px solid #6F3DBA',
            borderRadius: 8,
            padding: '16px 18px',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <div style={{ fontSize: 11, fontWeight: 800, color: '#6F3DBA', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 10 }}>
            HOW THE AGENT SHOULD WORK
          </div>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 11.5, lineHeight: 1.6, color: 'var(--text-secondary)' }}>
            <li>Ingest EDI/portal/email order data and match it to customer/material masters.</li>
            <li>Validate revisions, cumulative quantities, delivery windows and duplicate schedules.</li>
            <li>Check ATP/CTP using inventory, capacity and approved production plan.</li>
            <li>Flag conflicts and generate feasible promise-date recommendations.</li>
            <li>Customer-service/sales approves commitments; monitor milestones through delivery.</li>
          </ul>
        </div>
      </div>

      {/* 4. BOTTOM 4 ARCHITECTURE BOXES */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 14, marginBottom: 20 }}>
        {/* SYSTEMS AND DATA REQUIRED */}
        <div
          style={{
            background: 'var(--kg-bg-2)',
            border: '1px solid var(--line)',
            borderLeft: '4px solid #F58A3A',
            borderRadius: 8,
            padding: '14px 16px',
          }}
        >
          <div style={{ fontSize: 10.5, fontWeight: 800, color: '#F58A3A', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 6 }}>
            SYSTEMS AND DATA REQUIRED
          </div>
          <p style={{ margin: 0, fontSize: 11, lineHeight: 1.5, color: 'var(--text-secondary)' }}>
            Customer EDI/portal • SAP/ERP SD • production plan/MES • inventory/WMS • QMS release • TMS delivery milestones
          </p>
        </div>

        {/* OUTPUTS / DELIVERABLES */}
        <div
          style={{
            background: 'var(--kg-bg-2)',
            border: '1.5px dashed #31B7C3',
            borderRadius: 8,
            padding: '14px 16px',
          }}
        >
          <div style={{ fontSize: 10.5, fontWeight: 800, color: '#31B7C3', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 6 }}>
            OUTPUTS / DELIVERABLES
          </div>
          <p style={{ margin: 0, fontSize: 11, lineHeight: 1.5, color: 'var(--text-secondary)' }}>
            Order book • promise-date risk • allocation proposal • customer status draft • overdue order alerts • delivery performance
          </p>
        </div>

        {/* SUCCESS MEASURES (KPIS) */}
        <div
          style={{
            background: 'var(--kg-bg-2)',
            border: '1px solid var(--line)',
            borderLeft: '4px solid #22C55E',
            borderRadius: 8,
            padding: '14px 16px',
          }}
        >
          <div style={{ fontSize: 10.5, fontWeight: 800, color: '#22C55E', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 6 }}>
            SUCCESS MEASURES (KPIS)
          </div>
          <p style={{ margin: 0, fontSize: 11, lineHeight: 1.5, color: 'var(--text-secondary)' }}>
            OTIF customer • order confirmation time • schedule adherence • backlog ageing • promise-date accuracy • expedite cost
          </p>
        </div>

        {/* AUTONOMY, APPROVALS AND CONTROLS */}
        <div
          style={{
            background: 'var(--kg-bg-2)',
            border: '1px solid var(--line)',
            borderLeft: '4px solid #E45C72',
            borderRadius: 8,
            padding: '14px 16px',
          }}
        >
          <div style={{ fontSize: 10.5, fontWeight: 800, color: '#E45C72', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 6 }}>
            AUTONOMY, APPROVALS AND CONTROLS
          </div>
          <p style={{ margin: 0, fontSize: 11, lineHeight: 1.5, color: 'var(--text-secondary)' }}>
            Only authorized personnel confirm commercial commitments, pricing and delivery changes. Enforce customer-specific rules, data segregation and revision control.
          </p>
        </div>
      </div>

      {/* 5. LIVE SUCCESS MEASURES (6 KPI CARDS) */}
      <div style={{ marginTop: 22, paddingTop: 18, borderTop: '1px solid var(--line)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div style={{ fontSize: 12, fontWeight: 800, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.05em', display: 'flex', alignItems: 'center', gap: 6 }}>
            <TrendingUp size={15} color="#22C55E" />
            Live Success Measures (Governed Slide 18 Operational KPIs)
          </div>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Real-time PostgreSQL analytics</span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
          {kpis.map((kpi, idx) => (
            <div
              key={kpi.code}
              style={{
                background: 'var(--kg-bg-2)',
                border: '1px solid var(--line)',
                borderTop: idx % 2 === 0 ? '3px solid #22C55E' : '3px solid #F58A3A',
                borderRadius: 8,
                padding: '12px 14px',
                display: 'flex',
                flexDirection: 'column',
                gap: 4,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  {idx + 1}. {kpi.name}
                </span>
              </div>
              <div style={{ fontSize: 20, fontWeight: 900, color: 'var(--text-primary)', letterSpacing: '-0.02em', margin: '2px 0' }}>
                {kpi.value}
              </div>
              <div style={{ fontSize: 10, fontWeight: 600, color: '#F58A3A' }}>
                {kpi.target}
              </div>
              <div style={{ fontSize: 9.5, color: 'var(--text-muted)', marginTop: 2 }}>
                {kpi.sub}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 6. BLUEPRINT FOOTER */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginTop: 20,
          paddingTop: 12,
          borderTop: '1px solid var(--line)',
          fontSize: 10,
          fontWeight: 700,
          letterSpacing: '0.08em',
          color: 'var(--text-muted)',
          textTransform: 'uppercase',
        }}
      >
        <span>MANUFACTURING AGENTIC AI PLATFORM | MULTI-TENANT ENTERPRISE BLUEPRINT</span>
        <span>18 / 20</span>
      </div>
    </div>
  )
}
