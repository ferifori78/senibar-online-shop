import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import adminApi from '@/api/admin'
import { useApiErrors } from './errors'

export const useInventoryStore = defineStore('adminInventory', () => {
  const totals = ref(null)
  const products = ref([])
  const fading = ref([])
  const log = ref([])

  const loading = ref(false)
  const acting = ref(false)
  const error = ref('')
  const fieldErrors = ref({})

  // The adjust dialog has no per-field error slots, so a DRF validation error
  // must reach the banner rather than being swallowed by a generic fallback.
  const { capture, reset: resetErrors } = useApiErrors(error, fieldErrors, {
    foldFieldErrors: true,
  })

  const search = ref('')
  // 'all' | 'out' | 'low' — the three states a packer actually sorts by.
  const view = ref('all')

  const threshold = computed(() => totals.value?.low_stock_threshold ?? 1000)

  const visible = computed(() => {
    let rows = products.value

    if (view.value === 'out') rows = rows.filter((r) => r.sellable_grams <= 0)
    else if (view.value === 'low')
      rows = rows.filter((r) => r.sellable_grams > 0 && r.sellable_grams < threshold.value)

    const term = search.value.trim().toLowerCase()
    if (term) {
      rows = rows.filter(
        (r) =>
          r.name.toLowerCase().includes(term) ||
          r.batches.some((b) => b.batch_code.toLowerCase().includes(term)),
      )
    }
    return rows
  })

  const isEmpty = computed(() => !loading.value && visible.value.length === 0)

  /** Where a row sits, for the status lamp. */
  function levelOf(row) {
    if (row.sellable_grams <= 0) return 'out'
    if (row.sellable_grams < threshold.value) return 'low'
    return 'ok'
  }

  async function fetchInventory() {
    loading.value = true
    resetErrors()
    try {
      const { data } = await adminApi.inventory()
      totals.value = data.totals
      products.value = data.products
      fading.value = data.fading
      return { ok: true }
    } catch (err) {
      capture(err, 'دریافت موجودی ناموفق بود.')
      products.value = []
      return { ok: false, error: err }
    } finally {
      loading.value = false
    }
  }

  async function fetchLog(params = {}) {
    try {
      const { data } = await adminApi.adjustmentLog(params)
      log.value = data
      return data
    } catch (err) {
      capture(err, 'دریافت تاریخچه‌ی تعدیل‌ها ناموفق بود.')
      return []
    }
  }

  async function adjust(batchId, payload) {
    acting.value = true
    resetErrors()
    try {
      const { data } = await adminApi.adjustStock(batchId, payload)
      log.value = [data, ...log.value]
      // Totals, freshness and status all shift with one adjustment; refetching
      // is cheaper to reason about than patching four derived numbers by hand.
      await fetchInventory()
      return { ok: true, data }
    } catch (err) {
      // The server's refusals name the actual grams involved — show them.
      capture(err, 'ثبت تعدیل ناموفق بود.')
      return { ok: false, error: err }
    } finally {
      acting.value = false
    }
  }

  return {
    totals,
    products,
    fading,
    log,
    loading,
    acting,
    error,
    fieldErrors,
    search,
    view,
    threshold,
    visible,
    isEmpty,
    levelOf,
    resetErrors,
    fetchInventory,
    fetchLog,
    adjust,
  }
})
