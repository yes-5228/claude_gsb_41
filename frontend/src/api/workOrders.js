import http, { toParams } from './client.js'

export const listWorkOrders = (params) =>
  http.get('/work-orders/', { params: toParams(params) })
export const getWorkOrder = (id) => http.get(`/work-orders/${id}`)
export const createWorkOrder = (payload) => http.post('/work-orders/', payload)
export const updateWorkOrder = (id, payload) => http.patch(`/work-orders/${id}`, payload)
export const workOrderOptions = () => http.get('/work-orders/options')
export const workOrderSummary = (params) =>
  http.get('/work-orders/summary', { params: toParams(params) })
