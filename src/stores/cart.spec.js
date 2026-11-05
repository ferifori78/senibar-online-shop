import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/orders', () => ({
  default: { quoteCart: vi.fn() },
  paymentsApi: {},
}))

import ordersApi from '@/api/orders'
import { useCartStore } from './cart'

const PRODUCT = {
  id: 1,
  slug: 'yirgacheffe',
  name: 'Yirgacheffe',
  origin_country: 'Ethiopia',
  image: null,
  price_options: [
    { weight_grams: 100, price: 392000 },
    { weight_grams: 250, price: 980000 },
    { weight_grams: 500, price: 1960000 },
    { weight_grams: 1000, price: 3920000 },
  ],
}

function quoteReply(overrides = {}) {
  return {
    data: {
      items: [],
      subtotal: 0,
      shipping_cost: 0,
      total: 0,
      issues: [],
      is_orderable: true,
      shipping_options: [],
      ...overrides,
    },
  }
}

describe('cart store', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    ordersApi.quoteCart.mockResolvedValue(quoteReply())
    setActivePinia(createPinia())
  })

  it('adds a line and captures the price for the chosen weight', async () => {
    const cart = useCartStore()

    await cart.add(PRODUCT, { weight_grams: 250, grind_type: 'v60', quantity: 2 })

    expect(cart.items).toHaveLength(1)
    expect(cart.items[0]).toMatchObject({
      slug: 'yirgacheffe',
      weight_grams: 250,
      grind_type: 'v60',
      quantity: 2,
      unit_price: 980000,
    })
    expect(cart.count).toBe(2)
    expect(cart.localSubtotal).toBe(1960000)
  })

  it('merges an identical product/weight/grind instead of duplicating', async () => {
    const cart = useCartStore()

    await cart.add(PRODUCT, { weight_grams: 250, grind_type: 'whole' })
    await cart.add(PRODUCT, { weight_grams: 250, grind_type: 'whole', quantity: 3 })

    expect(cart.items).toHaveLength(1)
    expect(cart.items[0].quantity).toBe(4)
  })

  it('keeps the same coffee at a different grind as its own line', async () => {
    const cart = useCartStore()

    await cart.add(PRODUCT, { weight_grams: 250, grind_type: 'whole' })
    await cart.add(PRODUCT, { weight_grams: 250, grind_type: 'espresso' })

    expect(cart.items).toHaveLength(2)
  })

  it('re-prices a line when its weight changes', async () => {
    const cart = useCartStore()
    await cart.add(PRODUCT, { weight_grams: 250, grind_type: 'whole' })
    const key = cart.lineKey(cart.items[0])

    await cart.setWeight(key, 1000)

    expect(cart.items[0].weight_grams).toBe(1000)
    expect(cart.items[0].unit_price).toBe(3920000)
  })

  it('merges into an existing line when a weight change collides with it', async () => {
    const cart = useCartStore()
    await cart.add(PRODUCT, { weight_grams: 250, grind_type: 'whole', quantity: 1 })
    await cart.add(PRODUCT, { weight_grams: 500, grind_type: 'whole', quantity: 2 })
    const key = cart.lineKey(cart.items[0])

    // 250g -> 500g now matches the second line; they must become one.
    await cart.setWeight(key, 500)

    expect(cart.items).toHaveLength(1)
    expect(cart.items[0].quantity).toBe(3)
    expect(cart.items[0].weight_grams).toBe(500)
  })

  it('removes a line when its quantity drops below one', async () => {
    const cart = useCartStore()
    await cart.add(PRODUCT, { weight_grams: 250, grind_type: 'whole', quantity: 1 })
    const key = cart.lineKey(cart.items[0])

    await cart.setQuantity(key, 0)

    expect(cart.items).toHaveLength(0)
    expect(cart.isEmpty).toBe(true)
  })

  it('caps quantity at twenty', async () => {
    const cart = useCartStore()
    await cart.add(PRODUCT, { weight_grams: 250, grind_type: 'whole', quantity: 1 })
    const key = cart.lineKey(cart.items[0])

    await cart.setQuantity(key, 500)

    expect(cart.items[0].quantity).toBe(20)
  })

  it('prefers the server quote over locally captured prices', async () => {
    ordersApi.quoteCart.mockResolvedValue(
      quoteReply({
        items: [
          {
            product: 'yirgacheffe',
            weight_grams: 250,
            grind_type: 'whole',
            unit_price: 1100000, // the price rose since it was added
          },
        ],
        subtotal: 1100000,
        shipping_cost: 150000,
        total: 1250000,
      }),
    )
    const cart = useCartStore()

    await cart.add(PRODUCT, { weight_grams: 250, grind_type: 'whole' })

    expect(cart.subtotal).toBe(1100000)
    expect(cart.total).toBe(1250000)
    expect(cart.items[0].unit_price).toBe(1100000)
  })

  it('blocks checkout and exposes issues per product when stock is short', async () => {
    ordersApi.quoteCart.mockResolvedValue(
      quoteReply({
        issues: [
          { product: 'yirgacheffe', code: 'insufficient_stock', detail: 'تنها ۵۰۰ گرم موجود است.' },
        ],
        is_orderable: false,
      }),
    )
    const cart = useCartStore()

    await cart.add(PRODUCT, { weight_grams: 1000, grind_type: 'whole', quantity: 5 })

    expect(cart.canCheckout).toBe(false)
    expect(cart.issuesByProduct.yirgacheffe).toHaveLength(1)
  })

  it('persists across a reload and restores from storage', async () => {
    const cart = useCartStore()
    await cart.add(PRODUCT, { weight_grams: 500, grind_type: 'chemex', quantity: 2 })

    expect(JSON.parse(localStorage.getItem('senobar.cart'))).toHaveLength(1)

    setActivePinia(createPinia())
    const restored = useCartStore()

    expect(restored.items).toHaveLength(1)
    expect(restored.items[0].grind_type).toBe('chemex')
    expect(restored.count).toBe(2)
  })

  it('clears items and the quote together', async () => {
    const cart = useCartStore()
    await cart.add(PRODUCT, { weight_grams: 250, grind_type: 'whole' })

    cart.clear()

    expect(cart.isEmpty).toBe(true)
    expect(cart.quote).toBeNull()
    expect(cart.canCheckout).toBe(false)
  })

  it('surfaces a quote failure without wiping the cart', async () => {
    ordersApi.quoteCart.mockRejectedValue({ response: { status: 500, data: {} } })
    const cart = useCartStore()

    await cart.add(PRODUCT, { weight_grams: 250, grind_type: 'whole' })

    expect(cart.items).toHaveLength(1)
    expect(cart.error).toBeTruthy()
    expect(cart.canCheckout).toBe(false)
  })

  it('re-quotes when the shipping method changes', async () => {
    const cart = useCartStore()
    await cart.add(PRODUCT, { weight_grams: 250, grind_type: 'whole' })
    ordersApi.quoteCart.mockClear()

    await cart.setShippingMethod('express')

    expect(cart.shippingMethod).toBe('express')
    expect(ordersApi.quoteCart).toHaveBeenCalledWith(
      expect.objectContaining({ shipping_method: 'express' }),
    )
  })
})
