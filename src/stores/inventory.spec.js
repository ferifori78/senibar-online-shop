import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/admin', () => ({
  default: {
    inventory: vi.fn(),
    adjustmentLog: vi.fn(),
    adjustStock: vi.fn(),
  },
}))

import adminApi from '@/api/admin'
import { useInventoryStore } from './inventory'

function row(name, { sellable, reserved = 0, batches = [] } = {}) {
  return {
    product_id: name.length,
    name,
    slug: name,
    remaining_grams: sellable + reserved,
    reserved_grams: reserved,
    sellable_grams: sellable,
    batch_count: batches.length,
    batches,
  }
}

const PAYLOAD = {
  totals: {
    low_stock_threshold: 1000,
    low_stock: 1,
    out_of_stock: 1,
    total_sellable_grams: 5300,
    total_reserved_grams: 400,
  },
  products: [
    row('empty', { sellable: 0 }),
    row('scarce', { sellable: 800 }),
    row('plenty', {
      sellable: 4500,
      reserved: 400,
      batches: [{ id: 7, batch_code: 'ETH-01' }],
    }),
  ],
  fading: [],
}

describe('inventory store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    adminApi.inventory.mockResolvedValue({ data: PAYLOAD })
  })

  it('grades each row against the server-supplied threshold', async () => {
    const inv = useInventoryStore()
    await inv.fetchInventory()

    expect(inv.levelOf(PAYLOAD.products[0])).toBe('out')
    expect(inv.levelOf(PAYLOAD.products[1])).toBe('low')
    expect(inv.levelOf(PAYLOAD.products[2])).toBe('ok')
  })

  it('takes the threshold from the server, not a hardcoded number', async () => {
    adminApi.inventory.mockResolvedValue({
      data: { ...PAYLOAD, totals: { ...PAYLOAD.totals, low_stock_threshold: 500 } },
    })
    const inv = useInventoryStore()
    await inv.fetchInventory()

    // 800g is above a 500g threshold, so it is no longer "low".
    expect(inv.levelOf(PAYLOAD.products[1])).toBe('ok')
  })

  it('filters by view', async () => {
    const inv = useInventoryStore()
    await inv.fetchInventory()

    inv.view = 'out'
    expect(inv.visible.map((r) => r.name)).toEqual(['empty'])

    inv.view = 'low'
    expect(inv.visible.map((r) => r.name)).toEqual(['scarce'])

    inv.view = 'all'
    expect(inv.visible).toHaveLength(3)
  })

  it('searches batch codes as well as coffee names', async () => {
    const inv = useInventoryStore()
    await inv.fetchInventory()

    inv.search = 'eth-01'
    expect(inv.visible.map((r) => r.name)).toEqual(['plenty'])

    inv.search = 'scar'
    expect(inv.visible.map((r) => r.name)).toEqual(['scarce'])
  })

  it('refetches after an adjustment, since totals and status both shift', async () => {
    const inv = useInventoryStore()
    await inv.fetchInventory()
    adminApi.adjustStock.mockResolvedValue({ data: { id: 1, delta_grams: -200 } })

    const result = await inv.adjust(7, { delta_grams: -200, reason: 'spillage' })

    expect(result.ok).toBe(true)
    expect(adminApi.inventory).toHaveBeenCalledTimes(2)
    expect(inv.log[0].id).toBe(1)
  })

  it("surfaces the server's refusal verbatim, because it names the grams", async () => {
    const inv = useInventoryStore()
    adminApi.adjustStock.mockRejectedValue({
      response: {
        status: 400,
        data: { delta_grams: ['۴۰۰ گرم رزرو شده است؛ موجودی نمی‌تواند پایین‌تر برود.'] },
      },
    })

    const result = await inv.adjust(7, { delta_grams: -5000, reason: 'recount' })

    expect(result.ok).toBe(false)
    expect(inv.error).toContain('رزرو شده')
  })
})
