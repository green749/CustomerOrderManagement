import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''
let accessTokenInMemory

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

export const getAccessToken = () => accessTokenInMemory || localStorage.getItem('access_token') || undefined
export const setAccessToken = (accessToken) => {
  accessTokenInMemory = accessToken || undefined
  if (accessToken) {
    localStorage.setItem('access_token', accessToken)
  } else {
    localStorage.removeItem('access_token')
  }
}
export const clearTokens = () => {
  accessTokenInMemory = undefined
  localStorage.removeItem('access_token')
}

api.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

let refreshRequest
let onSessionExpired = () => {}
export const setSessionExpiredHandler = (handler) => {
  onSessionExpired = handler
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config
    const isAuthEndpoint = /\/api\/auth\/(login|refresh|logout)(?:\/|\?|$)/.test(original?.url ?? '')
    if (error.response?.status !== 401 || !original || isAuthEndpoint) return Promise.reject(error)
    if (original._retry) {
      clearTokens()
      onSessionExpired()
      return Promise.reject(error)
    }

    original._retry = true
    try {
      if (!refreshRequest) {
        refreshRequest = api
          .post('/api/auth/refresh')
          .then(({ data }) => {
            const accessToken = data.access_token
            if (!accessToken) throw new Error('Refresh response did not include an access token.')
            setAccessToken(accessToken)
            return accessToken
          })
          .finally(() => {
            refreshRequest = undefined
          })
      }
      const accessToken = await refreshRequest
      original.headers.Authorization = `Bearer ${accessToken}`
      return api(original)
    } catch (refreshError) {
      clearTokens()
      onSessionExpired()
      return Promise.reject(refreshError)
    }
  },
)
