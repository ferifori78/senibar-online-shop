import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import adminApi from '@/api/admin'
import { useApiErrors } from './errors'

export const useAdminStore = defineStore('admin', () => {
  const stats = ref(null)
  const board = ref([])
  const orders = ref([])
  const order = ref(null)
  const products = ref([])
  const batches = ref([])

  const loading = ref(false)
  const acting = ref(false)
  const error = ref('')
  const fieldErrors = ref({})

  const boardFilter = ref('queue')
  const boardSearch = ref('')

  const awaitingRoast = computed(() => stats.value?.queue?.awaiting_roast ?? 0)
  const todaySales = computed(() => Number(stats.value?.sales?.today ?? 0))

  const { capture: captureError, reset: resetErrors } = useApiErrors(error, fieldErrors)

  /** Shared wrapper for the read endpoints. */
  async function load(request, target, fallback) {
    loading.value = true
    resetErrors()
    try {
      const { data } = await request()
      target.value = data
      return { ok: true, data }
    } catch (err) {
      captureError(err, fallback)
      return { ok: false, error: err }
    } finally {
      loading.value = false
    }
  }

  const fetchStats = () =>
    load(() => adminApi.dashboard(), stats, 'دریافت آمار ناموفق بود.')

  async function fetchBoard() {
    loading.value = true
    resetErrors()
    try {
      const params = {}
      if (boardFilter.value !== 'all') params.state = boardFilter.value
      if (boardSearch.value) params.search = boardSearch.value

      const { data } = await adminApi.board(params)
      board.value = data.results
    } catch (err) {
      captureError(err, 'دریافت جدول سفارش‌ها ناموفق بود.')
      board.value = []
    } finally {
      loading.value = false
    }
  }

  function setBoardFilter(value) {
    boardFilter.value = value
    return fetchBoard()
  }

  async function fetchOrders(params = {}) {
    loading.value = true
    resetErrors()
    try {
      const { data } = await adminApi.orders(params)
      orders.value = data.results
    } catch (err) {
      captureError(err, 'دریافت سفارش‌ها ناموفق بود.')
    } finally {
      loading.value = false
    }
  }

  const fetchOrder = (number) =>
    load(() => adminApi.order(number), order, 'این سفارش پیدا نشد.')

  /** Move an order along the pipeline. The backend rejects illegal moves. */
  async function setStatus(number, status, note = '') {
    acting.value = true
    resetErrors()
    try {
      const { data } = await adminApi.setStatus(number, { status, note })
      order.value = data

      // Keep any list we're holding in step with the change.
      const index = orders.value.findIndex((o) => o.number === number)
      if (index !== -1) orders.value[index] = { ...orders.value[index], ...data }
      for (const row of board.value) {
        if (row.order_number === number) row.order_status = data.status
      }
      return { ok: true, data }
    } catch (err) {
      captureError(err, 'تغییر وضعیت ناموفق بود.')
      return { ok: false, error: err }
    } finally {
      acting.value = false
    }
  }

  // --- Catalog ------------------------------------------------------------
  async function fetchProducts(params = {}) {
    loading.value = true
    resetErrors()
    try {
      const { data } = await adminApi.products({ page_size: 100, ...params })
      products.value = data.results
    } catch (err) {
      captureError(err, 'دریافت محصولات ناموفق بود.')
    } finally {
      loading.value = false
    }
  }

  /** Read one product in full, for the edit form.
   *
   * The list payload is lean by design; the form needs every field, and
   * filling it from a partial record is how blank values got saved over real
   * ones. Deliberately does not touch `products`: the row in the list is fine
   * as it is, and replacing it with the detail shape would change what the
   * table renders. */
  async function fetchProduct(slug) {
    resetErrors()
    try {
      const { data } = await adminApi.product(slug)
      return { ok: true, data }
    } catch (err) {
      captureError(err, 'دریافت اطلاعات محصول ناموفق بود.')
      return { ok: false, data: null }
    }
  }

  /** Persist the shelf order after a drag.
   *
   * Deliberately does not touch `products`: the caller has already moved the
   * row so the drop feels immediate, and re-assigning here would make it jump.
   */
  async function reorderProducts(order) {
    resetErrors()
    try {
      const { data } = await adminApi.reorderProducts(order)
      return { ok: true, data }
    } catch (err) {
      captureError(err, 'ذخیره ترتیب ناموفق بود.')
      return { ok: false, data: null }
    }
  }

  async function saveProduct(payload, slug = null) {
    acting.value = true
    resetErrors()
    try {
      const { data } = slug
        ? await adminApi.updateProduct(slug, payload)
        : await adminApi.createProduct(payload)

      const index = products.value.findIndex((p) => p.slug === (slug || data.slug))
      if (index !== -1) products.value[index] = data
      else products.value.unshift(data)

      return { ok: true, data }
    } catch (err) {
      captureError(err, 'ذخیره محصول ناموفق بود.')
      return { ok: false, error: err }
    } finally {
      acting.value = false
    }
  }

  async function deleteProduct(slug) {
    acting.value = true
    resetErrors()
    try {
      const { data, status } = await adminApi.deleteProduct(slug)

      // 204 means the row is gone. 200 means the server archived it instead,
      // because orders or batches point at it — the coffee is off the shop
      // either way, but the list must keep showing the archived row rather
      // than dropping a product that still exists.
      if (status === 204) {
        products.value = products.value.filter((p) => p.slug !== slug)
        return { ok: true, erased: true }
      }

      const index = products.value.findIndex((p) => p.slug === slug)
      if (index !== -1) products.value[index] = { ...products.value[index], status: 'archived' }

      return { ok: true, erased: false, detail: data?.detail, blockers: data?.blockers }
    } catch (err) {
      captureError(err, 'حذف محصول ناموفق بود.')
      return { ok: false, error: err }
    } finally {
      acting.value = false
    }
  }

  async function archiveProduct(slug) {
    acting.value = true
    resetErrors()
    try {
      const { data } = await adminApi.archiveProduct(slug)
      const index = products.value.findIndex((p) => p.slug === slug)
      if (index !== -1) products.value[index] = { ...products.value[index], ...data }
      return { ok: true, data }
    } catch (err) {
      captureError(err, 'بایگانی محصول ناموفق بود.')
      return { ok: false, error: err }
    } finally {
      acting.value = false
    }
  }

  // --- Product gallery ------------------------------------------------------
  // These return the gallery rather than writing it into `products`: the form
  // modal owns the photo list while it is open, and the product list only
  // needs the cover, which the product payload already carries.

  async function fetchProductImages(slug) {
    resetErrors()
    try {
      const { data } = await adminApi.productImages(slug)
      return { ok: true, images: data }
    } catch (err) {
      captureError(err, 'دریافت تصویرها ناموفق بود.')
      return { ok: false, error: err }
    }
  }

  async function uploadProductImage(slug, file, altText = '') {
    acting.value = true
    resetErrors()
    try {
      const { data } = await adminApi.uploadProductImage(slug, file, altText)
      return { ok: true, image: data }
    } catch (err) {
      // Pillow rejects anything that is not a real image, and the server caps
      // the size — both come back as a field error worth showing verbatim.
      captureError(err, 'آپلود تصویر ناموفق بود.')
      return { ok: false, error: err }
    } finally {
      acting.value = false
    }
  }

  async function deleteProductImage(slug, id) {
    acting.value = true
    resetErrors()
    try {
      await adminApi.deleteProductImage(slug, id)
      return { ok: true }
    } catch (err) {
      captureError(err, 'حذف تصویر ناموفق بود.')
      return { ok: false, error: err }
    } finally {
      acting.value = false
    }
  }

  async function setProductCover(slug, id) {
    acting.value = true
    resetErrors()
    try {
      const { data } = await adminApi.setProductCover(slug, id)
      return { ok: true, images: data }
    } catch (err) {
      captureError(err, 'تعیین تصویر اصلی ناموفق بود.')
      return { ok: false, error: err }
    } finally {
      acting.value = false
    }
  }

  async function reorderProductImages(slug, order) {
    resetErrors()
    try {
      const { data } = await adminApi.reorderProductImages(slug, order)
      return { ok: true, images: data }
    } catch (err) {
      captureError(err, 'تغییر ترتیب تصویرها ناموفق بود.')
      return { ok: false, error: err }
    }
  }

  async function fetchBatches(params = {}) {
    loading.value = true
    resetErrors()
    try {
      const { data } = await adminApi.batches({ page_size: 100, ...params })
      batches.value = data.results
    } catch (err) {
      captureError(err, 'دریافت بچ‌ها ناموفق بود.')
    } finally {
      loading.value = false
    }
  }

  async function saveBatch(payload, id = null) {
    acting.value = true
    resetErrors()
    try {
      const { data } = id
        ? await adminApi.updateBatch(id, payload)
        : await adminApi.createBatch(payload)

      const index = batches.value.findIndex((b) => b.id === data.id)
      if (index !== -1) batches.value[index] = data
      else batches.value.unshift(data)

      return { ok: true, data }
    } catch (err) {
      captureError(err, 'ذخیره بچ ناموفق بود.')
      return { ok: false, error: err }
    } finally {
      acting.value = false
    }
  }

  async function deleteBatch(id) {
    acting.value = true
    resetErrors()
    try {
      await adminApi.deleteBatch(id)
      batches.value = batches.value.filter((b) => b.id !== id)
      return { ok: true }
    } catch (err) {
      // A batch that has been sold from comes back 409 with a sentence telling
      // the roaster to withdraw it instead. That text is the useful part.
      captureError(err, 'حذف بچ ناموفق بود.')
      return { ok: false, error: err }
    } finally {
      acting.value = false
    }
  }

  return {
    stats,
    board,
    orders,
    order,
    products,
    batches,
    loading,
    acting,
    error,
    fieldErrors,
    boardFilter,
    boardSearch,
    awaitingRoast,
    todaySales,
    resetErrors,
    fetchStats,
    fetchBoard,
    setBoardFilter,
    fetchOrders,
    fetchOrder,
    setStatus,
    fetchProducts,
    fetchProduct,
    reorderProducts,
    saveProduct,
    deleteProduct,
    archiveProduct,
    fetchProductImages,
    uploadProductImage,
    deleteProductImage,
    setProductCover,
    reorderProductImages,
    fetchBatches,
    saveBatch,
    deleteBatch,
  }
})
