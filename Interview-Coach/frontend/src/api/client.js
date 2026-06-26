import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 600000, // 10 min — 3-stage AI pipeline (GPT → Claude → Gemini) can take 3-5 min
  headers: { 'Content-Type': 'application/json' },
})

// ── Sessions ──────────────────────────────────────────────────────
export const listSessions = () => api.get('/sessions/')
export const getSession = (id) => api.get(`/sessions/${id}`)
export const deleteSession = (id) => api.delete(`/sessions/${id}`)
export const getSessionChain = (id) => api.get(`/sessions/${id}/chain`)

// ── Interview ─────────────────────────────────────────────────────
export const setupInterview = (data) => api.post('/interview/setup', data)
export const getInterviewStatus = (id) => api.get(`/interview/${id}/status`)
export const getInterview = (id) => api.get(`/interview/${id}`)
export const submitAnswer = (sessionId, questionId, answer) =>
  api.post(`/interview/${sessionId}/answer/${questionId}`, { answer })
export const getFeedback = (sessionId, questionId) =>
  api.post(`/interview/${sessionId}/feedback/${questionId}`)
export const completeSession = (sessionId) =>
  api.post(`/interview/${sessionId}/complete`)
export const getReport = (sessionId) => api.get(`/interview/${sessionId}/report`)
export const reattemptSession = (sessionId) =>
  api.post(`/interview/${sessionId}/reattempt`)

// ── Dashboard ─────────────────────────────────────────────────────
export const getDashboardStats = () => api.get('/dashboard/stats')
export const getDashboardSessions = () => api.get('/dashboard/sessions')

// ── Health ────────────────────────────────────────────────────────
export const checkHealth = () => api.get('/health')

export default api
