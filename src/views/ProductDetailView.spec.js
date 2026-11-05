import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('vue-router', async () => {
  const actual = await vi.importActual('vue-router')
  return {
    ...actual,
    useRoute: () => ({ params: { slug: 'x' } }),
    RouterLink: { template: '<a><slot /></a>' },
  }
})

vi.mock('@/api/catalog', () => ({
  default: { list: vi.fn(), facets: vi.fn(), detail: vi.fn(), batches: vi.fn() },
}))

import catalogApi from '@/api/catalog'
import ProductDetailView from './ProductDetailView.vue'

/*
 * The product page serves two kinds. A pantry item has no roast, no batch and
 * no lot, so every phrase built around those has to be checked — the model's
 * columns are not nullable, and wording is not.
 */

const LOT = {
  id: 1,
  slug: 'yirgacheffe',
  name: 'یرگاچف',
  kind: 'lot',
  description: 'یک قهوه‌ی روشن.',
  origin_country: 'اتیوپی',
  species_display: 'عربیکا',
  process_display: 'شسته',
  price_per_250g: 250000,
  price_options: [{ weight_grams: 250, price: 250000 }],
  available_grams: 1200,
  is_in_stock: true,
  flavor_notes: [],
  images: [],
}

const MASALA = {
  ...LOT,
  id: 2,
  slug: 'masala',
  name: 'چای ماسالا',
  kind: 'pantry',
  description: 'چای سیاه و ادویه.',
  brand: 'واگ باکری',
  sale_mode: 'package',
  package_grams: 200,
  package_price: 185000,
  available_packages: 40,
  available_grams: 8000,
  price_options: [{ weight_grams: 200, price: 185000 }],
}

const stubs = {
  ProductCarousel: true,
  GrindSelector: true,
  WeightSelector: true,
  BaseButton: { template: '<button><slot /></button>' },
  RouterLink: { template: '<a><slot /></a>' },
}

async function mountDetail(product, batches = []) {
  catalogApi.detail.mockResolvedValue({ data: product })
  catalogApi.batches.mockResolvedValue({ data: batches })
  const wrapper = mount(ProductDetailView, { global: { stubs } })
  await new Promise((r) => setTimeout(r, 0))
  await wrapper.vm.$nextTick()
  return wrapper
}

describe('ProductDetailView — pantry wording', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('never mentions a roast date for a pantry item', async () => {
    const wrapper = await mountDetail(MASALA)
    // Masala is not roasted, so «هنوز بچی … رست نشده» reads as a missing
    // value rather than one that never applied.
    expect(wrapper.text()).not.toContain('تاریخ رست')
    expect(wrapper.text()).not.toContain('رست نشده')
    expect(wrapper.find('.detail__roast').exists()).toBe(false)
  })

  it('still shows the roast panel for a coffee with no batch yet', async () => {
    const wrapper = await mountDetail(LOT)
    expect(wrapper.text()).toContain('تاریخ رست')
    expect(wrapper.text()).toContain('رست نشده')
  })

  it('says «درباره این محصول» for a pantry item', async () => {
    const wrapper = await mountDetail(MASALA)
    expect(wrapper.text()).toContain('درباره این محصول')
    expect(wrapper.text()).not.toContain('درباره این قهوه')
  })

  it('says «درباره این قهوه» for a coffee', async () => {
    const wrapper = await mountDetail(LOT)
    expect(wrapper.text()).toContain('درباره این قهوه')
  })

  it('counts remaining stock in packs, not grams', async () => {
    const wrapper = await mountDetail(MASALA)
    // «۸ کیلوگرم باقی مانده» for forty sealed 200g packs is a figure the
    // customer cannot act on.
    expect(wrapper.text()).toContain('۴۰ بسته باقی مانده')
    expect(wrapper.text()).not.toContain('کیلوگرم')
    expect(wrapper.text()).not.toContain('این لات')
  })

  it('still counts a coffee lot in grams', async () => {
    const wrapper = await mountDetail(LOT)
    expect(wrapper.text()).toContain('از این لات باقی مانده')
  })

  it('carries no emoji', async () => {
    const wrapper = await mountDetail(MASALA)
    expect(wrapper.text()).not.toMatch(/\p{Extended_Pictographic}/u)
  })
})
