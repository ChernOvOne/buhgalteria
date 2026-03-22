import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api

// ── Auth ──────────────────────────────────────────────────────────────────────
export const authAPI = {
  login: (data) => api.post('/auth/login', data),
  me: () => api.get('/auth/me'),
}

// ── Dashboard ─────────────────────────────────────────────────────────────────
export const dashboardAPI = {
  get: () => api.get('/dashboard/'),
}

// ── Transactions ──────────────────────────────────────────────────────────────
export const transactionsAPI = {
  list: (params) => api.get('/transactions/', { params }),
  create: (data) => api.post('/transactions/', data),
  update: (id, data) => api.patch(`/transactions/${id}`, data),
  delete: (id) => api.delete(`/transactions/${id}`),
  uploadReceipt: (id, file) => {
    const fd = new FormData()
    fd.append('file', file)
    return api.post(`/transactions/${id}/receipt`, fd)
  },
  summaryByMonth: (year) => api.get('/transactions/summary/by-month', { params: { year } }),
}

// ── Categories ────────────────────────────────────────────────────────────────
export const categoriesAPI = {
  list: () => api.get('/categories/'),
  create: (data) => api.post('/categories/', data),
  update: (id, data) => api.patch(`/categories/${id}`, data),
  delete: (id) => api.delete(`/categories/${id}`),
  listRules: () => api.get('/categories/auto-rules'),
  createRule: (data) => api.post('/categories/auto-rules', data),
  deleteRule: (id) => api.delete(`/categories/auto-rules/${id}`),
}

// ── Partners ──────────────────────────────────────────────────────────────────
export const partnersAPI = {
  list: () => api.get('/partners/'),
  create: (data) => api.post('/partners/', data),
  get: (id) => api.get(`/partners/${id}`),
  update: (id, data) => api.patch(`/partners/${id}`, data),
  delete: (id) => api.delete(`/partners/${id}`),
  createInkas: (data) => api.post('/partners/inkas', data),
  listInkas: (partner_id) => api.get('/partners/inkas/all', { params: { partner_id } }),
  deleteInkas: (id) => api.delete(`/partners/inkas/${id}`),
}

// ── Servers ───────────────────────────────────────────────────────────────────
export const serversAPI = {
  list: () => api.get('/servers/'),
  create: (data) => api.post('/servers/', data),
  update: (id, data) => api.patch(`/servers/${id}`, data),
  delete: (id) => api.delete(`/servers/${id}`),
}

// ── Ads ───────────────────────────────────────────────────────────────────────
export const adsAPI = {
  list: (params) => api.get('/ads/', { params }),
  create: (data) => api.post('/ads/', data),
  update: (id, data) => api.patch(`/ads/${id}`, data),
  delete: (id) => api.delete(`/ads/${id}`),
  summary: (params) => api.get('/ads/summary', { params }),
}

// ── Recurring ─────────────────────────────────────────────────────────────────
export const recurringAPI = {
  list: () => api.get('/recurring/'),
  create: (data) => api.post('/recurring/', data),
  delete: (id) => api.delete(`/recurring/${id}`),
}

// ── Reports ───────────────────────────────────────────────────────────────────
export const reportsAPI = {
  pdf: (data) => api.post('/reports/pdf', data, { responseType: 'blob' }),
  excel: (data) => api.post('/reports/excel', data, { responseType: 'blob' }),
  quick: (period, format) => api.get(`/reports/quick/${period}`, { params: { format }, responseType: 'blob' }),
}

// ── Settings ──────────────────────────────────────────────────────────────────
export const settingsAPI = {
  get: () => api.get('/settings/'),
  update: (data) => api.patch('/settings/', data),
  onboarding: (data) => api.post('/settings/onboarding', data),
  auditLog: (params) => api.get('/settings/audit-log', { params }),
}

// ── Users ─────────────────────────────────────────────────────────────────────
export const usersAPI = {
  list: () => api.get('/users/'),
  create: (data) => api.post('/users/', data),
  update: (id, data) => api.patch(`/users/${id}`, data),
  changePassword: (id, password) => api.post(`/users/${id}/password`, { new_password: password }),
  delete: (id) => api.delete(`/users/${id}`),
}

// ── Milestones ────────────────────────────────────────────────────────────────
export const milestonesAPI = {
  list: () => api.get('/milestones/'),
  create: (data) => api.post('/milestones/', data),
  delete: (id) => api.delete(`/milestones/${id}`),
}

// ── Monthly Stats ─────────────────────────────────────────────────────────────
export const statsAPI = {
  list: (year) => api.get('/monthly-stats/', { params: { year } }),
  upsert: (year, month, data) => api.put(`/monthly-stats/${year}/${month}`, data),
}

// ── Payments ──────────────────────────────────────────────────────────────────
export const paymentsAPI = {
  list: (params) => api.get('/payments/', { params }),
  get: (id) => api.get(`/payments/${id}`),
  delete: (id) => api.delete(`/payments/${id}`),
  stats: (params) => api.get('/payments/stats/summary', { params }),
  listKeys: () => api.get('/payments/keys/list'),
  createKey: (data) => api.post('/payments/keys', data),
  deleteKey: (id) => api.delete(`/payments/keys/${id}`),
}

// ── Notification channels ─────────────────────────────────────────────────────
export const notifChannelsAPI = {
  list: () => api.get('/notification-channels/'),
  create: (data) => api.post('/notification-channels/', data),
  update: (id, data) => api.patch(`/notification-channels/${id}`, data),
  delete: (id) => api.delete(`/notification-channels/${id}`),
  test: (id) => api.post(`/notification-channels/test/${id}`),
}
