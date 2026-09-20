import http, { toParams } from './client.js'

// ---- 巡检计划 ----
export const listPlans = (params) => http.get('/inspections/plans', { params: toParams(params) })
export const createPlan = (payload) => http.post('/inspections/plans', payload)
export const updatePlan = (id, payload) => http.put(`/inspections/plans/${id}`, payload)
export const deletePlan = (id) => http.delete(`/inspections/plans/${id}`)
export const dispatchPlan = (id) => http.post(`/inspections/plans/${id}/dispatch`)
export const dispatchAll = () => http.post('/inspections/dispatch')

// ---- 巡检任务 ----
export const listTasks = (params) => http.get('/inspections/tasks', { params: toParams(params) })
export const getTask = (id) => http.get(`/inspections/tasks/${id}`)
export const createTask = (payload) => http.post('/inspections/tasks', payload)
export const startTask = (id, payload = {}) => http.post(`/inspections/tasks/${id}/start`, payload)
export const completeTask = (id, payload) => http.post(`/inspections/tasks/${id}/complete`, payload)
export const cancelTask = (id, payload = {}) => http.post(`/inspections/tasks/${id}/cancel`, payload)

// ---- 待办与统计 ----
export const inspectionTodo = () => http.get('/inspections/todo')
export const inspectionSummary = () => http.get('/inspections/summary')
export const inspectionOptions = () => http.get('/inspections/options')
