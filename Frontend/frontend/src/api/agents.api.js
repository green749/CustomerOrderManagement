import { api, getAccessToken } from './axios'

async function consumeFeasibilityStream(url, body, onEvent) {
  const baseURL = api.defaults.baseURL || ''
  const token = getAccessToken()
  const headers = {
    'Content-Type': 'application/json',
    Accept: 'text/event-stream',
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  const resp = await fetch(`${baseURL}${url}`, {
    method: 'POST',
    headers,
    credentials: 'include',
    body: body ? JSON.stringify(body) : undefined,
  })

  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`
    try {
      const errJson = await resp.json()
      detail = errJson?.detail || errJson?.message || detail
    } catch {}
    throw new Error(detail)
  }

  if (!resp.body) {
    throw new Error('Streaming response body unavailable.')
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let completedAssessment = null

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() || ''

    for (const chunk of parts) {
      const lines = chunk.split('\n')
      for (const rawLine of lines) {
        const line = rawLine.trim()
        if (!line.startsWith('data:')) continue
        const jsonStr = line.slice(5).trim()
        if (!jsonStr) continue
        let evt
        try {
          evt = JSON.parse(jsonStr)
        } catch {
          continue
        }
        if (evt.event === 'error') {
          throw new Error(evt.detail || 'Agent 2 feasibility assessment failed.')
        }
        if (evt.event === 'complete') {
          completedAssessment = evt.assessment
        }
        if (onEvent) {
          onEvent(evt)
        }
      }
    }
  }

  if (!completedAssessment) {
    throw new Error('Assessment stream ended before completion.')
  }
  return completedAssessment
}

export const agentsApi = {
  // =========================================================================
  // AGENT 2 – FEASIBILITY & READINESS ASSESSMENTS
  // =========================================================================
  async assessNewOrder(payload) {
    const { data } = await api.post('/api/assessments', payload, { timeout: 120000 })
    return data
  },

  async assessNewOrderStream(payload, onEvent) {
    return consumeFeasibilityStream('/api/assessments/stream', payload, onEvent)
  },

  async reassessOrder(assessmentId) {
    const { data } = await api.post(`/api/assessments/${encodeURIComponent(assessmentId)}/reassess`, null, { timeout: 120000 })
    return data
  },

  async reassessOrderStream(assessmentId, onEvent) {
    return consumeFeasibilityStream(`/api/assessments/${encodeURIComponent(assessmentId)}/reassess/stream`, null, onEvent)
  },

  async listAssessments(params = {}) {
    const { data } = await api.get('/api/assessments', { params })
    return data
  },

  async getAssessmentsSummary() {
    const { data } = await api.get('/api/assessments/summary')
    return data
  },

  async getAssessment(assessmentId) {
    const { data } = await api.get(`/api/assessments/${encodeURIComponent(assessmentId)}`)
    return data
  },

  async getAssessmentDepartments(assessmentId) {
    const { data } = await api.get(`/api/assessments/${encodeURIComponent(assessmentId)}/departments`)
    return data
  },

  // =========================================================================
  // AGENT 3 – ORDER MONITORING & RISK ALERTS
  // =========================================================================
  async activateMonitoring(payload) {
    const { data } = await api.post('/api/monitoring/activate', payload)
    return data
  },

  async listMonitoringRecords(params = {}) {
    const { data } = await api.get('/api/monitoring/records', { params })
    return data
  },

  async getMonitoringRecord(customerOrderId) {
    const { data } = await api.get(`/api/monitoring/records/${encodeURIComponent(customerOrderId)}`)
    return data
  },

  async runMonitoringCycle() {
    const { data } = await api.post('/api/monitoring/run-cycle', null, { timeout: 240000 })
    return data
  },

  async triggerSurveillance() {
    const { data } = await api.post('/api/monitoring/run-cycle', null, { timeout: 240000 })
    return data
  },

  async listMonitoringLogs(limit = 20) {
    const { data } = await api.get('/api/monitoring/logs', { params: { limit } })
    return data
  },

  // =========================================================================
  // RISK ALERTS & NOTIFICATIONS
  // =========================================================================
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

  async recordCustomerCommunication(alertId, notes) {
    const { data } = await api.post(`/api/alerts/${encodeURIComponent(alertId)}/customer-communication`, {
      customer_communication_notes: notes,
      customer_communicated: true,
    })
    return data
  },

  async listNotifications(params = {}) {
    const { data } = await api.get('/api/alerts/notifications', { params })
    return data
  },

  async retryNotification(logId) {
    const { data } = await api.post(`/api/alerts/notifications/${encodeURIComponent(logId)}/retry`)
    return data
  },

  async retryAllFailedNotifications() {
    const { data } = await api.post('/api/alerts/notifications/retry-failed')
    return data
  },

  async listDepartmentContacts() {
    const { data } = await api.get('/api/alerts/contacts')
    return data
  },

  async dispatchAlertNotification(alertId) {
    const { data } = await api.post(`/api/alerts/${encodeURIComponent(alertId)}/dispatch-notification`)
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

  async sendTestNotification({ recipient_email, recipient_category = 'CUSTOMER_SERVICE' }) {
    const { data } = await api.post('/api/alerts/test-notification', {
      recipient_email,
      recipient_category,
    })
    return data
  },

  async getSmtpConfig() {
    const { data } = await api.get('/api/auth/smtp-config')
    return data
  },

  async updateSmtpConfig(config) {
    const { data } = await api.post('/api/auth/smtp-config', config)
    return data
  },

  // =========================================================================
  // AGENT 3 CORRECTIVE ACTIONS
  // =========================================================================
  async listActions(params = {}) {
    const { data } = await api.get('/api/actions', { params })
    return data
  },

  async getAction(actionId) {
    const { data } = await api.get(`/api/actions/${encodeURIComponent(actionId)}`)
    return data
  },

  async approveAction(actionId, payload = {}) {
    const { data } = await api.post(`/api/actions/${encodeURIComponent(actionId)}/approve`, payload)
    return data
  },

  async rejectAction(actionId, payload = {}) {
    const { data } = await api.post(`/api/actions/${encodeURIComponent(actionId)}/reject`, payload)
    return data
  },

  // =========================================================================
  // AUTONOMOUS AGENT GOVERNANCE & CONTROLS (ADMIN)
  // =========================================================================
  async getAgentsOverview() {
    const { data } = await api.get('/api/admin/agents/overview')
    return data
  },

  async pauseAgent(agentName, reason = '') {
    const { data } = await api.post(`/api/admin/agents/${encodeURIComponent(agentName)}/pause`, { reason })
    return data
  },

  async resumeAgent(agentName) {
    const { data } = await api.post(`/api/admin/agents/${encodeURIComponent(agentName)}/resume`)
    return data
  },

  async getAgentPerformanceKpis() {
    const { data } = await api.get('/api/kpis/agent-performance')
    return data
  },

  // =========================================================================
  // LIVE AGENT RUNS & STATUS
  // =========================================================================
  async getAgentStatus() {
    const { data } = await api.get('/api/agents/status')
    return data
  },

  async getAgentRuns(params = {}) {
    const { data } = await api.get('/api/agents/runs', { params })
    return data
  },
}

