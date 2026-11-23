import { api } from './axios'

const statusColors = ['#7655d6', '#b49af4', '#f2a66c', '#e47a67', '#ded8eb', '#75a68c']
const formatStatus = (status) => status.toLowerCase().replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())

let cachedSummary = null
let cachedSummaryTimestamp = 0
const SUMMARY_CACHE_TTL = 30000 // 30-second in-memory cache for instant page loads

export const dashboardApi = {
  async getSummary(forceRefresh = false) {
    const now = Date.now()
    if (!forceRefresh && cachedSummary && (now - cachedSummaryTimestamp < SUMMARY_CACHE_TTL)) {
      return cachedSummary
    }

    // Parallelize all calls including trends in ONE concurrent batch
    const [summaryRes, statusRes, riskRes, ordersRes, trendRes] = await Promise.allSettled([
      api.get('/api/dashboard/summary'),
      api.get('/api/dashboard/order-status'),
      api.get('/api/dashboard/at-risk', { params: { page: 1, page_size: 5 } }),
      api.get('/api/orders', { params: { page: 1, page_size: 5, sort_by: 'order_date', sort_order: 'desc' } }),
      api.get('/api/dashboard/trends'),
    ])

    if (summaryRes.status !== 'fulfilled') {
      throw summaryRes.reason
    }

    const summary = summaryRes.value.data
    const orderStatus = statusRes.status === 'fulfilled' && Array.isArray(statusRes.value.data) ? statusRes.value.data : []
    const atRisk = riskRes.status === 'fulfilled' && riskRes.value.data ? riskRes.value.data : { items: [], total_at_risk: 0, actual_delayed: 0, potential_delayed: 0, unknown_risk: 0 }
    const recentOrders = ordersRes.status === 'fulfilled' && ordersRes.value.data ? ordersRes.value.data : { items: [] }

    let trendData = []
    let trendError = ''
    if (trendRes.status === 'fulfilled' && Array.isArray(trendRes.value.data?.trends)) {
      trendData = trendRes.value.data.trends.map((item) => ({
        month: item.week_label,
        orders: item.total_orders,
        delivered: item.delivered_orders,
      }))
    } else {
      trendError = 'Weekly trends are temporarily unavailable.'
    }

    const statusCounts = new Map(orderStatus.map((item) => [item.status, item.count]))
    const kpis = [
      { label: 'Total orders', value: summary.total_orders, icon: 'orders', supportingText: 'Across all order statuses' },
      { label: 'Open orders', value: summary.open_orders, icon: 'open', supportingText: 'Awaiting the next step' },
      { label: 'Delivered orders', value: summary.delivered_orders, icon: 'delivered', supportingText: 'Source order status' },
      {
        label: 'In transit',
        value: statusCounts.get('IN_TRANSIT') ?? null,
        icon: 'transit',
        supportingText: statusCounts.has('IN_TRANSIT') ? 'Source order status' : 'Not reported by the backend',
      },
      { label: 'At-risk orders', value: atRisk.total_at_risk ?? summary.delayed_orders_count ?? 0, icon: 'risk', supportingText: `${atRisk.actual_delayed ?? 0} delayed · ${atRisk.potential_delayed ?? 0} potential · ${atRisk.unknown_risk ?? 0} unknown` },
    ]

    const result = {
      kpis,
      statusData: orderStatus.map((item, index) => ({
        name: formatStatus(item.status),
        value: item.count,
        color: statusColors[index % statusColors.length],
        sourceStatus: item.status,
      })),
      atRisk,
      riskOrders: atRisk.items || [],
      recentOrders: recentOrders.items || [],
      trendData,
      trendError,
      trendLabel: trendError ? 'UNAVAILABLE' : 'LIVE WEEKLY DATA',
      trendDescription: trendError ? 'Weekly trend data could not be loaded.' : 'Weekly order volume and delivered orders from the backend.',
      totalOrders: summary.total_orders,
      openOrders: summary.open_orders,
      deliveredOrders: summary.delivered_orders,
      inTransitOrders: statusCounts.get('IN_TRANSIT') ?? 0,
      atRiskOrders: atRisk.total_at_risk ?? summary.delayed_orders_count ?? 0,
      slide18Kpis: {
        totalOrderValueINR: summary.total_order_value_inr,
        totalShippedValueINR: summary.total_shipped_value_inr,
        onTimeDeliveryRatePct: summary.on_time_delivery_rate_pct,
        missingPOCount: summary.data_quality_missing_po_count,
      },
      deliveryPerformance: {
        customerPerformance: [],
        carrierPerformance: [],
      },
      overdueOrders: [],
    }

    cachedSummary = result
    cachedSummaryTimestamp = Date.now()
    return result
  },

  async getDeliveryPerformance() {
    const { data } = await api.get('/api/dashboard/delivery-performance')
    return data
  },

  async getAnalytics() {
    const { data } = await api.get('/api/dashboard/analytics')
    return data
  },

  async getOrdersProgress() {
    const { data } = await api.get('/api/dashboard/orders-progress')
    return data
  },
}
