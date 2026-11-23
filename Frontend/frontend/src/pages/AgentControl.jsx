import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Shield,
  Bot,
  Play,
  Pause,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Cpu,
  Layers,
  Zap,
  RotateCcw,
  Gauge,
  Lock,
  Mail,
  UserCheck,
} from 'lucide-react'
import { agentsApi } from '../api/agents.api'
import { useAuth } from '../context/AuthContext'
import { PageLoader } from '../components/common/PageLoader'
import { ErrorState } from '../components/common/ErrorState'
import { formatDate } from '../utils/format'

export default function AgentControl() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'

  const [actionPending, setActionPending] = useState({})
  const [feedbackMsg, setFeedbackMsg] = useState('')

  const {
    data: overview,
    isLoading: loading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['admin-agents-overview'],
    queryFn: () => agentsApi.getAgentsOverview(),
    enabled: isAdmin,
    refetchInterval: 15000,
  })

  const { data: kpis } = useQuery({
    queryKey: ['agent-performance-kpis'],
    queryFn: () => agentsApi.getAgentPerformanceKpis(),
    enabled: isAdmin,
  })

  if (!isAdmin) {
    return (
      <div className="page-stack">
        <div className="card" style={{ padding: 40, textAlign: 'center', maxWidth: 500, margin: '60px auto' }}>
          <Lock size={44} color="#dc2626" style={{ margin: '0 auto 16px' }} />
          <h2 style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-primary)', margin: '0 0 8px' }}>
            Administrator Access Restricted
          </h2>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: 0 }}>
            The Autonomous Agent Control Page and system kill switch controls are restricted to users with the Administrator role.
          </p>
        </div>
      </div>
    )
  }

  if (loading) return <PageLoader />
  if (error || !overview) {
    return (
      <div className="page-stack">
        <ErrorState
          title="Failed to Load Agent Governance Overview"
          message={error?.response?.data?.detail || error?.message || 'Could not retrieve agent overview.'}
          onRetry={() => refetch()}
        />
      </div>
    )
  }

  const agents = (overview.agents || []).filter((a) => a.id !== 'policy-engine' && a.id !== 'approval-policy')
  const limits = overview.limits || {}
  const counts = overview.counts || {}

  const handlePause = async (agentId) => {
    const reason = window.prompt(`Enter reason for pausing ${agentId} (leave blank for default):`, '')
    if (reason === null) return
    try {
      setActionPending((p) => ({ ...p, [agentId]: true }))
      await agentsApi.pauseAgent(agentId, reason.trim() || 'Manual administrator kill switch')
      setFeedbackMsg(`Agent '${agentId}' has been PAUSED.`)
      setTimeout(() => setFeedbackMsg(''), 4000)
      await refetch()
    } catch (err) {
      alert(`Could not pause agent: ${err.response?.data?.detail || err.message}`)
    } finally {
      setActionPending((p) => ({ ...p, [agentId]: false }))
    }
  }

  const handleResume = async (agentId) => {
    try {
      setActionPending((p) => ({ ...p, [agentId]: true }))
      await agentsApi.resumeAgent(agentId)
      setFeedbackMsg(`Agent '${agentId}' has been RESUMED.`)
      setTimeout(() => setFeedbackMsg(''), 4000)
      await refetch()
    } catch (err) {
      alert(`Could not resume agent: ${err.response?.data?.detail || err.message}`)
    } finally {
      setActionPending((p) => ({ ...p, [agentId]: false }))
    }
  }

  return (
    <div className="page-stack" style={{ gap: 20 }}>
      {feedbackMsg && (
        <div style={{
          padding: '12px 18px',
          borderRadius: 8,
          background: 'rgba(34, 197, 94, 0.1)',
          border: '1px solid rgba(34, 197, 94, 0.3)',
          color: '#16a34a',
          fontSize: 13,
          fontWeight: 700
        }}>
          {feedbackMsg}
        </div>
      )}

      {/* METRIC SUMMARY STRIP */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 14 }}>
        <div className="card" style={{ padding: 18, background: 'var(--surface-hi)', border: '1px solid var(--line)', borderRadius: 12 }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Evaluated Assessments</span>
          <div style={{ fontSize: 22, fontWeight: 900, color: '#3b82f6', marginTop: 4 }}>{counts.assessments || 0}</div>
          <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Agent 2 7-dept evaluations</span>
        </div>

        <div className="card" style={{ padding: 18, background: 'var(--surface-hi)', border: '1px solid var(--line)', borderRadius: 12 }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Human Approval Policy</span>
          <div style={{ fontSize: 19, fontWeight: 900, color: '#3b82f6', marginTop: 4 }}>100% Mandatory</div>
          <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>All orders require human approval</span>
        </div>

        <div className="card" style={{ padding: 18, background: 'var(--surface-hi)', border: '1px solid var(--line)', borderRadius: 12 }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Risk Alerts</span>
          <div style={{ fontSize: 22, fontWeight: 900, color: '#ef4444', marginTop: 4 }}>{counts.alerts || 0}</div>
          <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Agent 3 surveillance alerts</span>
        </div>

        <div className="card" style={{ padding: 18, background: 'var(--surface-hi)', border: '1px solid var(--line)', borderRadius: 12 }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Corrective Actions</span>
          <div style={{ fontSize: 22, fontWeight: 900, color: '#f59e0b', marginTop: 4 }}>{counts.actions || 0}</div>
          <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Proposed &amp; executed actions</span>
        </div>

        <div className="card" style={{ padding: 18, background: 'var(--surface-hi)', border: '1px solid var(--line)', borderRadius: 12 }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Agent Escalations</span>
          <div style={{ fontSize: 22, fontWeight: 900, color: 'var(--brand-purple)', marginTop: 4 }}>{counts.escalations || 0}</div>
          <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>NEEDS_HUMAN safety escalations</span>
        </div>
      </div>

      {/* KPI TILES (REQUIREMENT 5) */}
      {kpis && (
        <div className="card" style={{ padding: 20, background: 'var(--surface-hi)', border: '1px solid var(--line)', borderRadius: 14 }}>
          <h3 style={{ margin: '0 0 14px', fontSize: 14, fontWeight: 800, textTransform: 'uppercase', color: 'var(--brand-purple)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <Gauge size={16} /> Commercial Approval Delivery Performance &amp; SLA
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16 }}>
            <div style={{ padding: 14, borderRadius: 10, background: 'var(--kg-bg-2)', border: '1px solid var(--line)' }}>
              <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>Commercial Policy Status</span>
              <div style={{ fontSize: 18, fontWeight: 900, color: '#16a34a', marginTop: 4 }}>
                100% Human Review
              </div>
              <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                Auto-approval removed; all orders require human review
              </span>
            </div>

            <div style={{ padding: 14, borderRadius: 10, background: 'var(--kg-bg-2)', border: '1px solid var(--line)' }}>
              <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>Human-Approved On-Time Rate</span>
              <div style={{ fontSize: 24, fontWeight: 900, color: '#3b82f6', marginTop: 4 }}>
                {kpis.human_approved_on_time_rate}%
              </div>
              <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                {kpis.human_approved_on_time} of {kpis.human_approved_total} delivered on-time
              </span>
            </div>

            <div style={{ padding: 14, borderRadius: 10, background: 'var(--kg-bg-2)', border: '1px solid var(--line)' }}>
              <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>Avg Alert-to-Resolution Time</span>
              <div style={{ fontSize: 24, fontWeight: 900, color: '#f59e0b', marginTop: 4 }}>
                {kpis.avg_alert_resolution_hours} hrs
              </div>
              <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                Across {kpis.total_resolved_alerts} resolved operational alerts
              </span>
            </div>
          </div>
        </div>
      )}

      {/* AGENT STATUS & CONTROL CARDS */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          <h3 style={{ margin: 0, fontSize: 15, fontWeight: 800, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Autonomous Agents Status &amp; Kill Switch
          </h3>
          <button
            type="button"
            onClick={() => refetch()}
            className="button button-secondary"
            style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, padding: '6px 12px' }}
          >
            <RotateCcw size={13} /> Refresh State
          </button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>
          {agents.map((agent) => {
            const isPaused = agent.status === 'PAUSED'
            const isRunning = agent.status === 'RUNNING'
            const isScheduled = agent.status === 'SCHEDULED' || (agent.id === 'agent3' && !isPaused && !isRunning)
            const isBusy = !!actionPending[agent.id]

            let badgeBg = 'rgba(34, 197, 94, 0.12)'
            let badgeColor = '#16a34a'
            let badgeBorder = 'rgba(34, 197, 94, 0.3)'
            let dotColor = '#16a34a'
            let badgeLabel = agent.status

            if (isPaused) {
              badgeBg = 'rgba(239, 68, 68, 0.12)'
              badgeColor = '#dc2626'
              badgeBorder = 'rgba(239, 68, 68, 0.3)'
              dotColor = '#dc2626'
              badgeLabel = 'PAUSED'
            } else if (isScheduled) {
              badgeBg = 'rgba(59, 130, 246, 0.12)'
              badgeColor = '#2563eb'
              badgeBorder = 'rgba(59, 130, 246, 0.3)'
              dotColor = '#2563eb'
              badgeLabel = 'SCHEDULED (24h)'
            } else if (isRunning) {
              badgeLabel = 'RUNNING'
            }

            return (
              <div
                key={agent.id}
                className="card"
                style={{
                  padding: 20,
                  background: 'var(--surface-hi)',
                  border: isPaused
                    ? '1px solid rgba(239, 68, 68, 0.4)'
                    : isScheduled
                    ? '1px solid rgba(59, 130, 246, 0.35)'
                    : '1px solid var(--line)',
                  borderRadius: 14,
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  gap: 16,
                  boxShadow: isPaused
                    ? '0 2px 10px rgba(239, 68, 68, 0.08)'
                    : isScheduled
                    ? '0 2px 10px rgba(59, 130, 246, 0.06)'
                    : '0 1px 4px rgba(0,0,0,0.02)',
                }}
              >
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10 }}>
                    <div>
                      <h4 style={{ margin: 0, fontSize: 15, fontWeight: 800, color: 'var(--text-primary)' }}>
                        {agent.name}
                      </h4>
                      <p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--text-secondary)' }}>
                        {agent.role}
                      </p>
                    </div>

                    <span
                      style={{
                        fontSize: 11,
                        fontWeight: 800,
                        padding: '4px 10px',
                        borderRadius: 12,
                        background: badgeBg,
                        color: badgeColor,
                        border: `1px solid ${badgeBorder}`,
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 6,
                        flexShrink: 0,
                      }}
                    >
                      <span
                        style={{
                          width: 7,
                          height: 7,
                          borderRadius: '50%',
                          background: dotColor,
                        }}
                        className={isRunning ? 'animate-pulse' : ''}
                      />
                      {badgeLabel}
                    </span>
                  </div>

                  <div style={{ marginTop: 14, padding: '10px 14px', borderRadius: 8, background: 'var(--kg-bg-2)', border: '1px solid var(--line)', fontSize: 12 }}>
                    {/* Execution Cadence / Schedule */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, paddingBottom: 6, borderBottom: '1px solid var(--line)' }}>
                      <span style={{ color: 'var(--text-muted)' }}>Execution frequency:</span>
                      <strong style={{ color: agent.id === 'agent3' ? '#2563eb' : 'var(--text-primary)', fontWeight: 700 }}>
                        {agent.id === 'agent3' ? 'Once every 24 hours (Daily)' : 'On-demand (User Triggered)'}
                      </strong>
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <span style={{ color: 'var(--text-muted)' }}>Last run:</span>
                      <strong style={{ color: 'var(--text-primary)' }}>
                        {agent.last_run
                          ? new Date(agent.last_run).toLocaleString()
                          : (agent.id === 'agent3' ? 'Daily cycle completed' : 'Ready on standby')}
                      </strong>
                    </div>

                    {agent.next_run && (
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, marginBottom: 4 }}>
                        <span style={{ color: 'var(--text-muted)' }}>Next scheduled run:</span>
                        <strong style={{ color: '#2563eb' }}>
                          {new Date(agent.next_run).toLocaleString()}
                        </strong>
                      </div>
                    )}

                    {agent.metrics && (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginTop: 8, paddingTop: 6, borderTop: '1px dashed var(--line)' }}>
                        {Object.entries(agent.metrics).map(([k, v]) => (
                          <div key={k} style={{ fontSize: 11 }}>
                            <span style={{ color: 'var(--text-muted)' }}>{k.replace(/_/g, ' ')}: </span>
                            <strong style={{ color: 'var(--brand-purple)' }}>{v}</strong>
                          </div>
                        ))}
                      </div>
                    )}

                    {isPaused && agent.details?.reason && (
                      <div style={{ marginTop: 8, padding: '6px 10px', borderRadius: 6, background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.2)', color: '#dc2626', fontSize: 11 }}>
                        <strong>Pause reason:</strong> {agent.details.reason}
                        {agent.details.paused_at && ` (${new Date(agent.details.paused_at).toLocaleTimeString()})`}
                      </div>
                    )}
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
                  {isPaused ? (
                    <button
                      type="button"
                      className="button button-primary"
                      onClick={() => handleResume(agent.id)}
                      disabled={isBusy}
                      style={{ fontSize: 12, padding: '7px 16px', background: '#16a34a', borderColor: '#16a34a', display: 'flex', alignItems: 'center', gap: 6 }}
                    >
                      <Play size={13} /> {isBusy ? 'Resuming...' : 'Resume Agent'}
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="button button-secondary"
                      onClick={() => handlePause(agent.id)}
                      disabled={isBusy}
                      style={{ fontSize: 12, padding: '7px 16px', color: '#dc2626', borderColor: 'rgba(239, 68, 68, 0.4)', display: 'flex', alignItems: 'center', gap: 6 }}
                    >
                      <Pause size={13} /> {isBusy ? 'Pausing...' : 'Pause Agent'}
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* CENTRAL GOVERNOR LIMITS CONFIGURATION CARD */}
      <div className="card" style={{ padding: 22, background: 'var(--surface-hi)', border: '1px solid var(--line)', borderRadius: 14 }}>
        <h3 style={{ margin: '0 0 8px', fontSize: 14, fontWeight: 800, textTransform: 'uppercase', color: 'var(--brand-purple)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <Gauge size={16} /> Central Autonomous Governor Limits
        </h3>
        <p style={{ margin: '0 0 16px', fontSize: 12, color: 'var(--text-secondary)' }}>
          System safety boundaries automatically pause an agent and alert administrators whenever limits are reached.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 14 }}>
          <div style={{ padding: 14, borderRadius: 10, background: 'var(--kg-bg-2)', border: '1px solid var(--line)' }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Hourly LLM Call Cap</span>
            <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-primary)', marginTop: 2 }}>
              {limits.max_llm_calls_per_hour} calls/hr
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
              Current usage: <strong>{limits.current_llm_calls_hour || 0}</strong> calls in last 60m
            </div>
          </div>

          <div style={{ padding: 14, borderRadius: 10, background: 'var(--kg-bg-2)', border: '1px solid var(--line)' }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Daily Auto-Actions Cap</span>
            <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-primary)', marginTop: 2 }}>
              {limits.max_auto_actions_per_day} actions/day
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
              Throttles autonomous expedites and carrier upgrades
            </div>
          </div>

          <div style={{ padding: 14, borderRadius: 10, background: 'var(--kg-bg-2)', border: '1px solid var(--line)' }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Max Cost Per Cycle</span>
            <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-primary)', marginTop: 2 }}>
              ${Number(limits.max_cost_per_cycle).toFixed(2)}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
              Hard ceiling for Agent 3 batch surveillance cycle
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
