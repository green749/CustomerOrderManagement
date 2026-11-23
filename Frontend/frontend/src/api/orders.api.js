import { api } from './axios'

export const ordersApi = {
  async list(params, options = {}) {
    const queryParams = Object.fromEntries(
      Object.entries(params).filter(([, value]) => value !== '' && value !== undefined && value !== null),
    )
    const { data } = await api.get('/api/orders', { params: queryParams, ...options })
    return data
  },
  async getById(orderId) {
    const { data } = await api.get(`/api/orders/${encodeURIComponent(orderId)}`)
    return data
  },
  async getTimeline(orderId) {
    const { data } = await api.get(`/api/orders/${encodeURIComponent(orderId)}/timeline`)
    return data
  },
  async getEvents(orderId) {
    const data = await this.getTimeline(orderId)
    return data?.events || (Array.isArray(data) ? data : [])
  },
  async getAgentTimeline(orderId) {
    const { data } = await api.get(`/api/orders/${encodeURIComponent(orderId)}/agent-timeline`)
    return data
  },
  async listOverdue(params = {}) {
    const { data } = await api.get('/api/orders/overdue', { params })
    return data
  },
  async getAtpCtp(orderId) {
    const { data } = await api.get(`/api/orders/${encodeURIComponent(orderId)}/atp-ctp`)
    return data
  },
  async getPromiseRecommendation(orderId) {
    const { data } = await api.get(`/api/orders/${encodeURIComponent(orderId)}/promise-recommendation`)
    return data
  },
  async createCommitmentProposal(orderId, payload = {}) {
    const { data } = await api.post(`/api/orders/${encodeURIComponent(orderId)}/commitment-proposals`, payload)
    return data
  },
  async getStatusDraft(orderId) {
    const { data } = await api.get(`/api/orders/${encodeURIComponent(orderId)}/status-draft`)
    return data
  },
  async getEscalationPack(orderId) {
    const { data } = await api.get(`/api/orders/${encodeURIComponent(orderId)}/escalation-pack`)
    return data
  },
}
