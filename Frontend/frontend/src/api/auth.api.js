import { api, setAccessToken, clearTokens } from './axios'

export const authApi = {
  async login(credentials) {
    const { data } = await api.post('/api/auth/login', credentials)
    if (!data.access_token) throw new Error('Login response did not include an access token.')
    setAccessToken(data.access_token)
    return data.user
  },

  async logout() {
    try {
      await api.post('/api/auth/logout')
    } finally {
      clearTokens()
    }
  },

  async refresh() {
    const { data } = await api.post('/api/auth/refresh')
    if (!data.access_token) throw new Error('Refresh response did not include an access token.')
    setAccessToken(data.access_token)
    return data.user
  },

  async me() {
    const { data } = await api.get('/api/auth/me')
    return data
  },

  // =========================================================================
  // RBAC: USER MANAGEMENT (ADMINISTRATOR ONLY)
  // =========================================================================
  async listUsers() {
    const { data } = await api.get('/api/auth/users')
    return data
  },

  async createUser(payload) {
    const { data } = await api.post('/api/auth/users', payload)
    return data
  },

  async updateUser(userId, payload) {
    const { data } = await api.put(`/api/auth/users/${encodeURIComponent(userId)}`, payload)
    return data
  },

  async deactivateUser(userId) {
    const { data } = await api.delete(`/api/auth/users/${encodeURIComponent(userId)}`)
    return data
  },

  // =========================================================================
  // RBAC: DEPARTMENT MAPPINGS & CONTACT CONFIGURATION (ADMINISTRATOR)
  // =========================================================================
  async listDepartmentMappings() {
    const { data } = await api.get('/api/auth/department-mappings')
    return data
  },

  async updateDepartmentMapping(mappingId, payload) {
    const { data } = await api.put(`/api/auth/department-mappings/${encodeURIComponent(mappingId)}`, payload)
    return data
  },

  async listDepartmentContacts() {
    const { data } = await api.get('/api/auth/department-contacts')
    return data
  },

  async updateDepartmentContact(payload) {
    const { data } = await api.post('/api/auth/department-contacts', payload)
    return data
  },
}
