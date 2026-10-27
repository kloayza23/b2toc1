const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

export const session = {
  get token() { return localStorage.getItem('b2toc1_token') },
  set token(value) { value ? localStorage.setItem('b2toc1_token', value) : localStorage.removeItem('b2toc1_token') },
}

export async function api(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(session.token ? { Authorization: `Bearer ${session.token}` } : {}), ...options.headers },
  })
  if (response.status === 401) {
    session.token = null
    window.dispatchEvent(new Event('session-expired'))
  }
  const data = response.status === 204 ? null : await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map(item => item.msg).join('. ') : data.detail
    throw new Error(detail || 'No pudimos completar la solicitud')
  }
  return data
}

