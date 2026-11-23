import { ArrowUpRight, ChevronLeft, ChevronRight } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { formatDate } from '../../utils/format'
import { RiskBadge, StatusBadge } from '../common/StatusBadge'
import { DataTable } from '../common/DataTable'

const getShipmentStatus = (order) => {
  if (order.shipment_status) return order.shipment_status
  if (order.shipmentStatus) return order.shipmentStatus
  const shipped = Number(order.shipped_qty || 0)
  const total = Number(order.order_qty || 0)
  const status = (order.order_status || order.status || '').toUpperCase()
  if (status === 'DELIVERED') return 'DELIVERED'
  if (shipped >= total && total > 0) return 'SHIPPED'
  if (shipped > 0) return 'PARTIALLY_SHIPPED'
  if (['IN_PRODUCTION', 'PROCESSING', 'PLANNED'].includes(status)) return 'IN_PRODUCTION'
  return 'PENDING_DISPATCH'
}

const columns = [
  {
    key: 'order',
    title: 'Order',
    render: (order) => {
      const id = order.customer_order_id ?? order.id ?? order.order_id
      return (
        <span
          className="order-link-text"
          style={{
            fontFamily: 'monospace',
            fontWeight: 800,
            color: 'var(--brand-purple)',
            cursor: 'pointer',
          }}
        >
          {id}
        </span>
      )
    },
  },
  {
    key: 'customer',
    title: 'Customer',
    render: (order) => (
      <span className="customer-cell" style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
        {order.customer_name ?? order.customer ?? 'Unavailable'}
      </span>
    ),
  },
  { key: 'order_date', title: 'Order date', render: (order) => formatDate(order.order_date ?? order.date) },
  { key: 'order_qty', title: 'Qty.', render: (order) => order.order_qty ?? order.quantity ?? order.order_quantity ?? '—' },
  {
    key: 'order_status',
    title: 'Status',
    render: (order) => {
      const st = (order.order_status ?? order.status ?? '').toUpperCase()
      const isPending =
        st === 'HUMAN_APPROVAL' ||
        st === 'PENDING_APPROVAL' ||
        st === 'APPROVAL_PENDING'
      const displayStatus = isPending ? 'HUMAN APPROVAL PENDING' : st.replaceAll('_', ' ')
      return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          <StatusBadge>{displayStatus}</StatusBadge>
          {!isPending && order.latest_proposal_status === 'PENDING' && (
            <span
              style={{
                fontSize: 10,
                fontWeight: 700,
                padding: '2px 6px',
                borderRadius: 4,
                background: 'rgba(245, 158, 11, 0.12)',
                color: '#d97706',
                border: '1px solid rgba(245, 158, 11, 0.3)',
              }}
            >
              Rev Pending
            </span>
          )}
        </div>
      )
    },
  },
  { key: 'shipment', title: 'Shipment status', className: 'shipment-cell', render: (order) => <StatusBadge>{getShipmentStatus(order).replaceAll('_', ' ')}</StatusBadge> },
  { key: 'risk', title: 'Risk', render: (order) => <span className="risk-cell"><RiskBadge risk={order.risk?.risk_level} /><small>{order.risk?.category ?? 'UNKNOWN'}</small></span> },
  { key: 'release_status', title: 'Quality release', render: (order) => <StatusBadge>{(order.release_status ?? 'NOT_INSPECTED').replaceAll('_', ' ')}</StatusBadge> },
  { key: 'link_type', title: 'Production link', render: (order) => <StatusBadge>{(order.link_type ?? 'UNLINKED').replaceAll('_', ' ')}</StatusBadge> },
  {
    key: 'action',
    title: '',
    className: 'table-action-cell',
    render: (order) => {
      const id = order.customer_order_id ?? order.id ?? order.order_id
      return (
        <span
          className="table-action"
          title={`View order details for ${id}`}
          style={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center' }}
        >
          <ArrowUpRight size={16} />
        </span>
      )
    },
  },
]

export function OrdersTable({ orders, page, totalPages, total, onPageChange, loading, onOrderSelect }) {
  const navigate = useNavigate()

  const handleRowClick = (order) => {
    const id = order.customer_order_id ?? order.id ?? order.order_id
    if (!id) return
    if (onOrderSelect) {
      onOrderSelect(order)
    } else {
      navigate(`/orders/${encodeURIComponent(id)}`)
    }
  }

  return (
    <>
      <DataTable
        columns={columns}
        rows={orders}
        getRowKey={(order) => order.customer_order_id ?? order.id ?? order.order_id}
        loading={loading}
        emptyTitle="No orders found"
        emptyDescription="Try adjusting your search or filters."
        minWidth={900}
        onRowClick={handleRowClick}
      />
      <div className="table-footer" style={{ padding: '12px 20px', borderTop: '1px solid var(--line)' }}>
        <span>{total ? <>Showing <strong>{Math.min((page - 1) * 20 + 1, total)}–{Math.min(page * 20, total)}</strong> of <strong>{total}</strong> orders</> : 'No orders'}</span>
        <div className="pagination">
          <button onClick={() => onPageChange(page - 1)} disabled={page <= 1 || loading} aria-label="Previous page"><ChevronLeft size={16} /></button>
          <span>Page <strong>{page}</strong> of <strong>{totalPages || 1}</strong></span>
          <button onClick={() => onPageChange(page + 1)} disabled={page >= totalPages || loading} aria-label="Next page"><ChevronRight size={16} /></button>
        </div>
      </div>
    </>
  )
}
