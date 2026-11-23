import { api } from './axios'

function getListResponse(data, resource) {
  const items = Array.isArray(data) ? data : data?.items
  if (!Array.isArray(items)) throw new Error(`The ${resource} response did not contain a list.`)
  return items
}

export const agentApi = {
  async sendMessage(message, conversationId) {
    const { data } = await api.post(
      '/api/agent/chat',
      {
        message,
        conversation_id: conversationId,
      },
      { timeout: 120000 }
    )
    return data
  },
  async getConversations() {
    const { data } = await api.get('/api/conversations')
    return getListResponse(data, 'conversations')
  },
  async getMessages(conversationId) {
    const { data } = await api.get(`/api/conversations/${encodeURIComponent(conversationId)}/messages`)
    return getListResponse(data, 'conversation messages')
  },
}
