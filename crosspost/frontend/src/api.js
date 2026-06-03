import axios from 'axios'

const api = axios.create({ baseURL: '/api', timeout: 30000 })

export const fetchPlatforms = () => api.get('/platforms').then(r => r.data)
export const fetchAccounts  = (platform) => api.get('/accounts', { params: platform ? { platform } : {} }).then(r => r.data)
export const fetchPosts     = (limit = 50) => api.get('/posts', { params: { limit } }).then(r => r.data)
export const startLogin     = (platform, account) => api.post('/login/start', { platform, account }).then(r => r.data)
export const doPublish      = (payload) => api.post('/publish', payload).then(r => r.data)

/**
 * Subscribe to the SSE login stream. `onMessage` receives parsed JSON for
 * each event (`{event: 'qrcode'|'done'|'error'|'timeout', ...}`).
 * Returns the EventSource so the caller can `.close()` it.
 */
export function subscribeLogin(taskId, onMessage) {
  const es = new EventSource(`/api/login/stream/${taskId}`)
  es.onmessage = (ev) => {
    try { onMessage(JSON.parse(ev.data)) } catch (e) { console.error('bad SSE payload', ev.data) }
  }
  es.onerror = () => es.close()
  return es
}
