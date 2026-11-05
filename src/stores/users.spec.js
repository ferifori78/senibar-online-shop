import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/admin', () => ({
  default: {
    users: vi.fn(),
    userOrders: vi.fn(),
    setUserRole: vi.fn(),
    setUserActive: vi.fn(),
  },
}))

import adminApi from '@/api/admin'
import { useUsersStore } from './users'

const PAGE = {
  count: 2,
  next: null,
  results: [
    { id: 1, email: 'a@example.com', display_name: 'الف', role: 'customer', is_active: true },
    { id: 2, email: 'b@example.com', display_name: 'ب', role: 'roaster', is_active: true },
  ],
}

describe('users store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    adminApi.users.mockResolvedValue({ data: PAGE })
  })

  it('omits empty filters from the query', async () => {
    const users = useUsersStore()
    await users.applyFilters({ role: 'roaster' })

    const params = adminApi.users.mock.calls.at(-1)[0]
    expect(params).toEqual({ page: 1, role: 'roaster' })
    expect(params).not.toHaveProperty('search')
    expect(params).not.toHaveProperty('buyers')
  })

  it('returns to page one when filters change', async () => {
    const users = useUsersStore()
    adminApi.users.mockResolvedValue({ data: { ...PAGE, next: 'x' } })
    await users.fetchUsers()
    await users.loadMore()
    expect(users.page).toBe(2)

    await users.applyFilters({ role: 'admin' })
    expect(users.page).toBe(1)
  })

  it('patches a changed row in place rather than refetching the list', async () => {
    const users = useUsersStore()
    await users.fetchUsers()
    adminApi.users.mockClear()

    adminApi.setUserRole.mockResolvedValue({
      data: { ...PAGE.results[0], role: 'roaster' },
    })
    await users.setRole(1, 'roaster')

    expect(users.users[0].role).toBe('roaster')
    expect(users.users[1].role).toBe('roaster') // untouched
    expect(adminApi.users).not.toHaveBeenCalled()
  })

  it("shows the server's reason when a demotion is refused", async () => {
    const users = useUsersStore()
    adminApi.setUserRole.mockRejectedValue({
      response: { status: 403, data: { detail: 'آخرین ادمین فعال را نمی‌توان تنزل داد.' } },
    })

    const result = await users.setRole(2, 'customer')

    expect(result.ok).toBe(false)
    expect(users.error).toContain('آخرین ادمین')
  })

  it('caches a drill-down so reopening a row costs nothing', async () => {
    const users = useUsersStore()
    adminApi.userOrders.mockResolvedValue({ data: [{ number: 'SN-1' }] })

    await users.fetchUserOrders(1)
    await users.fetchUserOrders(1)

    expect(adminApi.userOrders).toHaveBeenCalledTimes(1)
    expect(users.ordersByUser[1]).toHaveLength(1)
  })

  it('counts only real filters as active, not the search box', async () => {
    const users = useUsersStore()
    await users.applyFilters({ search: 'ali' })
    expect(users.activeFilterCount).toBe(0)

    await users.applyFilters({ role: 'admin', is_active: 'true' })
    expect(users.activeFilterCount).toBe(2)
  })
})
