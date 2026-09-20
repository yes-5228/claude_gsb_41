import http, { toParams } from './client.js'

// ---- 巡检计划 ----
export const listPlans = (params) => http.get('/inspections/plans', { params: toParams(params) })
export const createPlan = (payload) => http.post('/inspections/plans', payload)
export const updatePlan = (id, payload) => http.put(`/inspections/plans/${id}`, payload)
export const deletePlan = (id) => http.delete(`/inspections/plans/${id}`)
export const dispatchPlan = (id) => http.post(`/inspections/plans/${id}/dispatch`)
export const dispatchDue = () => http.post('/inspections/dispatch-due')

// ---- 巡检任务 ----
export const listTasks = (params) => http.get('/inspections/tasks', { params: toParams(params) })
export const getTask = (id) => http.get(`/inspections/tasks/${id}`)
export const createTask = (payload) => http.post('/inspections/tasks', payload)
export const startTask = (id, payload = {}) => http.post(`/inspections/tasks/${id}/start`, payload)
export const submitTask = (id, payload = {}) => http.post(`/inspections/tasks/${id}/submit`, payload)
export const recordTaskItem = (taskId, itemId, payload) =>
  http.put(`/inspections/tasks/${taskId}/items/${itemId}`, payload)
export const convertItemToWorkOrder = (taskId, itemId, payload = {}) =>
  http.post(`/inspections/tasks/${taskId}/items/${itemId}/convert`, payload)

// ---- 目录 / 选项 / 统计 ----
export const inspectionCatalog = () => http.get('/inspections/catalog')
export const inspectionOptions = () => http.get('/inspections/options')
export const taskSummary = (params) =>
  http.get('/inspections/tasks/summary', { params: toParams(params) })
export const todoCounts = () => http.get('/inspections/todo-counts')
