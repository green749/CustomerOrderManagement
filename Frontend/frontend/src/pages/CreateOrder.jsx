import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  Building2,
  Package,
  CreditCard,
  CalendarDays,
  Sparkles,
  AlertTriangle,
  Loader2,
  Cpu,
  ShieldCheck,
  CheckCircle2,
  Clock,
  Layers,
  Truck,
  Box,
  FileCheck2,
} from 'lucide-react'
import { agentsApi } from '../api/agents.api'
import { formatINR } from '../utils/format'

const CUSTOMERS = [
  { id: 'CUS-001', name: 'Retailer North', defaultShipTo: 'Regional DC - North, Delhi NCR', contact: 'procurement@retailernorth.in' },
  { id: 'CUS-002', name: 'MobileMart', defaultShipTo: 'Central Distribution Hub, Mumbai', contact: 'orders@mobilemart.com' },
  { id: 'CUS-003', name: 'Digital Bazaar', defaultShipTo: 'Express Fulfillment Centre, Bengaluru', contact: 'supply@digitalbazaar.co' },
  { id: 'CUS-004', name: 'Global Devices', defaultShipTo: 'South Zone Gateway, Chennai', contact: 'imports@globaldevices.com' },
]

const PRODUCTS = [
  { id: 'SPH-A15-128', name: 'Aster 15 128GB', basePrice: 14500, description: 'Mid-tier enterprise flagship smartphone' },
  { id: 'SPH-A15-256', name: 'Aster 15 256GB', basePrice: 17200, description: 'High-capacity enterprise smartphone' },
  { id: 'SPH-PRO-256', name: 'Aster Pro 256GB', basePrice: 24900, description: 'Premium Pro Series with 120Hz display' },
]

const PACKAGING_OPTIONS = [
  'Standard Retail Master Carton (Palletized)',
  'Anti-Static ESD Protective Bulk Crates',
  'Reinforced Export Sea-Freight Packaging',
  'Custom OEM Customer-Branded Packaging',
]

const COLORS = ['Obsidian Black', 'Glacier White', 'Titanium Silver', 'Midnight Blue']

export default function CreateOrder() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // Form state
  const [customerId, setCustomerId] = useState('CUS-001')
  const [shipTo, setShipTo] = useState('Regional DC - North, Delhi NCR')
  const [contactEmail, setContactEmail] = useState('procurement@retailernorth.in')

  const [productId, setProductId] = useState('SPH-A15-128')
  const [orderQty, setOrderQty] = useState(250)
  const [unitOfMeasure, setUnitOfMeasure] = useState('Units')
  const [color, setColor] = useState('Obsidian Black')
  const [packagingReq, setPackagingReq] = useState('Standard Retail Master Carton (Palletized)')

  const [poNumber, setPoNumber] = useState(() => `PO-2026-${Math.floor(1000 + Math.random() * 9000)}`)
  const [unitPrice, setUnitPrice] = useState(14500)
  const [priority, setPriority] = useState('MEDIUM')
  const [channel, setChannel] = useState('PORTAL')

  // Target delivery date: default to 14 days out
  const defaultDate = new Date()
  defaultDate.setDate(defaultDate.getDate() + 14)
  const [requestedDeliveryDate, setRequestedDeliveryDate] = useState(() => defaultDate.toISOString().split('T')[0])
  const [specialInstructions, setSpecialInstructions] = useState('')

  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const selectedCustomer = CUSTOMERS.find((c) => c.id === customerId) || CUSTOMERS[0]
  const selectedProduct = PRODUCTS.find((p) => p.id === productId) || PRODUCTS[0]
  const totalValueINR = (Number(orderQty) || 0) * (Number(unitPrice) || 0)

  const handleCustomerChange = (cid) => {
    setCustomerId(cid)
    const match = CUSTOMERS.find((c) => c.id === cid)
    if (match) {
      setShipTo(match.defaultShipTo)
      setContactEmail(match.contact)
    }
  }

  const handleProductChange = (pid) => {
    setProductId(pid)
    const match = PRODUCTS.find((p) => p.id === pid)
    if (match) {
      setUnitPrice(match.basePrice)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (submitting) return
    setError('')
    setSubmitting(true)

    const payload = {
      customer_id: customerId,
      product_id: productId,
      order_qty: Number(orderQty),
      requested_delivery_date: requestedDeliveryDate,
      unit_price_inr: Number(unitPrice),
      priority,
      channel,
      ship_to: shipTo,
      product_config: {
        po_number: poNumber,
        color,
        uom: unitOfMeasure,
        special_instructions: specialInstructions,
      },
      packaging_req: packagingReq,
      submit_for_approval: true,
      customer_name: selectedCustomer.name,
      product_name: selectedProduct.name,
    }

    try {
      sessionStorage.setItem('pending_agent2_intake', JSON.stringify(payload))
    } catch (err) {
      console.warn('Session storage write error:', err)
    }

    // Immediately navigate to feasibility page without triggering Agent 2 here
    navigate('/assessments?runNewOrder=true', { state: { newOrderPayload: payload } })
  }

  return (
    <div className="page-stack create-order-page" style={{ maxWidth: 1200, margin: '0 auto', paddingBottom: 60 }}>
      {/* BREADCRUMB & HEADER */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button
            type="button"
            onClick={() => navigate('/orders')}
            className="text-button"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              color: 'var(--brand-purple)',
              fontWeight: 600,
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            <ArrowLeft size={16} /> Back to Orders
          </button>
          <span style={{ color: 'var(--text-muted)' }}>/</span>
          <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Create New Order</span>
        </div>

        <div
          style={{
            background: 'var(--brand-purple-soft)',
            border: '1px solid rgba(111, 61, 186, 0.2)',
            borderRadius: 8,
            padding: '6px 12px',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            fontSize: 12,
            color: 'var(--brand-purple)',
            fontWeight: 600,
          }}
        >
          <Cpu size={15} /> Agent 2 Automated Pre-Commitment
        </div>
      </div>

      {error && (
        <div
          role="alert"
          style={{
            padding: '14px 18px',
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid #EF4444',
            borderRadius: 8,
            color: '#DC2626',
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            fontSize: 14,
            fontWeight: 500,
          }}
        >
          <AlertTriangle size={18} />
          <div>{error}</div>
        </div>
      )}

      {/* MAIN TWO-COLUMN CONTENT */}
      <form onSubmit={handleSubmit} noValidate style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.8fr) minmax(0, 1.2fr)', gap: 24, marginTop: 8 }}>
        {/* LEFT COLUMN: THE FORM */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* SECTION 1: CUSTOMER INFORMATION */}
          <section
            className="card"
            style={{
              padding: 24,
              background: 'var(--surface-hi)',
              border: '1px solid var(--line)',
              borderRadius: 12,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16, borderBottom: '1px solid var(--line)', paddingBottom: 12 }}>
              <div style={{ width: 32, height: 32, borderRadius: 8, background: 'rgba(111, 61, 186, 0.1)', color: 'var(--brand-purple)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Building2 size={18} />
              </div>
              <div>
                <h3 style={{ fontSize: 16, fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>1. Customer Information</h3>
                <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: '2px 0 0' }}>Select registered enterprise customer account</p>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <div style={{ gridColumn: 'span 2' }}>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
                  Customer Account *
                </label>
                <select
                  value={customerId}
                  onChange={(e) => handleCustomerChange(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: 8,
                    border: '1px solid var(--line)',
                    background: 'var(--kg-bg-2)',
                    color: 'var(--text-primary)',
                    fontSize: 14,
                    fontWeight: 500,
                    outline: 'none',
                  }}
                >
                  {CUSTOMERS.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} ({c.id})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
                  Customer ID
                </label>
                <input
                  type="text"
                  value={customerId}
                  disabled
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: 8,
                    border: '1px solid var(--line)',
                    background: 'var(--line)',
                    color: 'var(--text-secondary)',
                    fontSize: 13,
                    fontFamily: 'monospace',
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
                  Contact Email
                </label>
                <input
                  type="email"
                  value={contactEmail}
                  onChange={(e) => setContactEmail(e.target.value)}
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
              </div>

              <div style={{ gridColumn: 'span 2' }}>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
                  Destination Ship-To Address *
                </label>
                <input
                  type="text"
                  value={shipTo}
                  onChange={(e) => setShipTo(e.target.value)}
                  placeholder="Delivery fulfillment facility address"
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
              </div>
            </div>
          </section>

          {/* SECTION 2: PRODUCT SPECIFICATIONS */}
          <section
            className="card"
            style={{
              padding: 24,
              background: 'var(--surface-hi)',
              border: '1px solid var(--line)',
              borderRadius: 12,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16, borderBottom: '1px solid var(--line)', paddingBottom: 12 }}>
              <div style={{ width: 32, height: 32, borderRadius: 8, background: 'rgba(77, 142, 235, 0.1)', color: 'var(--brand-blue)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Package size={18} />
              </div>
              <div>
                <h3 style={{ fontSize: 16, fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>2. Product & Configuration</h3>
                <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: '2px 0 0' }}>Configure item quantities, finish and packaging</p>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <div style={{ gridColumn: 'span 2' }}>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
                  Product Model *
                </label>
                <select
                  value={productId}
                  onChange={(e) => handleProductChange(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: 8,
                    border: '1px solid var(--line)',
                    background: 'var(--kg-bg-2)',
                    color: 'var(--text-primary)',
                    fontSize: 14,
                    fontWeight: 500,
                    outline: 'none',
                  }}
                >
                  {PRODUCTS.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.id}) — {p.description}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
                  Order Quantity *
                </label>
                <input
                  type="number"
                  min="1"
                  step="1"
                  value={orderQty}
                  onChange={(e) => setOrderQty(Math.max(1, parseInt(e.target.value, 10) || 1))}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: 8,
                    border: '1px solid var(--line)',
                    background: 'var(--kg-bg-2)',
                    color: 'var(--text-primary)',
                    fontSize: 14,
                    fontWeight: 600,
                  }}
                />
                {/* Quantity quick buttons */}
                <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                  {[100, 250, 500, 1000].map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => setOrderQty(q)}
                      style={{
                        padding: '2px 8px',
                        fontSize: 11,
                        borderRadius: 4,
                        border: '1px solid var(--line)',
                        background: orderQty === q ? 'var(--brand-purple)' : 'var(--kg-bg-2)',
                        color: orderQty === q ? '#FFFFFF' : 'var(--text-secondary)',
                        cursor: 'pointer',
                      }}
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
                  Unit of Measure
                </label>
                <input
                  type="text"
                  value={unitOfMeasure}
                  onChange={(e) => setUnitOfMeasure(e.target.value)}
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
              </div>

              <div>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
                  Color / Finish
                </label>
                <select
                  value={color}
                  onChange={(e) => setColor(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: 8,
                    border: '1px solid var(--line)',
                    background: 'var(--kg-bg-2)',
                    color: 'var(--text-primary)',
                    fontSize: 13,
                  }}
                >
                  {COLORS.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
                  Packaging Requirement
                </label>
                <select
                  value={packagingReq}
                  onChange={(e) => setPackagingReq(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: 8,
                    border: '1px solid var(--line)',
                    background: 'var(--kg-bg-2)',
                    color: 'var(--text-primary)',
                    fontSize: 13,
                  }}
                >
                  {PACKAGING_OPTIONS.map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </div>
            </div>
          </section>

          {/* SECTION 3: COMMERCIAL & SCHEDULE */}
          <section
            className="card"
            style={{
              padding: 24,
              background: 'var(--surface-hi)',
              border: '1px solid var(--line)',
              borderRadius: 12,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16, borderBottom: '1px solid var(--line)', paddingBottom: 12 }}>
              <div style={{ width: 32, height: 32, borderRadius: 8, background: 'rgba(245, 138, 58, 0.1)', color: 'var(--brand-orange)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <CreditCard size={18} />
              </div>
              <div>
                <h3 style={{ fontSize: 16, fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>3. Commercial Terms & Target Schedule</h3>
                <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: '2px 0 0' }}>PO references, pricing, priority and requested milestone date</p>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <div>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
                  Customer PO Number *
                </label>
                <input
                  type="text"
                  value={poNumber}
                  onChange={(e) => setPoNumber(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: 8,
                    border: '1px solid var(--line)',
                    background: 'var(--kg-bg-2)',
                    color: 'var(--text-primary)',
                    fontSize: 13,
                    fontFamily: 'monospace',
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
                  Unit Price (INR) *
                </label>
                <input
                  type="number"
                  min="0"
                  step="any"
                  value={unitPrice}
                  onChange={(e) => setUnitPrice(Math.max(0, parseFloat(e.target.value) || 0))}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: 8,
                    border: '1px solid var(--line)',
                    background: 'var(--kg-bg-2)',
                    color: 'var(--text-primary)',
                    fontSize: 14,
                    fontWeight: 600,
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
                  Priority Level
                </label>
                <select
                  value={priority}
                  onChange={(e) => setPriority(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: 8,
                    border: '1px solid var(--line)',
                    background: 'var(--kg-bg-2)',
                    color: 'var(--text-primary)',
                    fontSize: 13,
                  }}
                >
                  <option value="LOW">Low</option>
                  <option value="MEDIUM">Medium (Standard)</option>
                  <option value="HIGH">High Priority</option>
                  <option value="URGENT">Urgent Expedite</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
                  Sales Channel
                </label>
                <select
                  value={channel}
                  onChange={(e) => setChannel(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: 8,
                    border: '1px solid var(--line)',
                    background: 'var(--kg-bg-2)',
                    color: 'var(--text-primary)',
                    fontSize: 13,
                  }}
                >
                  <option value="PORTAL">B2B Customer Portal</option>
                  <option value="EDI">Automated EDI Feed</option>
                  <option value="DIRECT_SALES">Key Account Direct</option>
                  <option value="CUSTOMER_SERVICE">Customer Support Desk</option>
                </select>
              </div>

              <div style={{ gridColumn: 'span 2' }}>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
                  Customer Requested Delivery Date *
                </label>
                <input
                  type="date"
                  value={requestedDeliveryDate}
                  onChange={(e) => setRequestedDeliveryDate(e.target.value)}
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
              </div>

              <div style={{ gridColumn: 'span 2' }}>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
                  Special Handling / Instructions
                </label>
                <textarea
                  rows={2}
                  value={specialInstructions}
                  onChange={(e) => setSpecialInstructions(e.target.value)}
                  placeholder="e.g. Expedited air delivery requested; palletize maximum 50 units per pallet."
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: 8,
                    border: '1px solid var(--line)',
                    background: 'var(--kg-bg-2)',
                    color: 'var(--text-primary)',
                    fontSize: 13,
                    resize: 'vertical',
                  }}
                />
              </div>
            </div>
          </section>
        </div>

        {/* RIGHT COLUMN: LIVE SUMMARY & AGENT 2 PIPELINE */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* ORDER SUMMARY PREVIEW CARD */}
          <div
            className="card"
            style={{
              padding: 24,
              background: 'var(--surface-hi)',
              border: '1px solid var(--line)',
              borderRadius: 12,
              position: 'sticky',
              top: 20,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
              <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)' }}>
                Live Commitment Summary
              </span>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  padding: '2px 8px',
                  borderRadius: 999,
                  background: 'rgba(111, 61, 186, 0.1)',
                  color: 'var(--brand-purple)',
                }}
              >
                Draft
              </span>
            </div>

            <div style={{ padding: '16px 0', borderTop: '1px solid var(--line)', borderBottom: '1px solid var(--line)', display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Customer:</span>
                <strong style={{ fontSize: 13, color: 'var(--text-primary)' }}>{selectedCustomer.name}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Product:</span>
                <strong style={{ fontSize: 13, color: 'var(--text-primary)' }}>{selectedProduct.name}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Quantity:</span>
                <strong style={{ fontSize: 13, color: 'var(--text-primary)' }}>{orderQty.toLocaleString()} Units</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Unit Price:</span>
                <strong style={{ fontSize: 13, color: 'var(--text-primary)' }}>{formatINR(unitPrice)}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Requested Date:</span>
                <strong style={{ fontSize: 13, color: 'var(--brand-purple)' }}>{requestedDeliveryDate}</strong>
              </div>
            </div>

            <div style={{ margin: '18px 0', display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' }}>Total Commitment Value:</span>
              <strong style={{ fontSize: 24, fontWeight: 800, color: 'var(--text-primary)' }}>
                {formatINR(totalValueINR)}
              </strong>
            </div>

            {/* AGENT 2 PIPELINE EXPLANATION */}
            <div
              style={{
                background: 'var(--kg-bg-2)',
                border: '1px solid var(--line)',
                borderRadius: 10,
                padding: 16,
                marginBottom: 20,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--brand-purple)', fontWeight: 700, fontSize: 13, marginBottom: 8 }}>
                <Sparkles size={16} /> Agent 2 Automated Verification
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: '0 0 12px', lineHeight: 1.5 }}>
                Submitting this order will instantly query and evaluate readiness across all 7 manufacturing source systems:
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 11, color: 'var(--text-secondary)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <CreditCard size={13} color="var(--brand-blue)" /> <strong>ERP</strong> (Credit)
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Box size={13} color="var(--brand-purple)" /> <strong>MMS</strong> (Raw Stock)
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Layers size={13} color="var(--brand-orange)" /> <strong>MES</strong> (Capacity)
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Package size={13} color="var(--brand-blue)" /> <strong>WMS</strong> (Staging)
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <ShieldCheck size={13} color="#16A34A" /> <strong>QMS</strong> (Quality Hold)
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Truck size={13} color="var(--brand-orange)" /> <strong>TMS</strong> (Transit)
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, gridColumn: 'span 2' }}>
                  <FileCheck2 size={13} color="var(--brand-purple)" /> <strong>PLM</strong> (Design Lifecycle)
                </div>
              </div>
            </div>

            {/* ACTION BUTTONS */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <button
                type="submit"
                disabled={submitting}
                style={{
                  width: '100%',
                  padding: '14px 20px',
                  borderRadius: 10,
                  border: 'none',
                  background: 'linear-gradient(135deg, var(--brand-purple) 0%, #8553d1 100%)',
                  color: '#FFFFFF',
                  fontWeight: 700,
                  fontSize: 14,
                  cursor: submitting ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 10,
                  boxShadow: '0 4px 14px rgba(111, 61, 186, 0.35)',
                  transition: 'opacity 0.2s',
                  opacity: submitting ? 0.8 : 1,
                }}
              >
                {submitting ? (
                  <>
                    <Loader2 size={18} className="animate-spin" /> Evaluating 7 Departments...
                  </>
                ) : (
                  <>
                    <Sparkles size={18} /> Submit & Trigger Feasibility Assessment
                  </>
                )}
              </button>

              <button
                type="button"
                onClick={() => navigate('/orders')}
                disabled={submitting}
                style={{
                  width: '100%',
                  padding: '10px 16px',
                  borderRadius: 8,
                  border: '1px solid var(--line)',
                  background: 'transparent',
                  color: 'var(--text-secondary)',
                  fontWeight: 600,
                  fontSize: 13,
                  cursor: 'pointer',
                }}
              >
                Cancel & Return
              </button>
            </div>
          </div>
        </div>
      </form>
    </div>
  )
}

