import axios from 'axios'

// In development Vite proxies /api to the Django server (see vite.config.js).
// Set VITE_API_URL to call a backend on another origin.
const baseURL = import.meta.env.VITE_API_URL || '/api'

const ACCESS_KEY = 'dnd.access'
const REFRESH_KEY = 'dnd.refresh'
const EMAIL_KEY = 'dnd.email'

function read(key) {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function write(key, value) {
  try {
    if (value == null) localStorage.removeItem(key)
    else localStorage.setItem(key, value)
  } catch {
    // Storage can be unavailable (private mode); the session then lasts until reload.
  }
}

export const tokens = {
  get access() {
    return read(ACCESS_KEY)
  },
  get refresh() {
    return read(REFRESH_KEY)
  },
  get email() {
    return read(EMAIL_KEY)
  },
  save({ access, refresh, email }) {
    if (access !== undefined) write(ACCESS_KEY, access)
    if (refresh !== undefined) write(REFRESH_KEY, refresh)
    if (email !== undefined) write(EMAIL_KEY, email)
  },
  clear() {
    write(ACCESS_KEY, null)
    write(REFRESH_KEY, null)
    write(EMAIL_KEY, null)
  },
}

export const api = axios.create({ baseURL })

api.interceptors.request.use((config) => {
  const access = tokens.access
  if (access) config.headers.Authorization = `Bearer ${access}`
  return config
})

// Listeners are told when the session ends so the app can return to the login screen.
const logoutListeners = new Set()
export function onLogout(listener) {
  logoutListeners.add(listener)
  return () => logoutListeners.delete(listener)
}

let refreshing = null

// Access tokens last 30 minutes (SRS 6.3). On a 401, refresh once and retry the request.
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config
    const expired = error.response?.status === 401 && original && !original._retried
    if (!expired || !tokens.refresh || original.url?.startsWith('/auth/')) {
      if (error.response?.status === 401 && !original?.url?.startsWith('/auth/login')) {
        tokens.clear()
        logoutListeners.forEach((listener) => listener())
      }
      throw error
    }
    original._retried = true
    try {
      refreshing ??= axios
        .post(`${baseURL}/auth/refresh/`, { refresh: tokens.refresh })
        .then(({ data }) => tokens.save({ access: data.access, refresh: data.refresh }))
        .finally(() => {
          refreshing = null
        })
      await refreshing
      return api(original)
    } catch (refreshError) {
      tokens.clear()
      logoutListeners.forEach((listener) => listener())
      throw refreshError
    }
  },
)

// Turns a DRF error response into one readable sentence for the UI.
export function errorMessage(error, fallback = 'Something went wrong. Please try again.') {
  const data = error?.response?.data
  if (!data) return error?.message === 'Network Error' ? 'Cannot reach the server. Is the backend running?' : fallback
  if (typeof data === 'string') return fallback
  if (data.detail) return String(data.detail)
  const first = Object.entries(data)[0]
  if (!first) return fallback
  const [field, value] = first
  const text = Array.isArray(value) ? value[0] : typeof value === 'object' ? JSON.stringify(value) : value
  return field === 'non_field_errors' ? String(text) : `${field.replaceAll('_', ' ')}: ${text}`
}

// List endpoints are paginated ({results: [...]}); a few return a plain array.
export function listOf(data) {
  return Array.isArray(data) ? data : (data?.results ?? [])
}
