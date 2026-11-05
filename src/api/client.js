import axios from 'axios'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api',
  headers: { 'Content-Type': 'application/json' },
})

// The store owns the tokens; the client only borrows them through these hooks.
// Set at app start by the auth store, so we avoid a circular import.
let tokenProvider = () => null
let onRefreshed = () => {}
let onAuthFailure = () => {}

export function configureClient({ getTokens, setTokens, onUnauthorized }) {
  tokenProvider = getTokens
  onRefreshed = setTokens
  onAuthFailure = onUnauthorized
}

client.interceptors.request.use((config) => {
  const access = tokenProvider()?.access
  if (access && !config.skipAuth) {
    config.headers.Authorization = `Bearer ${access}`
  }
  return config
})

// A single in-flight refresh, shared by every request that got a 401 while it
// was running. Without this, five parallel calls trigger five refreshes and
// rotation invalidates four of them.
let refreshInFlight = null

async function refreshAccessToken() {
  const refresh = tokenProvider()?.refresh
  if (!refresh) throw new Error('No refresh token')

  refreshInFlight ??= client
    .post('/auth/refresh/', { refresh }, { skipAuth: true, skipRetry: true })
    .then(({ data }) => {
      onRefreshed(data)
      return data.access
    })
    .finally(() => {
      refreshInFlight = null
    })

  return refreshInFlight
}

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { config, response } = error

    if (response?.status !== 401 || config?.skipRetry || config?._retried) {
      return Promise.reject(error)
    }

    config._retried = true
    try {
      const access = await refreshAccessToken()
      config.headers.Authorization = `Bearer ${access}`
      return client(config)
    } catch {
      onAuthFailure()
      return Promise.reject(error)
    }
  },
)

/** Flatten DRF's error shape into something a form can render. */
export function parseApiError(error) {
  const data = error?.response?.data

  if (!data) {
    return { message: 'ارتباط با سرور برقرار نشد.', fields: {} }
  }
  if (typeof data === 'string') {
    return { message: data, fields: {} }
  }

  const fields = {}
  let message = ''

  for (const [key, value] of Object.entries(data)) {
    const text = Array.isArray(value) ? value.join(' ') : String(value)
    if (key === 'detail' || key === 'non_field_errors') {
      message = text
    } else {
      fields[key] = text
    }
  }

  return { message: message || (Object.keys(fields).length ? '' : 'خطای ناشناخته.'), fields }
}

export default client
