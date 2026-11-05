import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import catalogApi from '@/api/catalog'
import { parseApiError } from '@/api/client'

/** Only send filter params the user actually set — empty values would
 *  otherwise become `?origin=&process=` and confuse the backend. */
function cleanParams(filters) {
  const params = {}
  for (const [key, value] of Object.entries(filters)) {
    if (value === '' || value === null || value === undefined) continue
    if (Array.isArray(value)) {
      if (value.length) params[key] = value.join(',')
    } else {
      params[key] = value
    }
  }
  return params
}

export const useCatalogStore = defineStore('catalog', () => {
  const products = ref([])
  const count = ref(0)
  const page = ref(1)
  const hasNext = ref(false)

  const product = ref(null)
  const batches = ref([])
  const facets = ref(null)

  const loading = ref(false)
  const detailLoading = ref(false)
  const error = ref('')

  /** The one place the filter shape is defined, so `resetFilters` cannot
   *  drift from the initial state and leave a stale key applied. */
  function blankFilters() {
    return {
      search: '',
      kind: [],
      species: [],
      origin_type: [],
      origin: [],
      process: [],
      roast_level: [],
      brew_method: '',
      in_stock: false,
      ordering: 'sort_order',
    }
  }

  const filters = ref(blankFilters())

  const activeFilterCount = computed(() => {
    const { search, ordering, ...rest } = filters.value
    return Object.values(rest).filter((v) => (Array.isArray(v) ? v.length : Boolean(v))).length
  })

  const isEmpty = computed(() => !loading.value && products.value.length === 0)

  async function fetchProducts({ append = false } = {}) {
    loading.value = true
    error.value = ''
    try {
      const params = cleanParams({ ...filters.value, page: page.value })
      const { data } = await catalogApi.list(params)
      products.value = append ? [...products.value, ...data.results] : data.results
      count.value = data.count
      hasNext.value = Boolean(data.next)
    } catch (err) {
      error.value = parseApiError(err).message
      if (!append) products.value = []
    } finally {
      loading.value = false
    }
  }

  /** Filters changed: go back to page one rather than paging into a new set. */
  async function applyFilters(patch = {}) {
    filters.value = { ...filters.value, ...patch }
    page.value = 1
    await fetchProducts()
  }

  async function loadMore() {
    if (!hasNext.value || loading.value) return
    page.value += 1
    await fetchProducts({ append: true })
  }

  function resetFilters() {
    filters.value = blankFilters()
    page.value = 1
    return fetchProducts()
  }

  async function fetchProduct(slug) {
    detailLoading.value = true
    error.value = ''
    product.value = null
    batches.value = []
    try {
      const [detail, batchList] = await Promise.all([
        catalogApi.detail(slug),
        catalogApi.batches(slug),
      ])
      product.value = detail.data
      batches.value = batchList.data
    } catch (err) {
      error.value = parseApiError(err).message || 'این محصول یافت نشد.'
    } finally {
      detailLoading.value = false
    }
  }

  async function fetchFacets() {
    if (facets.value) return facets.value
    try {
      const { data } = await catalogApi.facets()
      facets.value = data
    } catch {
      // Filter UI degrades to search-only; not worth surfacing an error.
      facets.value = null
    }
    return facets.value
  }

  return {
    products,
    count,
    page,
    hasNext,
    product,
    batches,
    facets,
    filters,
    loading,
    detailLoading,
    error,
    isEmpty,
    activeFilterCount,
    fetchProducts,
    applyFilters,
    loadMore,
    resetFilters,
    fetchProduct,
    fetchFacets,
  }
})
