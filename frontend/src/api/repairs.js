import http, { toParams } from './client.js'

export const listRepairs = (params) => http.get('/repairs', { params: toParams(params) })
export const getRepair = (id) => http.get(`/repairs/${id}`)
export const createRepair = (payload) => http.post('/repairs', payload)
export const claimRepair = (id, payload = {}) => http.post(`/repairs/${id}/claim`, payload)
export const resolveRepair = (id, payload) => http.post(`/repairs/${id}/resolve`, payload)
export const closeRepair = (id, payload = {}) => http.post(`/repairs/${id}/close`, payload)
export const repairOptions = () => http.get('/repairs/options')
