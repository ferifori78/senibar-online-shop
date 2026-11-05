import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import ordersApi from '@/api/orders'
import { parseApiError } from '@/api/client'

export const useOrdersStore = defineStore('orders', () => {
  const orders = ref([])
  const count = ref(0)
  const page = ref(1)
  const hasNext = ref(false)
  const state = ref('all') // all | open | past

  const order = ref(null)

  const loading = ref(false)
  const detailLoading = ref(false)
  const error = ref('')
  const acting = ref(false)

  const isEmpty = computed(() => !loading.value && orders.value.length === 0)

  async function fetchOrders({ append = false } = {}) {
    loading.value = true
    error.value = ''
    try {
      const params = { page: page.value }
      if (state.value !== 'all') params.state = state.value

      const { data } = await ordersApi.list(params)
      orders.value = append ? [...orders.value, ...data.results] : data.results
      count.value = data.count
      hasNext.value = Boolean(data.next)
    } catch (err) {
      error.value = parseApiError(err).message || 'دریافت سفارش‌ها ناموفق بود.'
      if (!append) orders.value = []
    } finally {
      loading.value = false
    }
  }

  function setState(next) {
    state.value = next
    page.value = 1
    return fetchOrders()
  }

  async function loadMore() {
    if (!hasNext.value || loading.value) return
    page.value += 1
    await fetchOrders({ append: true })
  }

  async function fetchOrder(number) {
    detailLoading.value = true
    error.value = ''
    order.value = null
    try {
      const { data } = await ordersApi.detail(number)
      order.value = data
    } catch (err) {
      error.value = parseApiError(err).message || 'این سفارش پیدا نشد.'
    } finally {
      detailLoading.value = false
    }
  }

  /** Cancel, and fold the returned order back into any list we're holding, so
   *  the card and the detail page never disagree. */
  async function cancelOrder(number, reason = '') {
    acting.value = true
    error.value = ''
    try {
      const { data } = await ordersApi.cancel(number, reason)
      order.value = data
      const index = orders.value.findIndex((o) => o.number === number)
      if (index !== -1) {
        orders.value[index] = { ...orders.value[index], ...data }
      }
      return { ok: true, data }
    } catch (err) {
      error.value = parseApiError(err).message || 'لغو سفارش ناموفق بود.'
      return { ok: false, error: err }
    } finally {
      acting.value = false
    }
  }

  return {
    orders,
    order,
    count,
    page,
    hasNext,
    state,
    loading,
    detailLoading,
    acting,
    error,
    isEmpty,
    fetchOrders,
    fetchOrder,
    setState,
    loadMore,
    cancelOrder,
  }
})
