import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'

import ordersApi from '@/api/orders'
import { parseApiError } from '@/api/client'

const STORAGE_KEY = 'senobar.cart'

/** A line is identified by product + weight + grind. Adding the same three
 *  again bumps quantity rather than creating a second row — the backend has a
 *  unique constraint on exactly this triple. */
function lineKey(item) {
  return `${item.slug}::${item.weight_grams}::${item.grind_type}`
}

function readStored() {
  try {
    const raw = JSON.parse(localStorage.getItem(STORAGE_KEY))
    return Array.isArray(raw) ? raw : []
  } catch {
    return []
  }
}

export const useCartStore = defineStore('cart', () => {
  const items = ref(readStored())
  const shippingMethod = ref('standard')

  // Server-priced figures. The local ones below are for instant feedback only.
  const quote = ref(null)
  const quoteLoading = ref(false)
  const error = ref('')

  const count = computed(() => items.value.reduce((sum, i) => sum + i.quantity, 0))
  const isEmpty = computed(() => items.value.length === 0)

  /** Optimistic subtotal from prices captured at add-to-cart time. The quote
   *  endpoint is what checkout actually trusts. */
  const localSubtotal = computed(() =>
    items.value.reduce((sum, i) => sum + Number(i.unit_price) * i.quantity, 0),
  )

  const totalGrams = computed(() =>
    items.value.reduce((sum, i) => sum + i.weight_grams * i.quantity, 0),
  )

  const subtotal = computed(() =>
    quote.value ? Number(quote.value.subtotal) : localSubtotal.value,
  )
  const shippingCost = computed(() => (quote.value ? Number(quote.value.shipping_cost) : 0))
  const total = computed(() => (quote.value ? Number(quote.value.total) : localSubtotal.value))

  const issues = computed(() => quote.value?.issues || [])
  const shippingOptions = computed(() => quote.value?.shipping_options || [])
  const canCheckout = computed(() => Boolean(quote.value?.is_orderable))

  /** Problems keyed by product slug, so a cart row can show its own warning. */
  const issuesByProduct = computed(() => {
    const map = {}
    for (const issue of issues.value) {
      ;(map[issue.product] ||= []).push(issue)
    }
    return map
  })

  watch(
    items,
    (value) => {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(value))
      } catch {
        // Storage unavailable; the cart lives for this tab only.
      }
    },
    { deep: true },
  )

  function add(product, { weight_grams = 250, grind_type = 'whole', quantity = 1 } = {}) {
    const option = product.price_options?.find((o) => o.weight_grams === weight_grams)
    const line = {
      slug: product.slug,
      product_id: product.id,
      name: product.name,
      origin: product.origin_country,
      image: product.image || null,
      weight_grams,
      grind_type,
      quantity,
      unit_price: option ? Number(option.price) : 0,
    }

    const key = lineKey(line)
    const existing = items.value.find((i) => lineKey(i) === key)

    if (existing) {
      existing.quantity = Math.min(existing.quantity + quantity, 20)
    } else {
      items.value.push(line)
    }
    return refreshQuote()
  }

  function remove(key) {
    items.value = items.value.filter((i) => lineKey(i) !== key)
    return items.value.length ? refreshQuote() : clearQuote()
  }

  function setQuantity(key, quantity) {
    const item = items.value.find((i) => lineKey(i) === key)
    if (!item) return Promise.resolve()

    if (quantity < 1) return remove(key)
    item.quantity = Math.min(quantity, 20)
    return refreshQuote()
  }

  /** Changing weight re-prices the line and may collide with an existing one
   *  at the same weight and grind — merge instead of creating a duplicate. */
  function setWeight(key, weight_grams) {
    const item = items.value.find((i) => lineKey(i) === key)
    if (!item || item.weight_grams === weight_grams) return Promise.resolve()

    const candidate = { ...item, weight_grams }
    const twin = items.value.find(
      (i) => lineKey(i) === lineKey(candidate) && lineKey(i) !== key,
    )

    if (twin) {
      twin.quantity = Math.min(twin.quantity + item.quantity, 20)
      items.value = items.value.filter((i) => lineKey(i) !== key)
    } else {
      // Price scales linearly off the 250g base, matching price_for_grams().
      item.unit_price = Math.round((item.unit_price / item.weight_grams) * weight_grams)
      item.weight_grams = weight_grams
    }
    return refreshQuote()
  }

  function setGrind(key, grind_type) {
    const item = items.value.find((i) => lineKey(i) === key)
    if (!item || item.grind_type === grind_type) return Promise.resolve()

    const candidate = { ...item, grind_type }
    const twin = items.value.find(
      (i) => lineKey(i) === lineKey(candidate) && lineKey(i) !== key,
    )

    if (twin) {
      twin.quantity = Math.min(twin.quantity + item.quantity, 20)
      items.value = items.value.filter((i) => lineKey(i) !== key)
    } else {
      item.grind_type = grind_type
    }
    return refreshQuote()
  }

  function clear() {
    items.value = []
    clearQuote()
  }

  function clearQuote() {
    quote.value = null
    error.value = ''
    return Promise.resolve()
  }

  function setShippingMethod(method) {
    shippingMethod.value = method
    return refreshQuote()
  }

  /** Ask the server what this cart really costs. Prices, stock and shipping
   *  are all re-read there; nothing in the browser is trusted. */
  async function refreshQuote() {
    if (!items.value.length) return clearQuote()

    quoteLoading.value = true
    error.value = ''
    try {
      const { data } = await ordersApi.quoteCart({
        items: items.value.map((i) => ({
          product: i.product_id,
          weight_grams: i.weight_grams,
          grind_type: i.grind_type,
          quantity: i.quantity,
        })),
        shipping_method: shippingMethod.value,
      })
      quote.value = data

      // Re-sync captured prices, so the cart shows today's figures even if the
      // item was added last week.
      for (const line of data.items) {
        const local = items.value.find(
          (i) =>
            i.slug === line.product &&
            i.weight_grams === line.weight_grams &&
            i.grind_type === line.grind_type,
        )
        if (local) local.unit_price = Number(line.unit_price)
      }
    } catch (err) {
      error.value = parseApiError(err).message || 'قیمت‌گذاری سبد ناموفق بود.'
      quote.value = null
    } finally {
      quoteLoading.value = false
    }
  }

  return {
    items,
    shippingMethod,
    quote,
    quoteLoading,
    error,
    count,
    isEmpty,
    subtotal,
    localSubtotal,
    shippingCost,
    total,
    totalGrams,
    issues,
    issuesByProduct,
    shippingOptions,
    canCheckout,
    lineKey,
    add,
    remove,
    setQuantity,
    setWeight,
    setGrind,
    setShippingMethod,
    refreshQuote,
    clear,
  }
})
