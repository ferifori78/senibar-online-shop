import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import authApi from '@/api/auth'
import { configureClient, parseApiError } from '@/api/client'

const STORAGE_KEY = 'senobar.auth'

function readStored() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {}
  } catch {
    return {}
  }
}

function persist(tokens) {
  try {
    if (tokens?.access) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(tokens))
    } else {
      localStorage.removeItem(STORAGE_KEY)
    }
  } catch {
    // Private browsing or blocked storage — the session simply won't survive
    // a reload. Not worth failing the login over.
  }
}

export const useAuthStore = defineStore('auth', () => {
  const stored = readStored()

  const access = ref(stored.access || null)
  const refresh = ref(stored.refresh || null)
  const user = ref(null)

  const loading = ref(false)
  const error = ref('')
  const fieldErrors = ref({})
  // True until the first hydrate() settles, so router guards don't bounce a
  // signed-in user to /login just because the profile hasn't loaded yet.
  const initializing = ref(Boolean(stored.access))

  const isAuthenticated = computed(() => Boolean(access.value))
  // The admin panel compares rows against the signed-in account, so it never
  // offers a control that would strand the person using it.
  const userId = computed(() => user.value?.id ?? null)
  const isStaff = computed(() => ['admin', 'roaster'].includes(user.value?.role))
  const displayName = computed(() => user.value?.display_name || '')

  function setTokens({ access: newAccess, refresh: newRefresh }) {
    access.value = newAccess ?? access.value
    // Rotation returns a new refresh token; keep the old one if it doesn't.
    refresh.value = newRefresh ?? refresh.value
    persist({ access: access.value, refresh: refresh.value })
  }

  function clear() {
    access.value = null
    refresh.value = null
    user.value = null
    persist(null)
  }

  function resetErrors() {
    error.value = ''
    fieldErrors.value = {}
  }

  function captureError(err) {
    const parsed = parseApiError(err)
    error.value = parsed.message
    fieldErrors.value = parsed.fields
    return parsed
  }

  /** Runs one auth request with shared loading/error handling. */
  async function run(request) {
    loading.value = true
    resetErrors()
    try {
      const { data } = await request()
      setTokens(data)
      user.value = data.user
      return { ok: true, data }
    } catch (err) {
      captureError(err)
      return { ok: false, error: err }
    } finally {
      loading.value = false
    }
  }

  const login = (credentials) => run(() => authApi.login(credentials))
  const register = (payload) => run(() => authApi.register(payload))

  /** Ask for a code. Does not sign anyone in, so it bypasses `run`, which
   *  would try to read tokens out of the response. */
  async function requestCode(phone) {
    loading.value = true
    resetErrors()
    try {
      const { data } = await authApi.requestCode(phone)
      return { ok: true, data }
    } catch (err) {
      const parsed = captureError(err)
      return {
        ok: false,
        error: err,
        // The server says how long to wait; the form disables its button for
        // exactly that long rather than guessing.
        retryAfter: err?.response?.data?.retry_after ?? null,
        message: parsed.message,
      }
    } finally {
      loading.value = false
    }
  }

  /** Exchange a code for tokens, creating the account if the number is new. */
  const verifyCode = (payload) => run(() => authApi.verifyCode(payload))

  async function logout() {
    const token = refresh.value
    clear()
    if (token) {
      // Fire and forget: the client is already signed out either way.
      authApi.logout(token).catch(() => {})
    }
  }

  /** Load the profile for an existing token. Called once at app start. */
  async function hydrate() {
    if (!access.value) {
      initializing.value = false
      return
    }
    try {
      const { data } = await authApi.profile()
      user.value = data
    } catch {
      // The interceptor already tried to refresh; if we're here, it failed.
      clear()
    } finally {
      initializing.value = false
    }
  }

  async function updateProfile(payload) {
    loading.value = true
    resetErrors()
    try {
      const { data } = await authApi.updateProfile(payload)
      user.value = data
      return { ok: true, data }
    } catch (err) {
      captureError(err)
      return { ok: false, error: err }
    } finally {
      loading.value = false
    }
  }

  // Hand the client its token hooks. Done here so client.js never imports the
  // store, which would be circular.
  configureClient({
    getTokens: () => ({ access: access.value, refresh: refresh.value }),
    setTokens,
    onUnauthorized: clear,
  })

  return {
    access,
    refresh,
    user,
    loading,
    error,
    fieldErrors,
    initializing,
    isAuthenticated,
    userId,
    isStaff,
    displayName,
    setTokens,
    login,
    register,
    logout,
    requestCode,
    verifyCode,
    hydrate,
    updateProfile,
    resetErrors,
  }
})
