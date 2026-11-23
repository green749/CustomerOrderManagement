import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowLeft,
  Building2,
  Package,
  Clock,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  Truck,
  RotateCcw,
  Search,
  PlusCircle,
  Database,
  ExternalLink,
  Layers,
  ArrowUpRight,
  TrendingUp,
} from 'lucide-react'
import { customersApi } from '../api/customers.api'
import { ordersApi } from '../api/orders.api'
import { OrdersTable } from '../components/orders/OrdersTable'
import { PageLoader } from '../components/common/PageLoader'
import { ErrorState } from '../components/common/ErrorState'
import { Input } from '../components/common/Input'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import { formatNumber } from '../utils/format'

const CUSTOMER_THEMES = {
  'CUS-001': { color: '#6f3dba', bgLight: '#f5f3ff', border: '#ddd6fe', badge: '#4338ca' },
  'CUS-002': { color: '#0284c7', bgLight: '#f0f9ff', border: '#bae6fd', badge: '#0369a1' },
  'CUS-003': { color: '#d97706', bgLight: '#fffbeb', border: '#fde68a', badge: '#b45309' },
  'CUS-004': { color: '#059669', bgLight: '#ecfdf5', border: '#a7f3d0', badge: '#047857' },
}

const PAGE_SIZE = 20

function getOrdersResponse(response) {
  if (!Array.isArray(response?.items) || typeof response?.total !== 'number' || typeof response?.total_pages !== 'number') {
    return { orders: [], total: 0, totalPages: 0 }
  }
  return { orders: response.items, total: response.total, totalPages: response.total_pages }
}

export default function CustomerDetails() {
  const { customerId } = useParams()
  const navigate = useNavigate()

  const [statusFilter, setStatusFilter] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [page, setPage] = useState(1)

  const debouncedQuery = useDebouncedValue(searchQuery)

  useEffect(() => {
    setPage(1)
  }, [debouncedQuery, statusFilter])

  const theme = CUSTOMER_THEMES[customerId] || {
    color: '#4f46e5',
    bgLight: '#f8fafc',
    border: '#e2e8f0',
    badge: '#3730a3',
  }

  // 1. Fetch Customer Detail from PostgreSQL 16
  const {
    data: customer,
    isLoading: loadingCustomer,
    error: customerError,
    refetch: refetchCustomer,
  } = useQuery({
    queryKey: ['customer-detail', customerId],
    queryFn: () => customersApi.getById(customerId),
    enabled: Boolean(customerId),
    staleTime: 60 * 1000,
  })

  // 2. Fetch Orders for this Customer from PostgreSQL 16
  const {
    data: ordersResult = { orders: [], total: 0, totalPages: 0 },
    isLoading: loadingOrders,
    isFetching: fetchingOrders,
    error: ordersError,
    refetch: refetchOrders,
  } = useQuery({
    queryKey: ['customer-orders', customerId, statusFilter, debouncedQuery, page],
    queryFn: async ({ signal }) => {
      const cleanSearch = debouncedQuery.trim() || undefined
      const cleanStatus = statusFilter || undefined
      const response = await ordersApi.list(
        {
          customer_id: customerId,
          status: cleanStatus,
          search: cleanSearch,
          page,
          page_size: PAGE_SIZE,
        },
        { signal }
      )
      return getOrdersResponse(response)
    },
    enabled: Boolean(customerId),
    staleTime: 30 * 1000,
    placeholderData: (previousData) => previousData,
  })

  if (loadingCustomer && !customer) {
    return <PageLoader message="Loading customer account details from Neon PostgreSQL 16..." />
  }

  if (customerError) {
    return (
      <div className="page-stack">
        <ErrorState
          title="Customer Not Found"
          message={`Unable to load details for account ${customerId} from PostgreSQL store.`}
          onRetry={refetchCustomer}
        />
        <button
          type="button"
          className="button button-outline"
          onClick={() => navigate('/architecture')}
          style={{ width: 'fit-content' }}
        >
          ← Return to Architecture Diagram
        </button>
      </div>
    )
  }

  const statusCounts = customer?.status_counts || {}
  const inProdCount = statusCounts.IN_PRODUCTION || 0
  const approvalCount = statusCounts.HUMAN_APPROVAL || 0
  const openCount = statusCounts.OPEN || 0
  const confirmedCount = statusCounts.CONFIRMED || 0
  const deliveredCount = statusCounts.DELIVERED || 0
  const shippedCount = statusCounts.PARTIALLY_SHIPPED || 0
  const totalOrders = customer?.total_orders || ordersResult.total || 0

  const STAGE_TABS = [
    { id: '', label: 'All Orders', count: totalOrders },
    { id: 'HUMAN_APPROVAL', label: 'Human Approval', count: approvalCount, color: '#f59e0b' },
    { id: 'IN_PRODUCTION', label: 'In Production (MES)', count: inProdCount, color: '#3b82f6' },
    { id: 'OPEN', label: 'Open Intake', count: openCount, color: '#8b5cf6' },
    { id: 'CONFIRMED', label: 'Confirmed', count: confirmedCount, color: '#10b981' },
    { id: 'PARTIALLY_SHIPPED', label: 'Partially Shipped', count: shippedCount, color: '#06b6d4' },
    { id: 'DELIVERED', label: 'Delivered', count: deliveredCount, color: '#16a34a' },
  ]

  return (
    <div className="page-stack customer-details-page" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* 1. TOP BREADCRUMB & ACTION ROW */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button
            type="button"
            onClick={() => navigate('/architecture')}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              background: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: 8,
              padding: '6px 12px',
              fontSize: 12,
              fontWeight: 700,
              color: '#475569',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            <ArrowLeft size={14} /> Back to Architecture
          </button>
          <span style={{ color: '#cbd5e1' }}>/</span>
          <span style={{ fontSize: 12, color: '#64748b', fontWeight: 600 }}>Enterprise Accounts</span>
          <span style={{ color: '#cbd5e1' }}>/</span>
          <span style={{ fontSize: 12, color: theme.color, fontWeight: 800 }}>
            {customer?.customer_name || customerId}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button
            type="button"
            onClick={() => navigate('/orders')}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              background: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: 8,
              padding: '7px 14px',
              fontSize: 12,
              fontWeight: 700,
              color: '#334155',
              cursor: 'pointer',
            }}
          >
            <Layers size={14} /> View All Company Orders
          </button>
          <button
            type="button"
            onClick={() => navigate('/orders/new')}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              background: `linear-gradient(135deg, ${theme.color}, #4338ca)`,
              color: '#ffffff',
              border: 'none',
              borderRadius: 8,
              padding: '7px 16px',
              fontSize: 12,
              fontWeight: 700,
              cursor: 'pointer',
              boxShadow: `0 2px 8px ${theme.color}40`,
            }}
          >
            <PlusCircle size={14} /> Create Order for {customer?.customer_name}
          </button>
        </div>
      </div>

      {/* 2. CUSTOMER ACCOUNT DOSSIER HEADER */}
      <div
        style={{
          background: `linear-gradient(135deg, #ffffff, ${theme.bgLight})`,
          border: `1.5px solid ${theme.border}`,
          borderRadius: 12,
          padding: '16px 20px',
          boxShadow: '0 2px 10px rgba(0,0,0,0.03)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 16,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div
            style={{
              width: 52,
              height: 52,
              borderRadius: 12,
              background: theme.color,
              color: '#ffffff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 22,
              fontWeight: 900,
              boxShadow: `0 4px 12px ${theme.color}35`,
            }}
          >
            <Building2 size={26} />
          </div>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <h1 style={{ fontSize: 22, fontWeight: 900, color: '#0f172a', margin: 0, letterSpacing: '-0.02em' }}>
                {customer?.customer_name}
              </h1>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 800,
                  fontFamily: 'monospace',
                  padding: '3px 8px',
                  borderRadius: 6,
                  background: `${theme.color}18`,
                  color: theme.color,
                  border: `1px solid ${theme.color}35`,
                }}
              >
                {customer?.customer_id}
              </span>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  padding: '3px 8px',
                  borderRadius: 6,
                  background: '#e0f2fe',
                  color: '#0369a1',
                }}
              >
                {customer?.segment || 'Enterprise'} Tier
              </span>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  padding: '3px 8px',
                  borderRadius: 6,
                  background: '#f1f5f9',
                  color: '#475569',
                }}
              >
                {customer?.country || 'India'} Region
              </span>
            </div>
            <p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--mfg-text-secondary, #64748b)' }}>
              Enterprise strategic buyer profile &amp; commitments ledger.
            </p>
          </div>
        </div>
      </div>

      {/* 3. LIVE DATABASE METRIC CARDS */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: 12,
        }}
      >
        <div
          style={{
            background: '#ffffff',
            border: '1px solid #e2e8f0',
            borderRadius: 10,
            padding: '12px 16px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: '#64748b', fontSize: 11, fontWeight: 700 }}>
            <span>TOTAL ORDERS</span>
            <Package size={15} style={{ color: theme.color }} />
          </div>
          <div style={{ fontSize: 22, fontWeight: 900, color: '#0f172a', margin: '4px 0 2px' }}>
            {totalOrders.toLocaleString()}
          </div>
          <div style={{ fontSize: 10.5, color: '#64748b' }}>Active order commitments</div>
        </div>

        <div
          style={{
            background: '#ffffff',
            border: '1px solid #e2e8f0',
            borderRadius: 10,
            padding: '12px 16px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: '#64748b', fontSize: 11, fontWeight: 700 }}>
            <span>TOTAL VOLUME</span>
            <TrendingUp size={15} style={{ color: '#0284c7' }} />
          </div>
          <div style={{ fontSize: 22, fontWeight: 900, color: '#0f172a', margin: '4px 0 2px' }}>
            {(customer?.total_quantity || 0).toLocaleString()}
          </div>
          <div style={{ fontSize: 10.5, color: '#64748b' }}>Product units committed</div>
        </div>

        <div
          style={{
            background: '#ffffff',
            border: '1px solid #e2e8f0',
            borderRadius: 10,
            padding: '12px 16px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: '#64748b', fontSize: 11, fontWeight: 700 }}>
            <span>IN PRODUCTION (WIP)</span>
            <Clock size={15} style={{ color: '#3b82f6' }} />
          </div>
          <div style={{ fontSize: 22, fontWeight: 900, color: '#1d4ed8', margin: '4px 0 2px' }}>
            {inProdCount.toLocaleString()}
          </div>
          <div style={{ fontSize: 10.5, color: '#64748b' }}>Active on shop floors</div>
        </div>

        <div
          style={{
            background: '#ffffff',
            border: '1px solid #e2e8f0',
            borderRadius: 10,
            padding: '12px 16px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: '#64748b', fontSize: 11, fontWeight: 700 }}>
            <span>HUMAN APPROVAL</span>
            <ShieldCheck size={15} style={{ color: '#f59e0b' }} />
          </div>
          <div style={{ fontSize: 22, fontWeight: 900, color: '#b45309', margin: '4px 0 2px' }}>
            {approvalCount.toLocaleString()}
          </div>
          <div style={{ fontSize: 10.5, color: '#64748b' }}>Requires Sign-Off gate</div>
        </div>

        <div
          style={{
            background: '#ffffff',
            border: '1px solid #e2e8f0',
            borderRadius: 10,
            padding: '12px 16px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: '#64748b', fontSize: 11, fontWeight: 700 }}>
            <span>DELIVERED &amp; SHIPPED</span>
            <CheckCircle2 size={15} style={{ color: '#16a34a' }} />
          </div>
          <div style={{ fontSize: 22, fontWeight: 900, color: '#15803d', margin: '4px 0 2px' }}>
            {(deliveredCount + shippedCount).toLocaleString()}
          </div>
          <div style={{ fontSize: 10.5, color: '#64748b' }}>Fulfilled realizations</div>
        </div>

        <div
          style={{
            background: '#ffffff',
            border: '1px solid #e2e8f0',
            borderRadius: 10,
            padding: '12px 16px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: '#64748b', fontSize: 11, fontWeight: 700 }}>
            <span>PRODUCT MODELS</span>
            <Layers size={15} style={{ color: '#8b5cf6' }} />
          </div>
          <div style={{ fontSize: 22, fontWeight: 900, color: '#0f172a', margin: '4px 0 2px' }}>
            {customer?.products_count || 3}
          </div>
          <div style={{ fontSize: 10.5, color: '#64748b' }}>Active SKU variants</div>
        </div>
      </div>

      {/* 4. LIFECYCLE STAGE TABS */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          overflowX: 'auto',
          paddingBottom: 2,
        }}
      >
        {STAGE_TABS.map((tab) => {
          const isActive = statusFilter === tab.id
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setStatusFilter(tab.id)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 7,
                padding: '6px 14px',
                borderRadius: 8,
                fontSize: 12,
                fontWeight: 700,
                border: isActive ? `1.5px solid ${theme.color}` : '1px solid #e2e8f0',
                background: isActive ? theme.color : '#ffffff',
                color: isActive ? '#ffffff' : '#475569',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                transition: 'all 0.15s ease',
              }}
            >
              <span>{tab.label}</span>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 800,
                  padding: '1px 6px',
                  borderRadius: 10,
                  background: isActive ? 'rgba(255,255,255,0.25)' : '#f1f5f9',
                  color: isActive ? '#ffffff' : '#64748b',
                }}
              >
                {tab.count}
              </span>
            </button>
          )
        })}
      </div>

      {/* 5. SEARCH & ORDERS TABLE */}
      <div
        style={{
          background: '#ffffff',
          border: '1px solid #e2e8f0',
          borderRadius: 12,
          boxShadow: '0 1px 4px rgba(0,0,0,0.03)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
          padding: '16px 20px',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 12,
          }}
        >
          <div>
            <h2 style={{ fontSize: 15, fontWeight: 800, color: '#0f172a', margin: 0 }}>
              {customer?.customer_name} Orders Ledger
            </h2>
            <p style={{ margin: '2px 0 0', fontSize: 11, color: '#64748b' }}>
              Showing {ordersResult.total.toLocaleString()} commitments · Click any order row to inspect 7-dept audit &amp; agent logs
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                background: '#f8fafc',
                border: '1px solid #e2e8f0',
                borderRadius: 8,
                padding: '4px 10px',
                width: 280,
              }}
            >
              <Search size={14} style={{ color: '#94a3b8' }} />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search Order ID, product..."
                style={{
                  border: 'none',
                  background: 'transparent',
                  outline: 'none',
                  fontSize: 12,
                  width: '100%',
                  color: '#0f172a',
                }}
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 11, color: '#94a3b8' }}
                >
                  ✕
                </button>
              )}
            </div>

            {(statusFilter || searchQuery) && (
              <button
                type="button"
                onClick={() => {
                  setStatusFilter('')
                  setSearchQuery('')
                }}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  border: 'none',
                  background: 'none',
                  fontSize: 11,
                  fontWeight: 700,
                  color: theme.color,
                  cursor: 'pointer',
                }}
              >
                <RotateCcw size={12} /> Reset
              </button>
            )}
          </div>
        </div>

        {/* Orders Table */}
        <div style={{ marginTop: 4 }}>
          <OrdersTable
            orders={ordersResult.orders}
            page={page}
            totalPages={ordersResult.totalPages}
            total={ordersResult.total}
            onPageChange={setPage}
            loading={loadingOrders || fetchingOrders}
          />
        </div>
      </div>
    </div>
  )
}
