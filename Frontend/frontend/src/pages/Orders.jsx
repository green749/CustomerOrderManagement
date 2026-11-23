import { useEffect, useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import {
  Download,
  Filter,
  PlusCircle,
  RotateCcw,
  Search,
  ArrowRight,
  TrendingUp,
  Package,
  Building2,
  Calendar,
  AlertTriangle,
} from 'lucide-react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ordersApi } from '../api/orders.api'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import { formatDate, formatINR, formatNumber, getErrorMessage } from '../utils/format'
import { OrdersTable } from '../components/orders/OrdersTable'
import { ErrorState } from '../components/common/ErrorState'
import { Input } from '../components/common/Input'
import { Select } from '../components/common/Select'
import { Button } from '../components/common/Button'
import { StatusBadge, RiskBadge } from '../components/common/StatusBadge'
import { CreateOrderIntakeModal } from '../components/orders/CreateOrderIntakeModal'

const PAGE_SIZE = 20
const csvValue = (value) => `"${String(value ?? '').replaceAll('"', '""')}"`

function getOrdersResponse(response) {
  if (!Array.isArray(response?.items) || typeof response?.total !== 'number' || typeof response?.total_pages !== 'number') {
    throw new Error('Orders response did not match the backend pagination schema.')
  }
  return { orders: response.items, total: response.total, totalPages: response.total_pages }
}

function getRiskCategory(order) {
  const risk = order?.risk
  if (typeof risk === 'object') {
    return String(risk.category ?? risk.risk_level ?? risk.risk ?? '').toUpperCase()
  }
  return String(risk ?? order?.risk_status ?? '').toUpperCase()
}

const initialParams = (params) => ({
  status: params.get('status') ?? '',
  customer_id: params.get('customer_id') ?? '',
  product_id: params.get('product_id') ?? '',
  priority: params.get('priority') ?? '',
  risk: params.get('risk') ?? '',
  release_status: params.get('release_status') ?? '',
  link_type: params.get('link_type') ?? '',
  start_date: params.get('start_date') ?? '',
  end_date: params.get('end_date') ?? '',
  sort_by: params.get('sort_by') ?? 'order_date',
  sort_order: params.get('sort_order') ?? 'desc',
})

export default function Orders() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [urlParams, setUrlParams] = useSearchParams()
  const [filters, setFilters] = useState(() => initialParams(urlParams))
  const [query, setQuery] = useState(urlParams.get('q') ?? '')
  const [page, setPage] = useState(1)
  const [isIntakeOpen, setIsIntakeOpen] = useState(false)
  const debouncedQuery = useDebouncedValue(query)

  useEffect(() => {
    const currentQ = urlParams.get('q') || ''
    if (currentQ !== debouncedQuery) {
      setUrlParams((current) => {
        const next = new URLSearchParams(current)
        if (debouncedQuery) next.set('q', debouncedQuery)
        else next.delete('q')
        return next
      })
    }
  }, [debouncedQuery, urlParams, setUrlParams])

  // Sync filters from URL parameters if navigated from external link (e.g. Architecture heatmap)
  useEffect(() => {
    const nextParams = initialParams(urlParams)
    setFilters((prev) => {
      const isDiff = Object.keys(nextParams).some((k) => nextParams[k] !== prev[k])
      return isDiff ? nextParams : prev
    })
  }, [urlParams])

  const {
    data: result = { orders: [], total: 0, totalPages: 0 },
    isLoading,
    isFetching,
    error: queryError,
    refetch,
  } = useQuery({
    queryKey: ['orders', filters, debouncedQuery, page],
    queryFn: async ({ signal }) => {
      const { risk, release_status, link_type, ...apiFilters } = filters
      const cleanSearch = debouncedQuery.trim() || undefined
      const response = await ordersApi.list({ ...apiFilters, search: cleanSearch, page, page_size: PAGE_SIZE }, { signal })
      return getOrdersResponse(response)
    },
    staleTime: 30 * 1000,
    placeholderData: (previousData) => previousData,
    refetchOnWindowFocus: false,
  })

  const loading = isLoading || isFetching
  const error = queryError ? getErrorMessage(queryError, 'Could not load orders.') : ''

  // Reset page to 1 whenever debouncedQuery changes
  useEffect(() => {
    setPage(1)
  }, [debouncedQuery])

  const pageOrders = useMemo(() => {
    const riskFilter = filters.risk
    return result.orders.filter((order) => (
      (!riskFilter || getRiskCategory(order) === riskFilter)
      && (!filters.release_status || order.release_status === filters.release_status)
      && (!filters.link_type || order.link_type === filters.link_type)
    ))
  }, [filters.risk, filters.release_status, filters.link_type, result.orders])

  const updateFilter = (key, value) => {
    setPage(1)
    setFilters((current) => ({ ...current, [key]: value }))
    setUrlParams((current) => {
      const next = new URLSearchParams(current)
      if (value) next.set(key, value)
      else next.delete(key)
      return next
    })
  }

  const resetFilters = () => {
    setFilters({ status: '', customer_id: '', product_id: '', priority: '', risk: '', release_status: '', link_type: '', start_date: '', end_date: '', sort_by: 'order_date', sort_order: 'desc' })
    setQuery('')
    setUrlParams({})
    setPage(1)
  }

  const downloadCurrentPage = () => {
    const columns = ['Order ID', 'Customer', 'Product', 'Order date', 'Quantity', 'Status', 'Priority', 'Risk level']
    const rows = pageOrders.map((order) => [
      order.customer_order_id ?? order.id,
      order.customer_name ?? order.customer_id,
      order.product_id ?? '',
      order.order_date ?? order.date,
      order.order_qty ?? order.quantity,
      order.order_status ?? order.status,
      order.priority,
      typeof order.risk === 'object' ? order.risk?.risk_level : order.risk,
    ])
    const content = [columns, ...rows].map((row) => row.map(csvValue).join(',')).join('\r\n')
    const url = URL.createObjectURL(new Blob([content], { type: 'text/csv;charset=utf-8' }))
    const link = document.createElement('a')
    link.href = url
    link.download = `manufacturing-orders-page-${page}.csv`
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="page-stack orders-page">
      {error && <ErrorState title="Orders unavailable" message={error} onRetry={() => refetch()} />}

      {/* CUSTOMER PORTFOLIO DOSSIER BANNER (WHEN FILTERED BY CUSTOMER) */}
      {filters.customer_id && (
        <div
          style={{
            background: 'linear-gradient(135deg, #f5f3ff, #ede9fe)',
            border: '1.5px solid #ddd6fe',
            borderRadius: 12,
            padding: '12px 18px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: 12,
            boxShadow: '0 2px 8px rgba(111, 61, 186, 0.08)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div
              style={{
                width: 38,
                height: 38,
                borderRadius: 9,
                background: '#6f3dba',
                color: '#ffffff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Building2 size={20} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <strong style={{ fontSize: 14, color: '#3b0764' }}>
                  {filters.customer_id === 'CUS-001'
                    ? 'Retailer North'
                    : filters.customer_id === 'CUS-002'
                    ? 'MobileMart'
                    : filters.customer_id === 'CUS-003'
                    ? 'Digital Bazaar'
                    : filters.customer_id === 'CUS-004'
                    ? 'Global Devices'
                    : filters.customer_id}
                </strong>
                <span
                  style={{
                    fontSize: 10.5,
                    fontWeight: 800,
                    fontFamily: 'monospace',
                    padding: '2px 7px',
                    borderRadius: 5,
                    background: '#ffffff',
                    color: '#6f3dba',
                    border: '1px solid #ddd6fe',
                  }}
                >
                  {filters.customer_id}
                </span>
                <span
                  style={{
                    fontSize: 10.5,
                    fontWeight: 700,
                    padding: '2px 8px',
                    borderRadius: 12,
                    background: '#10b981',
                    color: '#ffffff',
                  }}
                >
                  Neon PostgreSQL 16 · {result.total.toLocaleString()} Orders
                </span>
              </div>
              <div style={{ fontSize: 11, color: '#6b21a8', marginTop: 2 }}>
                Live star schema records: Click any row below for 7-dept audit or open the full customer dossier.
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button
              type="button"
              onClick={() => navigate(`/customers/${filters.customer_id}`)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
                background: '#6f3dba',
                color: '#ffffff',
                border: 'none',
                borderRadius: 8,
                padding: '7px 14px',
                fontSize: 12,
                fontWeight: 700,
                cursor: 'pointer',
                boxShadow: '0 2px 6px rgba(111, 61, 186, 0.3)',
              }}
            >
              Open Customer Dossier <ArrowRight size={13} />
            </button>
            <button
              type="button"
              onClick={() => updateFilter('customer_id', '')}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                background: '#ffffff',
                color: '#475569',
                border: '1px solid #cbd5e1',
                borderRadius: 8,
                padding: '7px 12px',
                fontSize: 11.5,
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              View All Customers
            </button>
          </div>
        </div>
      )}

      {/* A. ORDER FILTERS (NO OUTER CARD OUTLINE, ZERO NEGATIVE SPACE) */}
      <div className="orders-filters-container" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div className="filter-grid" style={{ margin: 0 }}>
          <label className="filter-search">
            <Search size={16} />
            <Input
              bare
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Filter by Order ID (CO-XXXX), customer, or product model"
              aria-label="Search orders"
            />
          </label>
          <Select label="Order Lifecycle Status" value={filters.status} onChange={(event) => updateFilter('status', event.target.value)}>
            <option value="">All Lifecycle Stages</option>
            <option value="OPEN">Open (Order Intake)</option>
            <option value="HUMAN_APPROVAL">Human Approval Pending</option>
            <option value="CONFIRMED">Confirmed (Baseline Committed)</option>
            <option value="IN_PRODUCTION">In Production (MES Active)</option>
            <option value="PARTIALLY_SHIPPED">Partially Shipped</option>
            <option value="DELIVERED">Delivered &amp; Closed</option>
            <option value="CANCELLED">Cancelled</option>
          </Select>
          <Select label="Customer Account" value={filters.customer_id} onChange={(event) => updateFilter('customer_id', event.target.value)}>
            <option value="">All Customer Accounts</option>
            <option value="CUS-001">Retailer North (CUS-001)</option>
            <option value="CUS-002">MobileMart (CUS-002)</option>
            <option value="CUS-003">Digital Bazaar (CUS-003)</option>
            <option value="CUS-004">Global Devices (CUS-004)</option>
          </Select>
          <Input label="Product Model" value={filters.product_id} onChange={(event) => updateFilter('product_id', event.target.value)} placeholder="e.g. SPH-A15-128" />
          <Select label="Priority" value={filters.priority} onChange={(event) => updateFilter('priority', event.target.value)}>
            <option value="">All Priorities</option>
            <option value="HIGH">HIGH Priority</option>
            <option value="MEDIUM">MEDIUM Priority</option>
            <option value="LOW">LOW Priority</option>
          </Select>
          <Select label="Delivery Risk" value={filters.risk} onChange={(event) => updateFilter('risk', event.target.value)}>
            <option value="">All Risk States</option>
            <option value="ACTUAL_DELAY">Actual Delay</option>
            <option value="POTENTIAL_DELAY">Potential Delay</option>
            <option value="ON_SCHEDULE">On Schedule</option>
            <option value="UNKNOWN_RISK">Unknown Risk</option>
          </Select>
          <Select label="Quality Release" value={filters.release_status} onChange={(event) => updateFilter('release_status', event.target.value)}>
            <option value="">All Quality Releases</option>
            <option value="RELEASED">Released for Dispatch</option>
            <option value="ON_HOLD">Quality Hold Active</option>
            <option value="REWORK">Rework Required</option>
            <option value="NOT_INSPECTED">Inspection Pending</option>
          </Select>
          <Select label="Production Link" value={filters.link_type} onChange={(event) => updateFilter('link_type', event.target.value)}>
            <option value="">All Link Types</option>
            <option value="DIRECT">Direct Work Order</option>
            <option value="INFERRED">Inferred Line Association</option>
            <option value="UNLINKED">Unlinked Capacity</option>
          </Select>
          <Input label="Order Date From" type="date" value={filters.start_date} onChange={(event) => updateFilter('start_date', event.target.value)} />
          <Input label="Order Date To" type="date" value={filters.end_date} onChange={(event) => updateFilter('end_date', event.target.value)} />
          <Select label="Sort Order" value={`${filters.sort_by}:${filters.sort_order}`} onChange={(event) => { const [sort_by, sort_order] = event.target.value.split(':'); setFilters((current) => ({ ...current, sort_by, sort_order })) }}>
            <option value="order_date:desc">Order Date: Newest First</option>
            <option value="order_date:asc">Order Date: Oldest First</option>
            <option value="order_qty:desc">Quantity: High to Low</option>
            <option value="order_qty:asc">Quantity: Low to High</option>
          </Select>

          {/* 12th SLOT: RESET FILTERS & NEW ORDER ACTIONS (MOVED FROM TOP TO FILL EMPTY GRID SPACE) */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'flex-end',
              gap: 8,
              height: 34,
              alignSelf: 'end',
            }}
          >
            <button
              type="button"
              className="text-button"
              onClick={resetFilters}
              style={{
                fontSize: 11.5,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
                background: 'var(--surface-hi)',
                border: '1px solid var(--line)',
                color: 'var(--text-muted)',
                cursor: 'pointer',
                padding: '0 12px',
                borderRadius: 6,
                height: 34,
                fontWeight: 600,
                whiteSpace: 'nowrap',
                transition: 'all 0.15s ease',
              }}
              title="Reset all search queries and filters"
            >
              <RotateCcw size={12} /> Reset filters
            </button>
            <button
              type="button"
              className="button button-primary glow-orange"
              onClick={() => navigate('/orders/new')}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                fontWeight: 700,
                padding: '0 15px',
                fontSize: 12,
                background: 'linear-gradient(135deg, var(--brand-orange, #FF8A24), #ea580c)',
                color: 'white',
                border: 'none',
                borderRadius: 6,
                boxShadow: '0 2px 6px rgba(255, 138, 36, 0.28)',
                cursor: 'pointer',
                height: 34,
                whiteSpace: 'nowrap',
                transition: 'all 0.15s ease',
              }}
              title="Create a new customer order intake with Agent 2 feasibility assessment"
            >
              <PlusCircle size={14} /> New Order
            </button>
          </div>
        </div>

        {debouncedQuery && (
          <p className="page-search-note" style={{ color: 'var(--mfg-text-muted)', fontSize: 11, margin: '4px 0 0' }}>
            Searching database records for "{debouncedQuery}". Found {result.total.toLocaleString()} matching {result.total === 1 ? 'order' : 'orders'}.
          </p>
        )}
      </div>

      {/* B. ONLY FOR THE TABLE THE OUTLINE SHOULD BE THERE */}
      {!error && (
        <div
          className="orders-table-card"
          style={{
            background: 'var(--surface-hi)',
            border: '1px solid var(--line)',
            borderRadius: 12,
            boxShadow: 'var(--shadow-card)',
            overflow: 'hidden',
          }}
        >
          <OrdersTable
            orders={pageOrders}
            page={page}
            totalPages={result.totalPages}
            total={result.total}
            onPageChange={setPage}
            loading={loading}
          />
        </div>
      )}

      {/* D. NEW ORDER INTAKE MODAL */}
      <CreateOrderIntakeModal
        isOpen={isIntakeOpen}
        onClose={() => setIsIntakeOpen(false)}
        onAssessmentCreated={(assessment) => {
          queryClient.invalidateQueries({ queryKey: ['assessments-list'] })
          queryClient.invalidateQueries({ queryKey: ['orders'] })
          refetch()
          navigate(`/assessments?id=${assessment.assessment_id}&autoRun=true`)
        }}
        onCreated={() => {
          queryClient.invalidateQueries({ queryKey: ['orders'] })
          refetch()
        }}
      />
    </div>
  )
}
