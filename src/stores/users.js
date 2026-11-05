import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import adminApi from '@/api/admin'
import { useApiErrors } from './errors'

export const useUsersStore = defineStore('adminUsers', () => {
  const users = ref([])
  const count = ref(0)
  const page = ref(1)
  const hasNext = ref(false)

  // The drill-down: one customer's orders, keyed so reopening a row the panel
  // already fetched costs nothing.
  const ordersByUser = ref({})

  const loading = ref(false)
  const acting = ref(false)
  const error = ref('')
  const fieldErrors = ref({})

  const { capture, reset: resetErrors } = useApiErrors(error, fieldErrors)

  const filters = ref({ search: '', role: '', is_active: '', buyers: '' })

  const isEmpty = computed(() => !loading.value && users.value.length === 0)

  const activeFilterCount = computed(
    () => Object.entries(filters.value).filter(([k, v]) => k !== 'search' && v).length,
  )

  function cleanParams() {
    const params = { page: page.value }
    for (const [key, value] of Object.entries(filters.value)) {
      if (value !== '' && value !== null && value !== undefined) params[key] = value
    }
    return params
  }

  async function fetchUsers({ append = false } = {}) {
    loading.value = true
    resetErrors()
    try {
      const { data } = await adminApi.users(cleanParams())
      users.value = append ? [...users.value, ...data.results] : data.results
      count.value = data.count
      hasNext.value = Boolean(data.next)
      return { ok: true }
    } catch (err) {
      capture(err, 'دریافت فهرست کاربران ناموفق بود.')
      if (!append) users.value = []
      return { ok: false, error: err }
    } finally {
      loading.value = false
    }
  }

  async function applyFilters(patch = {}) {
    filters.value = { ...filters.value, ...patch }
    page.value = 1
    return fetchUsers()
  }

  function resetFilters() {
    filters.value = { search: '', role: '', is_active: '', buyers: '' }
    page.value = 1
    return fetchUsers()
  }

  async function loadMore() {
    if (!hasNext.value || loading.value) return
    page.value += 1
    await fetchUsers({ append: true })
  }

  async function fetchUserOrders(id) {
    if (ordersByUser.value[id]) return ordersByUser.value[id]
    try {
      const { data } = await adminApi.userOrders(id)
      ordersByUser.value = { ...ordersByUser.value, [id]: data }
      return data
    } catch (err) {
      capture(err, 'دریافت سفارش‌های این کاربر ناموفق بود.')
      return []
    }
  }

  /** Replace one row in place, so a change does not reset scroll or filters. */
  function patchRow(updated) {
    const index = users.value.findIndex((u) => u.id === updated.id)
    if (index !== -1) users.value[index] = updated
  }

  async function setRole(id, role) {
    acting.value = true
    resetErrors()
    try {
      const { data } = await adminApi.setUserRole(id, role)
      patchRow(data)
      return { ok: true, data }
    } catch (err) {
      // The server refuses self-demotion and last-admin demotion with a
      // sentence worth showing verbatim.
      capture(err, 'تغییر نقش ناموفق بود.')
      return { ok: false, error: err }
    } finally {
      acting.value = false
    }
  }

  async function setActive(id, isActive) {
    acting.value = true
    resetErrors()
    try {
      const { data } = await adminApi.setUserActive(id, isActive)
      patchRow(data)
      return { ok: true, data }
    } catch (err) {
      capture(err, isActive ? 'فعال‌سازی ناموفق بود.' : 'غیرفعال‌سازی ناموفق بود.')
      return { ok: false, error: err }
    } finally {
      acting.value = false
    }
  }

  return {
    users,
    count,
    page,
    hasNext,
    ordersByUser,
    loading,
    acting,
    error,
    fieldErrors,
    filters,
    isEmpty,
    activeFilterCount,
    resetErrors,
    fetchUsers,
    applyFilters,
    resetFilters,
    loadMore,
    fetchUserOrders,
    setRole,
    setActive,
  }
})
