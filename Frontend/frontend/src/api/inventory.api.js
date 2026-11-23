import { api } from './axios'

export const inventoryApi = {
  async list(params = {}) {
    const queryParams = Object.fromEntries(
      Object.entries(params).filter(([, value]) => value !== '' && value !== undefined && value !== null),
    )
    const { data } = await api.get('/api/inventory/materials', { params: queryParams })
    return data
  },
  async getSummary(materialId) {
    const { data } = await api.get(`/api/inventory/materials/${encodeURIComponent(materialId)}/summary`)
    return data
  },
}
