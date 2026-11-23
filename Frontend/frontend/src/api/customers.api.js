import { api } from './axios'

export const customersApi = {
  async list() {
    const { data } = await api.get('/api/customers')
    return data
  },
  async getById(customerId) {
    const { data } = await api.get(`/api/customers/${encodeURIComponent(customerId)}`)
    return data
  },
}
