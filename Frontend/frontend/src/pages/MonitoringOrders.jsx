import { useState, useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowLeft,
  Eye,
  Search,
  Filter,
  ArrowUpRight,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  Mail,
  Play,
  Package,
} from 'lucide-react'
import { agentsApi } from '../api/agents.api'
import { formatDate, formatNumber } from '../utils/format'
import { PageLoader } from '../components/common/PageLoader'

export default function MonitoringOrders() {
  const navigate = useNavigate()
  const [recordSearch, setRecordSearch] = useState('')
  const [recordTab, setRecordTab] = useState('ALL') // 'ALL' | 'ACTIVE' | 'RISKS' | 'CLEAR' | 'DELIVERED'
  const [recordPage, setRecordPage] = useState(1)
  const RECORDS_PER_PAGE = 8

  // Fetch monitoring records from Agent 3
  const {
    data: records = [],
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ['monitoringRecords'],
    queryFn: async () => {
      const res = await agentsApi.listMonitoringRecords({ limit: 200 })
      return Array.isArray(res) ? res : []
    },
    refetchInterval: 15000,
  })

  // Summary counts
  const activeRecordsCount = useMemo(() => records.filter((r) => r.status === 'ACTIVE').length, [records])
  const riskyRecordsCount = useMemo(() => records.filter((r) => (r.open_alerts_count || 0) > 0).length, [records])
  const clearRecordsCount = useMemo(
    () => records.filter((r) => r.status === 'ACTIVE' && (!r.open_alerts_count || r.open_alerts_count === 0)).length,
    [records]
  )
  const deliveredRecordsCount = useMemo(() => records.filter((r) => r.status === 'DELIVERED').length, [records])

  // Filtered records
  const filteredRecords = useMemo(() => {
    return records.filter((r) => {
      // Tab filter
      if (recordTab === 'ACTIVE' && r.status !== 'ACTIVE') return false
      if (recordTab === 'DELIVERED' && r.status !== 'DELIVERED') return false
      if (recordTab === 'RISKS' && ((r.open_alerts_count || 0) === 0 || r.status !== 'ACTIVE')) return false
      if (recordTab === 'CLEAR' && ((r.open_alerts_count || 0) > 0 || r.status !== 'ACTIVE')) return false

      // Search filter
      if (recordSearch.trim()) {
        const q = recordSearch.toLowerCase().trim()
        const matchId = (r.customer_order_id || '').toLowerCase().includes(q)
        const matchCust = (r.customer_name || '').toLowerCase().includes(q)
        const matchProd = (r.product_name || '').toLowerCase().includes(q)
        if (!matchId && !matchCust && !matchProd) return false
      }
      return true
    })
  }, [records, recordTab, recordSearch])

  const totalRecordPages = Math.max(1, Math.ceil(filteredRecords.length / RECORDS_PER_PAGE))
  const paginatedRecords = useMemo(() => {
    const start = (recordPage - 1) * RECORDS_PER_PAGE
    return filteredRecords.slice(start, start + RECORDS_PER_PAGE)
  }, [filteredRecords, recordPage])

  if (isLoading) return <PageLoader />

  return (
    <div className="page-stack">
      {/* PAGE HEADER */}
      <div
        className="page-intro"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 16,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <button
            type="button"
            onClick={() => navigate('/monitoring')}
            className="button button-secondary"
            title="Return to Multi-Department Surveillance Radar"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              padding: '8px 14px',
              fontSize: 12,
              fontWeight: 600,
              borderRadius: 8,
              background: 'var(--surface-hi)',
              border: '1px solid var(--line)',
              color: 'var(--text-primary)',
              cursor: 'pointer',
              boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
              transition: 'all 0.15s ease',
            }}
          >
            <ArrowLeft size={14} /> Back to Surveillance
          </button>
        </div>

        {/* TOP ACTION BUTTONS */}
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={() => navigate('/monitoring')}
            className="button button-primary"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 7,
              padding: '8px 16px',
              fontSize: 12,
              fontWeight: 700,
              borderRadius: 8,
              background: 'linear-gradient(135deg, var(--brand-purple), var(--dr-purple))',
              color: 'white',
              border: 'none',
              cursor: 'pointer',
              boxShadow: '0 2px 8px rgba(111, 61, 186, 0.25)',
            }}
          >
            <Play size={13} fill="white" />
            <span>Run Surveillance</span>
          </button>

          <button
            type="button"
            onClick={() => navigate('/monitoring/outbox')}
            className="button button-secondary"
            title="Open Notification Outbox"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 7,
              padding: '8px 14px',
              fontSize: 12,
              fontWeight: 600,
              borderRadius: 8,
              background: 'var(--surface-hi)',
              border: '1px solid var(--line)',
              color: 'var(--text-primary)',
              cursor: 'pointer',
              boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
            }}
          >
            <Mail size={14} style={{ color: 'var(--brand-purple)' }} />
            <span>Outbox</span>
          </button>
        </div>
      </div>

      {/* ORDERS UNDER ACTIVE MONITORING (AGENT 3 SURVEILLANCE STAGE) */}
      <div
        id="monitored-orders-section"
        className="card"
        style={{
          padding: 22,
          background: 'var(--surface-hi)',
          border: '1px solid var(--line)',
          borderRadius: 14,
          boxShadow: '0 2px 8px rgba(0,0,0,0.02)',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            marginBottom: 16,
            flexWrap: 'wrap',
            gap: 14,
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: 8,
                  background: 'rgba(111, 61, 186, 0.12)',
                  color: 'var(--brand-purple)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Eye size={18} />
              </span>
              <div>
                <h3
                  style={{
                    fontSize: 16,
                    fontWeight: 800,
                    margin: 0,
                    color: 'var(--text-primary)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    letterSpacing: '-0.01em',
                  }}
                >
                  Orders in Monitoring Stage
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      padding: '2px 8px',
                      borderRadius: 12,
                      background: 'rgba(34, 197, 94, 0.12)',
                      color: '#16a34a',
                      border: '1px solid rgba(34, 197, 94, 0.25)',
                    }}
                  >
                    {activeRecordsCount} ACTIVE SURVEILLANCE
                  </span>
                </h3>
                <p style={{ margin: '3px 0 0', fontSize: 12, color: 'var(--text-secondary)' }}>
                  Active multi-department surveillance over confirmed customer commitments with automated risk alerting.
                </p>
              </div>
            </div>
          </div>

          {/* Search Monitored Orders */}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <div style={{ position: 'relative' }}>
              <Search
                size={14}
                style={{ position: 'absolute', left: 10, top: 10, color: 'var(--text-muted)' }}
              />
              <input
                type="text"
                placeholder="Search monitored orders..."
                value={recordSearch}
                onChange={(e) => {
                  setRecordSearch(e.target.value)
                  setRecordPage(1)
                }}
                style={{
                  width: 240,
                  padding: '7px 10px 7px 30px',
                  borderRadius: 6,
                  border: '1px solid var(--line)',
                  background: 'var(--kg-bg-2)',
                  color: 'var(--text-primary)',
                  fontSize: 12,
                  outline: 'none',
                }}
              />
              {recordSearch && (
                <button
                  type="button"
                  onClick={() => setRecordSearch('')}
                  style={{
                    position: 'absolute',
                    right: 8,
                    top: 8,
                    border: 'none',
                    background: 'transparent',
                    cursor: 'pointer',
                    color: 'var(--text-muted)',
                    fontSize: 11,
                  }}
                >
                  ✕
                </button>
              )}
            </div>
            {recordSearch && (
              <button
                type="button"
                className="button button-secondary"
                onClick={() => setRecordSearch('')}
                style={{ fontSize: 11, padding: '6px 12px', display: 'flex', alignItems: 'center', gap: 4 }}
              >
                <RotateCcw size={12} /> Clear Filter
              </button>
            )}
          </div>
        </div>

        {/* Filter Pills */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 14, overflowX: 'auto', paddingBottom: 4 }}>
          {[
            { id: 'ALL', label: `All Monitored (${records.length})` },
            { id: 'ACTIVE', label: `Active (${activeRecordsCount})` },
            { id: 'RISKS', label: `Open Risks (${riskyRecordsCount})` },
            { id: 'CLEAR', label: `All Clear (${clearRecordsCount})` },
            { id: 'DELIVERED', label: `Delivered (${deliveredRecordsCount})` },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => {
                setRecordTab(tab.id)
                setRecordPage(1)
              }}
              style={{
                padding: '5px 12px',
                borderRadius: 20,
                fontSize: 12,
                fontWeight: recordTab === tab.id ? 700 : 500,
                border: '1px solid',
                borderColor: recordTab === tab.id ? 'var(--brand-purple)' : 'var(--line)',
                background: recordTab === tab.id ? 'var(--brand-purple-soft)' : 'var(--kg-bg-2)',
                color: recordTab === tab.id ? 'var(--brand-purple)' : 'var(--text-secondary)',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                transition: 'all 0.15s ease',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Monitored Orders Table */}
        {filteredRecords.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
            No monitored orders match your filter.
          </div>
        ) : (
          <div className="table-scroll" style={{ overflowX: 'auto', overflowY: 'auto', width: '100%', border: 'none', borderRadius: 0, scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr
                  style={{
                    borderBottom: '1px solid var(--line)',
                    textAlign: 'left',
                    color: 'var(--text-muted)',
                    fontSize: 11,
                    textTransform: 'uppercase',
                    letterSpacing: '0.04em',
                  }}
                >
                  <th style={{ padding: '10px 12px' }}>Order ID</th>
                  <th style={{ padding: '10px 12px' }}>Customer &amp; Product</th>
                  <th style={{ padding: '10px 12px' }}>Committed Delivery</th>
                  <th style={{ padding: '10px 12px' }}>Surveillance Status</th>
                  <th style={{ padding: '10px 12px' }}>Risk Health</th>
                  <th style={{ padding: '10px 12px' }}>Last Audit</th>
                  <th style={{ padding: '10px 12px', textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {paginatedRecords.map((r) => {
                  const hasRisks = (r.open_alerts_count || 0) > 0

                  return (
                    <tr
                      key={r.id}
                      style={{
                        borderBottom: '1px solid var(--line)',
                        transition: 'background 0.15s ease',
                      }}
                    >
                      <td style={{ padding: '12px' }}>
                        <Link
                          to={`/orders/${encodeURIComponent(r.customer_order_id)}`}
                          style={{
                            fontWeight: 700,
                            color: 'var(--brand-purple)',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 4,
                            textDecoration: 'none',
                          }}
                        >
                          {r.customer_order_id}
                          <ArrowUpRight size={13} />
                        </Link>
                      </td>
                      <td style={{ padding: '12px' }}>
                        <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                          {r.customer_name || 'Enterprise Customer'}
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                          {r.product_name || 'Smartphone Product'}{' '}
                          {r.order_qty ? `· ${formatNumber(r.order_qty)} units` : ''}
                        </div>
                      </td>
                      <td style={{ padding: '12px', fontWeight: 600, color: 'var(--text-primary)' }}>
                        {formatDate(r.approved_delivery_date)}
                      </td>
                      <td style={{ padding: '12px' }}>
                        {r.status === 'ACTIVE' ? (
                          <span
                            className="mfg-badge mfg-badge-ready"
                            style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 10 }}
                          >
                            <span
                              style={{
                                width: 6,
                                height: 6,
                                borderRadius: '50%',
                                background: '#22c55e',
                                display: 'inline-block',
                              }}
                            />
                            ACTIVE SURVEILLANCE
                          </span>
                        ) : (
                          <span className="mfg-badge mfg-badge-neutral" style={{ fontSize: 10 }}>
                            DELIVERED &amp; CLOSED
                          </span>
                        )}
                      </td>
                      <td style={{ padding: '12px' }}>
                        {hasRisks ? (
                          <button
                            type="button"
                            onClick={() =>
                              navigate(`/monitoring?orderId=${encodeURIComponent(r.customer_order_id)}`)
                            }
                            style={{
                              border: 'none',
                              background: 'transparent',
                              cursor: 'pointer',
                              padding: 0,
                            }}
                            title="Click to view alerts for this order in Surveillance Radar"
                          >
                            <span
                              className="mfg-badge mfg-badge-warning"
                              style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 10 }}
                            >
                              <AlertTriangle size={11} /> {r.open_alerts_count} Open Risk
                              {r.open_alerts_count > 1 ? 's' : ''}
                            </span>
                          </button>
                        ) : (
                          <span
                            className="mfg-badge mfg-badge-ready"
                            style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 10 }}
                          >
                            <CheckCircle2 size={11} /> All Clear
                          </span>
                        )}
                      </td>
                      <td style={{ padding: '12px', fontSize: 11, color: 'var(--text-muted)' }}>
                        {formatDate(r.last_checked_at || r.started_at)}
                      </td>
                      <td style={{ padding: '12px', textAlign: 'right' }}>
                        <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end', alignItems: 'center' }}>
                          <button
                            type="button"
                            className="button button-secondary"
                            onClick={() =>
                              navigate(`/monitoring?orderId=${encodeURIComponent(r.customer_order_id)}`)
                            }
                            style={{
                              fontSize: 11,
                              padding: '4px 8px',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: 4,
                            }}
                            title="Filter risks for this order in Surveillance view"
                          >
                            <Filter size={11} /> Filter Risks
                          </button>
                          <Link
                            to={`/orders/${encodeURIComponent(r.customer_order_id)}`}
                            className="button button-secondary"
                            style={{
                              fontSize: 11,
                              padding: '4px 8px',
                              textDecoration: 'none',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: 3,
                            }}
                          >
                            View Order <ExternalLink size={11} />
                          </Link>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>

            {/* Pagination Controls */}
            {totalRecordPages > 1 && (
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginTop: 14,
                  paddingTop: 10,
                  borderTop: '1px solid var(--line)',
                  fontSize: 11,
                  color: 'var(--text-muted)',
                }}
              >
                <span>
                  Showing {(recordPage - 1) * RECORDS_PER_PAGE + 1}–
                  {Math.min(recordPage * RECORDS_PER_PAGE, filteredRecords.length)} of {filteredRecords.length}{' '}
                  monitored orders
                </span>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <button
                    type="button"
                    disabled={recordPage <= 1}
                    onClick={() => setRecordPage((p) => Math.max(1, p - 1))}
                    className="button button-secondary"
                    style={{ padding: '4px 8px', fontSize: 11 }}
                  >
                    <ChevronLeft size={13} /> Prev
                  </button>
                  <span style={{ fontWeight: 700, color: 'var(--text-primary)', padding: '0 4px' }}>
                    Page {recordPage} of {totalRecordPages}
                  </span>
                  <button
                    type="button"
                    disabled={recordPage >= totalRecordPages}
                    onClick={() => setRecordPage((p) => Math.min(totalRecordPages, p + 1))}
                    className="button button-secondary"
                    style={{ padding: '4px 8px', fontSize: 11 }}
                  >
                    Next <ChevronRight size={13} />
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
