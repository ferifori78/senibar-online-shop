import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/catalog', () => ({
  default: { list: vi.fn(), facets: vi.fn(), quiz: vi.fn(), recommend: vi.fn() },
}))

import catalogApi from '@/api/catalog'
import HomeView from './HomeView.vue'

/*
 * The shelf on the landing page. A roaster picks what sits there with a
 * checkbox; until they pick anything it falls back to the newest coffees,
 * which is what the section did before the checkbox existed.
 */

const PICKED = { id: 1, slug: 'yirgacheffe', name: 'یرگاچف', kind: 'lot', is_featured: true }
const NEWEST = { id: 2, slug: 'santos', name: 'سانتوس', kind: 'lot', is_featured: false }

const stubs = {
  ProductCard: { props: ['product'], template: '<div class="card">{{ product.name }}</div>' },
  RouterLink: { template: '<a><slot /></a>' },
  LoadingState: true,
  EmptyState: true,
  VerseBlock: true,
  PlateQuiz: true,
  BaseButton: { template: '<button><slot /></button>' },
}

const reply = (results) => ({ data: { results, count: results.length, next: null } })

async function mountHome() {
  const wrapper = mount(HomeView, { global: { stubs } })
  await new Promise((r) => setTimeout(r, 0))
  await wrapper.vm.$nextTick()
  return wrapper
}

describe('HomeView — featured shelf', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it("asks for the roaster's picks first", async () => {
    catalogApi.list.mockResolvedValue(reply([PICKED]))
    await mountHome()

    const first = catalogApi.list.mock.calls[0][0]
    expect(first.featured).toBe(true)
    // Shelf order, not newest: the roaster arranged these deliberately.
    expect(first.ordering).toBe('sort_order')
  })

  it('shows the picks and names the section after them', async () => {
    catalogApi.list.mockResolvedValue(reply([PICKED]))
    const wrapper = await mountHome()

    expect(wrapper.text()).toContain('یرگاچف')
    expect(wrapper.text()).toContain('محصولات پیشنهادی صنوبر')
  })

  it('falls back to the newest when nothing is picked', async () => {
    catalogApi.list
      .mockResolvedValueOnce(reply([])) // no picks yet
      .mockResolvedValueOnce(reply([NEWEST])) // newest, in stock

    const wrapper = await mountHome()
    expect(wrapper.text()).toContain('سانتوس')

    const second = catalogApi.list.mock.calls[1][0]
    expect(second.ordering).toBe('-created_at')
    expect(second.in_stock).toBe(true)
  })

  it('keeps the old heading when these are not really picks', async () => {
    catalogApi.list.mockResolvedValueOnce(reply([])).mockResolvedValueOnce(reply([NEWEST]))
    const wrapper = await mountHome()

    // Calling the newest three «پیشنهادی صنوبر» would be a claim nobody in
    // the shop has made.
    expect(wrapper.text()).toContain('تازه‌ترین لات‌ها')
    expect(wrapper.text()).not.toContain('محصولات پیشنهادی صنوبر')
  })

  it('shows at most three', async () => {
    catalogApi.list.mockResolvedValue(
      reply([PICKED, NEWEST, { ...PICKED, id: 3, name: 'سوم' }, { ...PICKED, id: 4, name: 'چهارم' }]),
    )
    const wrapper = await mountHome()
    expect(wrapper.findAll('.card')).toHaveLength(3)
    expect(wrapper.text()).not.toContain('چهارم')
  })

  it('still renders when the API is down', async () => {
    catalogApi.list.mockRejectedValue(new Error('network'))
    const wrapper = await mountHome()
    // A landing page must not become an error banner: the hero and the steps
    // below it do not depend on the API at all.
    expect(wrapper.text()).toContain('رست پس از سفارش')
    expect(wrapper.text()).toContain('داستان ما')
  })
})
