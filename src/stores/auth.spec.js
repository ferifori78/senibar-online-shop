import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/auth', () => ({
  default: {
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(() => Promise.resolve({ data: {} })),
    profile: vi.fn(),
    updateProfile: vi.fn(),
  },
}))

import authApi from '@/api/auth'
import { useAuthStore } from './auth'

const TOKENS = {
  access: 'access-1',
  refresh: 'refresh-1',
  user: { id: 1, email: 'a@b.c', display_name: 'Ali', role: 'customer' },
}

function apiError(status, data) {
  return Object.assign(new Error('request failed'), { response: { status, data } })
}

describe('auth store', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    setActivePinia(createPinia())
  })

  it('stores tokens and user on login', async () => {
    authApi.login.mockResolvedValue({ data: TOKENS })
    const auth = useAuthStore()

    const result = await auth.login({ email: 'a@b.c', password: 'pw' })

    expect(result.ok).toBe(true)
    expect(auth.isAuthenticated).toBe(true)
    expect(auth.displayName).toBe('Ali')
    expect(auth.loading).toBe(false)
    expect(JSON.parse(localStorage.getItem('senobar.auth')).access).toBe('access-1')
  })

  it('surfaces field errors from the server without authenticating', async () => {
    authApi.register.mockRejectedValue(
      apiError(400, { email: ['A user with this email already exists.'] }),
    )
    const auth = useAuthStore()

    const result = await auth.register({ email: 'a@b.c' })

    expect(result.ok).toBe(false)
    expect(auth.isAuthenticated).toBe(false)
    expect(auth.fieldErrors.email).toContain('already exists')
    expect(auth.loading).toBe(false)
  })

  it('reads detail as a banner message, not a field error', async () => {
    authApi.login.mockRejectedValue(apiError(401, { detail: 'No active account found.' }))
    const auth = useAuthStore()

    await auth.login({ email: 'a@b.c', password: 'nope' })

    expect(auth.error).toBe('No active account found.')
    expect(auth.fieldErrors).toEqual({})
  })

  it('clears everything on logout and revokes the refresh token', async () => {
    authApi.login.mockResolvedValue({ data: TOKENS })
    const auth = useAuthStore()
    await auth.login({ email: 'a@b.c', password: 'pw' })

    await auth.logout()

    expect(auth.isAuthenticated).toBe(false)
    expect(auth.user).toBeNull()
    expect(localStorage.getItem('senobar.auth')).toBeNull()
    expect(authApi.logout).toHaveBeenCalledWith('refresh-1')
  })

  it('restores a session from storage and loads the profile', async () => {
    localStorage.setItem(
      'senobar.auth',
      JSON.stringify({ access: 'access-1', refresh: 'refresh-1' }),
    )
    authApi.profile.mockResolvedValue({ data: TOKENS.user })
    const auth = useAuthStore()

    expect(auth.initializing).toBe(true)
    await auth.hydrate()

    expect(auth.initializing).toBe(false)
    expect(auth.user.email).toBe('a@b.c')
  })

  it('drops a stored session whose token no longer works', async () => {
    localStorage.setItem('senobar.auth', JSON.stringify({ access: 'stale', refresh: 'stale' }))
    authApi.profile.mockRejectedValue(apiError(401, { detail: 'Token is invalid.' }))
    const auth = useAuthStore()

    await auth.hydrate()

    expect(auth.isAuthenticated).toBe(false)
    expect(localStorage.getItem('senobar.auth')).toBeNull()
  })

  it('keeps the existing refresh token when a response omits it', async () => {
    authApi.login.mockResolvedValue({ data: TOKENS })
    const auth = useAuthStore()
    await auth.login({ email: 'a@b.c', password: 'pw' })

    // A plain /refresh/ response without rotation returns only `access`.
    auth.$patch({})
    const { setTokens } = auth
    setTokens({ access: 'access-2' })

    expect(auth.access).toBe('access-2')
    expect(auth.refresh).toBe('refresh-1')
  })

  it('marks staff roles distinctly from customers', async () => {
    authApi.login.mockResolvedValue({
      data: { ...TOKENS, user: { ...TOKENS.user, role: 'roaster' } },
    })
    const auth = useAuthStore()
    await auth.login({ email: 'a@b.c', password: 'pw' })

    expect(auth.isStaff).toBe(true)
  })
})
