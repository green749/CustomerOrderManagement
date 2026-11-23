import { api } from './axios'

export const connectorsApi = {
  async getStatus() {
    const { data } = await api.get('/api/connectors/status')
    return data
  },

  async testConnection(payload) {
    const { data } = await api.post('/api/connectors/test', payload)
    return data
  },

  async connect(payload) {
    const { data } = await api.post('/api/connectors/connect', payload)
    return data
  },

  async seedData() {
    const { data } = await api.post('/api/connectors/seed')
    return data
  },

  async syncData() {
    const { data } = await api.post('/api/connectors/sync')
    return data
  },

  async getAgentDatabases() {
    const { data } = await api.get('/api/connectors/agent-databases')
    return data
  },

  async getInventoryAgentLive() {
    const { data } = await api.get('/api/connectors/agent-databases/inventory/live')
    return data
  },

  async getVisionAIAgentLive() {
    const { data } = await api.get('/api/connectors/agent-databases/vision-ai/live')
    return data
  },

  async pingAgentDatabase(agentId) {
    const { data } = await api.post(`/api/connectors/agent-databases/ping?agent_id=${encodeURIComponent(agentId)}`)
    return data
  },
}
