import { api } from './axios'

export const workflowApi = {
  async listProposals(params = {}) {
    const { data } = await api.get('/api/commitment-proposals', { params })
    if (!Array.isArray(data)) throw new Error('Commitment proposal response did not contain a list.')
    return data
  },
  async approveProposal(proposalId, decisionNote) {
    const { data } = await api.post(`/api/commitment-proposals/${encodeURIComponent(proposalId)}/approve`, {
      decision_note: decisionNote,
    })
    return data
  },
  async rejectProposal(proposalId, decisionNote) {
    const { data } = await api.post(`/api/commitment-proposals/${encodeURIComponent(proposalId)}/reject`, {
      decision_note: decisionNote,
    })
    return data
  },
  async decideProposal(proposalId, payload = {}) {
    const decision = (payload.decision || 'APPROVED').toUpperCase()
    const note = payload.decision_note || payload.review_notes || ''
    if (decision === 'REJECTED' || decision === 'REJECT') {
      return this.rejectProposal(proposalId, note)
    }
    return this.approveProposal(proposalId, note)
  },
  async getAllocationProposal(productId) {
    const params = productId ? { product_id: productId } : {}
    const { data } = await api.get('/api/allocation/proposal', { params })
    if (
      !Array.isArray(data?.allocations)
      || ['total_usable_inventory_units', 'total_demanded_units', 'total_allocated_units', 'total_unfulfilled_units']
        .some((field) => typeof data[field] !== 'number')
    ) {
      throw new Error('Allocation response did not match the backend proposal schema.')
    }
    return data
  },
  async getKpis(params = {}) {
    const { data } = await api.get('/api/kpis', { params })
    if (data?.expedite_cost && typeof data.expedite_cost.total_expedite_cost_inr !== 'number') {
      data.expedite_cost.total_expedite_cost_inr = Number(data.expedite_cost.total_expedite_cost_inr) || 0
    }
    const requiredNumbers = [
      data?.otif?.otif_rate_pct,
      data?.order_confirmation_time?.average_confirmation_days_proxy,
      data?.schedule_adherence?.schedule_adherence_pct,
      data?.schedule_adherence?.on_time_production_orders,
      data?.schedule_adherence?.total_production_orders,
      data?.promise_date_accuracy?.promise_date_accuracy_pct,
      data?.expedite_cost?.total_expedite_cost_inr,
    ]
    const isNumeric = (val) => typeof val === 'number' && !isNaN(val)
    if (!Array.isArray(data?.backlog_ageing) || !requiredNumbers.every(isNumeric)) {
      throw new Error('KPI response did not match the backend schema.')
    }
    return data
  },
  async getDeliveryPerformance() {
    const { data } = await api.get('/api/dashboard/delivery-performance')
    if (!Array.isArray(data?.customers) || !Array.isArray(data?.carriers)) {
      throw new Error('Delivery performance response did not match the backend schema.')
    }
    return data
  },
  // Agent 2: Feasibility Assessments
  async createAssessment(payload) {
    const { data } = await api.post('/api/assessments', payload)
    return data
  },
  async listAssessments(params = {}) {
    const { data } = await api.get('/api/assessments', { params })
    return data
  },
  async getAssessment(id) {
    const { data } = await api.get(`/api/assessments/${encodeURIComponent(id)}`)
    return data
  },
  // Agent 3: Alerts & Monitoring
  async listAlerts(params = {}) {
    const { data } = await api.get('/api/alerts', { params })
    return data
  },
  async getAlertsSummary() {
    const { data } = await api.get('/api/alerts/summary')
    return data
  },
  async acknowledgeAlert(alertId) {
    const { data } = await api.post(`/api/alerts/${encodeURIComponent(alertId)}/acknowledge`)
    return data
  },
  async assignAlert(alertId, assignedOwner) {
    const { data } = await api.post(`/api/alerts/${encodeURIComponent(alertId)}/assign`, {
      assigned_owner: assignedOwner,
    })
    return data
  },
  async resolveAlert(alertId, resolutionNotes) {
    const { data } = await api.post(`/api/alerts/${encodeURIComponent(alertId)}/resolve`, {
      resolution_notes: resolutionNotes,
    })
    return data
  },
  async checkFollowups(forceSendAll = false) {
    const { data } = await api.post('/api/alerts/check-followups', null, {
      params: { force_send_all: forceSendAll },
    })
    return data
  },
  async sendFollowup(alertId, forceSend = true) {
    const { data } = await api.post(`/api/alerts/${encodeURIComponent(alertId)}/send-followup`, null, {
      params: { force_send: forceSend },
    })
    return data
  },
  async listMonitoringRecords(params = {}) {
    const { data } = await api.get('/api/monitoring/records', { params })
    return data
  },
  async runMonitoringCycle() {
    const { data } = await api.post('/api/monitoring/run-cycle')
    return data
  },
}
