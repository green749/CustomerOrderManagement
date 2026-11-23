export const formatDate = (value) => {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? '—'
    : new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric', year: 'numeric' }).format(date)
}

export const formatNumber = (value) => new Intl.NumberFormat('en').format(value ?? 0)

export const formatINR = (value) => value == null
  ? '—'
  : new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(Number(value))

export const getErrorMessage = (error, fallback = 'Something went wrong. Please try again.') => {
  const payload = error?.response?.data
  const details = Array.isArray(payload?.details)
    ? payload.details.map((item) => {
      if (typeof item === 'string') return item
      if (item && typeof item.msg === 'string') return item.msg
      return JSON.stringify(item)
    }).join(' ')
    : ''
  const serverMessage = payload?.error ?? payload?.detail ?? payload?.message
  if (serverMessage) return details ? `${serverMessage} ${details}` : serverMessage
  if (details) return details
  if (error?.code === 'ECONNABORTED') return 'The request timed out. Please try again.'
  if (error?.message === 'Network Error') return 'Unable to reach the service. Check your connection and API configuration.'
  return error?.message || fallback
}
