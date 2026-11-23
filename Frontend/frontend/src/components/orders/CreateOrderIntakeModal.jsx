import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import {
  X,
  FilePlus2,
  Building2,
  Package,
  CreditCard,
  CalendarDays,
  Sparkles,
  AlertTriangle,
  Loader2,
  CheckCircle2,
  Layers,
  Factory,
  Warehouse,
  ShieldAlert,
  Truck,
  Cpu,
} from 'lucide-react'
import { agentsApi } from '../../api/agents.api'

const CUSTOMERS = [
  { id: 'CUS-001', name: 'Retailer North', defaultShipTo: 'Regional DC - North, Delhi NCR', contact: 'procurement@retailernorth.in' },
  { id: 'CUS-002', name: 'MobileMart', defaultShipTo: 'Central Distribution Hub, Mumbai', contact: 'orders@mobilemart.com' },
  { id: 'CUS-003', name: 'Digital Bazaar', defaultShipTo: 'Express Fulfillment Centre, Bengaluru', contact: 'supply@digitalbazaar.co' },
  { id: 'CUS-004', name: 'Global Devices', defaultShipTo: 'South Zone Gateway, Chennai', contact: 'imports@globaldevices.com' },
]

const PRODUCTS = [
  { id: 'SPH-A15-128', name: 'Aster 15 128GB', basePrice: 14500, defaultStorage: '128GB', defaultRam: '6GB' },
  { id: 'SPH-A15-256', name: 'Aster 15 256GB', basePrice: 17200, defaultStorage: '256GB', defaultRam: '8GB' },
  { id: 'SPH-PRO-256', name: 'Aster Pro 256GB', basePrice: 24900, defaultStorage: '256GB', defaultRam: '12GB' },
]

const PACKAGING_OPTIONS = [
  'Standard Retail Master Carton (Palletized)',
  'Anti-Static ESD Protective Bulk Crates',
  'Reinforced Export Sea-Freight Packaging',
  'Custom OEM Customer-Branded Packaging',
]

// 7 Departments for Agent 2 Autonomous Feasibility Check
const AGENT2_DEPTS = [
  { code: 'ERP', name: 'Order & Commercial', icon: Building2, desc: 'Pricing, credit rating & commercial contract' },
  { code: 'MMS', name: 'Material Planning', icon: Layers, desc: 'BOM explosion & ATP component stock' },
  { code: 'MES', name: 'Plant Production', icon: Factory, desc: 'Line capacity & daily throughput scheduling' },
  { code: 'WMS', name: 'Warehouse & Staging', icon: Warehouse, desc: 'Packaging readiness & staging bay allocation' },
  { code: 'QMS', name: 'Quality Assurance', icon: ShieldAlert, desc: 'Quality holds & lot compliance clearance' },
  { code: 'TMS', name: 'Logistics & Transit', icon: Truck, desc: 'Carrier dispatch window & regional transit' },
  { code: 'PLM', name: 'Product Lifecycle', icon: Cpu, desc: 'BOM revisions & engineering compatibility' },
]

export function CreateOrderIntakeModal({ isOpen, open, onClose, onAssessmentCreated, onCreated }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const isModalOpen = isOpen ?? open ?? false
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

  // Default requested delivery date: 14 days from today
  const defaultDate = new Date()
  defaultDate.setDate(defaultDate.getDate() + 14)
  const [requestedDeliveryDate, setRequestedDeliveryDate] = useState(() => defaultDate.toISOString().split('T')[0])
  const [specialInstructions, setSpecialInstructions] = useState('')

  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  if (!isModalOpen) return null

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

    onClose()
    navigate('/assessments?runNewOrder=true', { state: { newOrderPayload: payload } })
  }

  return (
    <div className="mfg-modal-overlay" role="dialog" aria-modal="true">
      <div className="mfg-modal-content" style={{ maxWidth: 720, maxHeight: '88vh', display: 'flex', flexDirection: 'column' }}>
        {/* Modal Header */}
        <div className="mfg-modal-header" style={{ flexShrink: 0 }}>
          <h2>
            <FilePlus2 size={20} color="var(--brand-orange)" />
            Customer Order Intake · Agent 2 Assessment Trigger
          </h2>
          <button
            type="button"
            className="icon-button"
            onClick={onClose}
            aria-label="Close dialog"
            disabled={submitting}
          >
            <X size={18} />
          </button>
        </div>

        <form
          onSubmit={handleSubmit}
          style={{
            display: 'flex',
            flexDirection: 'column',
            flex: 1,
            minHeight: 0,
            overflow: 'hidden',
          }}
        >
            {error && (
              <div
                style={{
                  margin: '16px 24px 0',
                  padding: '12px 16px',
                  background: 'rgba(255,107,129,0.15)',
                  border: '1px solid #ff6b81',
                  borderRadius: 8,
                  color: '#ff8597',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  fontSize: 12,
                  flexShrink: 0,
                }}
              >
                <AlertTriangle size={16} />
                <span>{error}</span>
              </div>
            )}

            <div
              className="mfg-modal-body"
              style={{
                flex: 1,
                overflowY: 'auto',
                maxHeight: 'calc(88vh - 130px)',
                minHeight: 0,
              }}
            >
              {/* SECTION A: CUSTOMER CONTEXT */}
              <div className="mfg-form-section">
                <div className="mfg-section-title">
                  <Building2 size={15} /> Section A: Customer Master Data
                </div>
                <div className="mfg-form-grid">
                  <div className="mfg-form-group">
                    <label className="input-label">Select Customer Account</label>
                    <select className="select input" value={customerId} onChange={(e) => handleCustomerChange(e.target.value)}>
                      {CUSTOMERS.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name} ({c.id})
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="mfg-form-group">
                    <label className="input-label">Ship-to Facility / Delivery Hub</label>
                    <input className="input" type="text" value={shipTo} onChange={(e) => setShipTo(e.target.value)} required />
                  </div>
                  <div className="mfg-form-group">
                    <label className="input-label">Customer Contact Email (PO Notifications)</label>
                    <input
                      className="input"
                      type="email"
                      value={contactEmail}
                      onChange={(e) => setContactEmail(e.target.value)}
                      required
                    />
                  </div>
                  <div className="mfg-form-group">
                    <label className="input-label">Internal Intake Channel</label>
                    <select className="select input" value={channel} onChange={(e) => setChannel(e.target.value)}>
                      <option value="PORTAL">PORTAL (Enterprise Web Interface)</option>
                      <option value="EDI">EDI (Automated 850 Intake)</option>
                      <option value="ERP">ERP (SAP Direct Intake)</option>
                      <option value="EMAIL">EMAIL (Customer Support Intake)</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* SECTION B: PRODUCT SPECIFICATIONS */}
              <div className="mfg-form-section">
                <div className="mfg-section-title">
                  <Package size={15} /> Section B: Product &amp; Bill of Materials (BOM) Specs
                </div>
                <div className="mfg-form-grid">
                  <div className="mfg-form-group">
                    <label className="input-label">Product Model</label>
                    <select className="select input" value={productId} onChange={(e) => handleProductChange(e.target.value)}>
                      {PRODUCTS.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name} ({p.id})
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="mfg-form-group">
                    <label className="input-label">Order Quantity</label>
                    <input
                      className="input"
                      type="number"
                      min={1}
                      max={100000}
                      value={orderQty}
                      onChange={(e) => setOrderQty(e.target.value)}
                      required
                    />
                  </div>
                  <div className="mfg-form-group">
                    <label className="input-label">Color Variant</label>
                    <select className="select input" value={color} onChange={(e) => setColor(e.target.value)}>
                      <option value="Obsidian Black">Obsidian Black</option>
                      <option value="Titanium Silver">Titanium Silver</option>
                      <option value="Glacier Blue">Glacier Blue</option>
                      <option value="Aurora Green">Aurora Green</option>
                    </select>
                  </div>
                  <div className="mfg-form-group">
                    <label className="input-label">Unit of Measure</label>
                    <input className="input" type="text" value={unitOfMeasure} onChange={(e) => setUnitOfMeasure(e.target.value)} />
                  </div>
                  <div className="mfg-form-group col-span-2">
                    <label className="input-label">Packaging Requirements</label>
                    <select className="select input" value={packagingReq} onChange={(e) => setPackagingReq(e.target.value)}>
                      {PACKAGING_OPTIONS.map((opt) => (
                        <option key={opt} value={opt}>
                          {opt}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>

              {/* SECTION C: COMMERCIAL TERMS */}
              <div className="mfg-form-section">
                <div className="mfg-section-title">
                  <CreditCard size={15} /> Section C: Commercial &amp; Contract Terms
                </div>
                <div className="mfg-form-grid">
                  <div className="mfg-form-group">
                    <label className="input-label">Customer PO Number</label>
                    <input className="input" type="text" value={poNumber} onChange={(e) => setPoNumber(e.target.value)} required />
                  </div>
                  <div className="mfg-form-group">
                    <label className="input-label">Unit Price (INR ₹)</label>
                    <input
                      className="input"
                      type="number"
                      min={1}
                      value={unitPrice}
                      onChange={(e) => setUnitPrice(e.target.value)}
                      required
                    />
                  </div>
                  <div className="mfg-form-group">
                    <label className="input-label">Order Priority</label>
                    <select className="select input" value={priority} onChange={(e) => setPriority(e.target.value)}>
                      <option value="LOW">LOW (Standard Buffer)</option>
                      <option value="MEDIUM">MEDIUM (Standard Fulfillment)</option>
                      <option value="HIGH">HIGH (Expedited Pipeline)</option>
                      <option value="URGENT">URGENT (Critical Priority SLA)</option>
                    </select>
                  </div>
                  <div className="mfg-form-group">
                    <label className="input-label">Total Contract Value (Calculated)</label>
                    <input
                      className="input"
                      type="text"
                      disabled
                      value={new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(
                        (Number(orderQty) || 0) * (Number(unitPrice) || 0)
                      )}
                      style={{ background: 'var(--kg-bg-2)', fontWeight: 700, color: 'var(--text-primary)' }}
                    />
                  </div>
                </div>
              </div>

              {/* SECTION D: REQUESTED DELIVERY */}
              <div className="mfg-form-section">
                <div className="mfg-section-title">
                  <CalendarDays size={15} /> Section D: Requested Delivery &amp; Logistics
                </div>
                <div className="mfg-form-grid">
                  <div className="mfg-form-group">
                    <label className="input-label">Customer Requested Delivery Date</label>
                    <input
                      className="input"
                      type="date"
                      value={requestedDeliveryDate}
                      onChange={(e) => setRequestedDeliveryDate(e.target.value)}
                      required
                    />
                  </div>
                  <div className="mfg-form-group">
                    <label className="input-label">Special Instructions / Gate Handling</label>
                    <input
                      className="input"
                      type="text"
                      value={specialInstructions}
                      onChange={(e) => setSpecialInstructions(e.target.value)}
                      placeholder="e.g. Liftgate required, Fragile ESD handling"
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="mfg-modal-footer" style={{ flexShrink: 0 }}>
              <button
                type="button"
                className="button button-secondary"
                onClick={onClose}
                disabled={submitting}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="button button-primary"
                disabled={submitting}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '10px 22px',
                  fontSize: 13,
                  fontWeight: 700,
                  borderRadius: 8,
                  background: 'linear-gradient(135deg, var(--brand-purple), #7c3aed)',
                  color: 'white',
                  border: 'none',
                  boxShadow: '0 3px 10px rgba(111, 61, 186, 0.35)',
                  cursor: submitting ? 'wait' : 'pointer',
                  minWidth: 320,
                  justifyContent: 'center',
                }}
              >
                {submitting ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    Running Agent 2 Feasibility Check…
                  </>
                ) : (
                  <>
                    <Sparkles size={16} />
                    Execute Agent 2 Assessment Across 7 Depts
                  </>
                )}
              </button>
            </div>
          </form>
      </div>
    </div>
  )
}
