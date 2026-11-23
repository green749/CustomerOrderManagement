import { useState } from 'react'
import { AlertTriangle, CheckCircle, Clock, Factory, FileCheck, Layers, PackageCheck, Send, ShieldAlert, Sparkles, Truck, Warehouse, X } from 'lucide-react'
import { workflowApi } from '../../api/workflow.api'
import { Button } from '../common/Button'
import { Input } from '../common/Input'
import { Select } from '../common/Select'
import { StatusBadge } from '../common/StatusBadge'
import { formatDate } from '../../utils/format'

const DEFAULT_CUSTOMERS = [
  { id: 'CUS-001', name: 'Retailer North' },
  { id: 'CUS-002', name: 'MobileMart' },
  { id: 'CUS-003', name: 'Digital Bazaar' },
  { id: 'CUS-004', name: 'Global Devices' },
]

const DEFAULT_PRODUCTS = [
  { id: 'SPH-A15-128', name: 'Smartphone A15 128GB' },
  { id: 'SPH-A15-256', name: 'Smartphone A15 256GB' },
  { id: 'SPH-PRO-256', name: 'Smartphone Pro 256GB' },
]

const DEPT_ICONS = {
  ERP: <FileCheck size={16} />,
  MMS: <Factory size={16} />,
  MES: <Layers size={16} />,
  WMS: <Warehouse size={16} />,
  QMS: <ShieldAlert size={16} />,
  TMS: <Truck size={16} />,
  PLM: <PackageCheck size={16} />,
}

export function NewOrderAssessmentModal({ isOpen, onClose, onAssessmentCreated }) {
  const [customerId, setCustomerId] = useState('CUS-001')
  const [productId, setProductId] = useState('SPH-A15-128')
  const [orderQty, setOrderQty] = useState('500')
  const [requestedDate, setRequestedDate] = useState(() => {
    const d = new Date()
    d.setDate(d.getDate() + 14)
    return d.toISOString().split('T')[0]
  })
  const [unitPrice, setUnitPrice] = useState('18500')
  const [priority, setPriority] = useState('MEDIUM')
  const [channel, setChannel] = useState('EDI')
  const [shipTo, setShipTo] = useState('Central Warehouse Hub, Delhi')

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [assessment, setAssessment] = useState(null)

  if (!isOpen) return null

  const handleRunAssessment = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    setAssessment(null)

    try {
      const payload = {
        customer_id: customerId.trim(),
        product_id: productId.trim(),
        order_qty: Number(orderQty) || 1,
        requested_delivery_date: requestedDate,
        unit_price_inr: Number(unitPrice) || undefined,
        priority,
        channel,
        ship_to: shipTo.trim() || undefined,
        submit_for_approval: true,
      }

      const res = await workflowApi.createAssessment(payload)
      setAssessment(res)
      if (onAssessmentCreated) {
        onAssessmentCreated(res)
      }
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Assessment could not be completed.')
    } finally {
      setLoading(false)
    }
  }

  const handleReset = () => {
    setAssessment(null)
    setError('')
  }

  return (
    <div className="modal-backdrop">
      <div className="card modal-content assessment-modal">
        <div className="modal-header">
          <div className="modal-title-wrap">
            <span className="agent-badge agent-2-badge"><Sparkles size={14} /> AGENT 2</span>
            <h2>Order Feasibility & Commitment Assessment</h2>
            <p>Pre-confirmation evaluation across 7 manufacturing departments</p>
          </div>
          <button className="modal-close" onClick={onClose} aria-label="Close modal">
            <X size={18} />
          </button>
        </div>

        <div className="modal-body">
          {!assessment ? (
            <form onSubmit={handleRunAssessment} className="assessment-form">
              <div className="form-grid">
                <Select
                  label="Customer"
                  value={customerId}
                  onChange={(e) => setCustomerId(e.target.value)}
                  required
                >
                  {DEFAULT_CUSTOMERS.map((c) => (
                    <option key={c.id} value={c.id}>{c.id} - {c.name}</option>
                  ))}
                </Select>

                <Select
                  label="Product"
                  value={productId}
                  onChange={(e) => setProductId(e.target.value)}
                  required
                >
                  {DEFAULT_PRODUCTS.map((p) => (
                    <option key={p.id} value={p.id}>{p.id} - {p.name}</option>
                  ))}
                </Select>

                <Input
                  label="Order Quantity (units)"
                  type="number"
                  min="1"
                  value={orderQty}
                  onChange={(e) => setOrderQty(e.target.value)}
                  required
                />

                <Input
                  label="Requested Delivery Date"
                  type="date"
                  value={requestedDate}
                  onChange={(e) => setRequestedDate(e.target.value)}
                  required
                />

                <Input
                  label="Unit Price (INR)"
                  type="number"
                  step="0.01"
                  value={unitPrice}
                  onChange={(e) => setUnitPrice(e.target.value)}
                />

                <Select
                  label="Order Priority"
                  value={priority}
                  onChange={(e) => setPriority(e.target.value)}
                >
                  <option value="HIGH">High Priority</option>
                  <option value="MEDIUM">Medium Priority</option>
                  <option value="LOW">Low Priority</option>
                </Select>

                <Select
                  label="Intake Channel"
                  value={channel}
                  onChange={(e) => setChannel(e.target.value)}
                >
                  <option value="EDI">Customer EDI</option>
                  <option value="PORTAL">B2B Portal</option>
                  <option value="DIRECT">Direct Account Rep</option>
                </Select>

                <Input
                  label="Ship-to Location"
                  value={shipTo}
                  onChange={(e) => setShipTo(e.target.value)}
                  placeholder="e.g. Central Warehouse, Mumbai"
                />
              </div>

              {error && (
                <div className="inline-error">
                  <AlertTriangle size={15} /> {error}
                </div>
              )}

              <div className="modal-actions">
                <Button type="button" variant="secondary" onClick={onClose} disabled={loading}>
                  Cancel
                </Button>
                <Button type="submit" disabled={loading}>
                  {loading ? (
                    <>Evaluating 7 departments…</>
                  ) : (
                    <><Sparkles size={15} /> Run Agent 2 Assessment</>
                  )}
                </Button>
              </div>
            </form>
          ) : (
            <div className="assessment-results">
              {/* Top Synthesis Banner */}
              <div className={`assessment-summary-banner status-banner-${assessment.overall_status.toLowerCase()}`}>
                <div className="banner-status-col">
                  <span className="banner-label">Overall Feasibility</span>
                  <StatusBadge>{assessment.overall_status.replaceAll('_', ' ')}</StatusBadge>
                  <small>Confidence: <strong>{assessment.confidence_level}</strong></small>
                </div>
                <div className="banner-date-col">
                  <div>
                    <span className="date-label">Requested Target</span>
                    <strong>{formatDate(assessment.requested_delivery_date)}</strong>
                  </div>
                  <div>
                    <span className="date-label">Achievable Estimate</span>
                    <strong className="achievable-date">
                      {assessment.estimated_delivery_date ? formatDate(assessment.estimated_delivery_date) : 'Not Achievable'}
                    </strong>
                  </div>
                  {assessment.days_variance !== null && assessment.days_variance !== undefined && (
                    <div className="variance-tag">
                      {assessment.days_variance <= 0 ? (
                        <span className="variance-ok">On Target ({assessment.days_variance}d)</span>
                      ) : (
                        <span className="variance-delay">+{assessment.days_variance} days variance</span>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* Proposal Submission Notice */}
              {assessment.proposal_id && (
                <div className="approval-notice">
                  <CheckCircle size={16} />
                  <span>
                    Commitment Proposal <strong>#{assessment.proposal_id}</strong> automatically submitted in <strong>PENDING</strong> status. A customer service manager must review and authorize this proposal before order confirmation.
                  </span>
                </div>
              )}

              {/* 7 Department Readiness Grid */}
              <h3 className="section-subheading">7-Department Manufacturing Readiness</h3>
              <div className="department-grid">
                {assessment.readiness_records?.map((dept) => (
                  <div key={dept.department} className={`card dept-card dept-status-${dept.readiness_status.toLowerCase()}`}>
                    <div className="dept-card-header">
                      <div className="dept-title">
                        <span className="dept-icon">{DEPT_ICONS[dept.department] || <Factory size={16} />}</span>
                        <strong>{dept.department}</strong>
                      </div>
                      <StatusBadge>{dept.readiness_status.replaceAll('_', ' ')}</StatusBadge>
                    </div>

                    {dept.identified_issue ? (
                      <div className="dept-issue">
                        <strong>Issue:</strong> {dept.identified_issue}
                      </div>
                    ) : (
                      <div className="dept-ok">
                        <CheckCircle size={13} /> {dept.required_action || 'No blockers detected.'}
                      </div>
                    )}

                    {dept.reason_for_issue && (
                      <div className="dept-reason">
                        <small><strong>Reason:</strong> {dept.reason_for_issue}</small>
                      </div>
                    )}

                    {dept.required_action && dept.identified_issue && (
                      <div className="dept-action">
                        <small><strong>Action:</strong> {dept.required_action}</small>
                      </div>
                    )}

                    <div className="dept-footer">
                      <small>Role: {dept.responsible_role || 'Operations'}</small>
                      {dept.estimated_delay_days > 0 && (
                        <span className="dept-delay-tag">+{dept.estimated_delay_days}d</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {/* Blockers & Corrective Actions */}
              {(assessment.blockers_summary?.length > 0 || assessment.corrective_actions_summary?.length > 0) && (
                <div className="recs-grid">
                  {assessment.blockers_summary?.length > 0 && (
                    <div className="card rec-blocker-card">
                      <h4>Identified Blockers ({assessment.blockers_summary.length})</h4>
                      <ul>
                        {assessment.blockers_summary.map((b, i) => (
                          <li key={i}>{b}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {assessment.corrective_actions_summary?.length > 0 && (
                    <div className="card rec-action-card">
                      <h4>Recommended Corrective Actions ({assessment.corrective_actions_summary.length})</h4>
                      <ul>
                        {assessment.corrective_actions_summary.map((a, i) => (
                          <li key={i}>{a}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              <div className="modal-actions">
                <Button type="button" variant="secondary" onClick={handleReset}>
                  Assess Another Order
                </Button>
                <Button type="button" onClick={onClose}>
                  Done & Close
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
