import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/catalog', () => ({
  default: { list: vi.fn(), facets: vi.fn(), detail: vi.fn(), batches: vi.fn() },
}))

import catalogApi from '@/api/catalog'
import ProductListView from './ProductListView.vue'
import { useCatalogStore } from '@/stores/catalog'

const FACETS = {
  origins: ['اتیوپی', 'برزیل'],
  kinds: [
    { value: 'lot', label: 'قهوه‌ها', count: 5 },
    { value: 'pantry', label: 'پودری‌جات', count: 2 },
  ],
  species: [
    { value: 'arabica', label: 'عربیکا', count: 3 },
    { value: 'blend', label: 'ترکیبی', count: 1 },
  ],
  origin_types: [
    { value: 'single', label: 'تک‌خاستگاه', count: 3 },
    { value: 'multi', label: 'چندخاستگاه', count: 2 },
  ],
  processes: [{ value: 'washed', label: 'شسته' }],
  roast_levels: [],
  flavor_notes: [],
}

const stubs = {
  ProductCard: true,
  BaseButton: { template: '<button><slot /></button>' },
  LoadingState: true,
  EmptyState: true,
  RouterLink: true,
}

async function mountView() {
  const wrapper = mount(ProductListView, { global: { stubs } })
  await new Promise((r) => setTimeout(r, 0))
  return wrapper
}

/** The rail group whose legend reads `label`. */
function group(wrapper, label) {
  return wrapper
    .findAll('fieldset')
    .find((f) => f.find('legend').text() === label)
}

describe('ProductListView — filter rail', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    catalogApi.list.mockResolvedValue({ data: { results: [], count: 0, next: null } })
    catalogApi.facets.mockResolvedValue({ data: FACETS })
  })

  it('renders a group for each axis the shop actually has', async () => {
    const wrapper = await mountView()
    for (const label of ['دسته', 'گونه', 'خاستگاه', 'مبدأ', 'وضعیت']) {
      expect(group(wrapper, label), label).toBeTruthy()
    }
  })

  it('hides the coffee-only groups once narrowed to pantry', async () => {
    const wrapper = await mountView()
    const pantry = group(wrapper, 'دسته').findAll('input')[1]
    await pantry.trigger('change')
    await wrapper.vm.$nextTick()

    // Species, origin and process are properties of coffee. Left on the rail
    // they would be five options that all return nothing.
    expect(group(wrapper, 'گونه')).toBeFalsy()
    expect(group(wrapper, 'خاستگاه')).toBeFalsy()
    expect(group(wrapper, 'پروسس')).toBeFalsy()
    // The kind group itself stays, or there is no way back.
    expect(group(wrapper, 'دسته')).toBeTruthy()
  })

  it('clears an applied species when the rail hides it', async () => {
    const wrapper = await mountView()
    const catalog = useCatalogStore()

    await group(wrapper, 'گونه').findAll('input')[0].trigger('change')
    expect(catalog.filters.species).toEqual(['arabica'])

    await group(wrapper, 'دسته').findAll('input')[1].trigger('change')
    await wrapper.vm.$nextTick()

    // The bug this pins: hiding the group without clearing its value leaves
    // `species=arabica` applied against pantry items, so the grid empties
    // and the filter responsible is no longer on screen to un-tick.
    expect(catalog.filters.species).toEqual([])
    const params = catalogApi.list.mock.calls.at(-1)[0]
    expect(params).not.toHaveProperty('species')
    expect(params.kind).toBe('pantry')
  })

  it('keeps the coffee groups when both kinds are ticked', async () => {
    const wrapper = await mountView()
    const kinds = group(wrapper, 'دسته').findAll('input')
    await kinds[0].trigger('change')
    await kinds[1].trigger('change')
    await wrapper.vm.$nextTick()

    // "lot and pantry" still includes coffee, so narrowing by species is
    // meaningful — only *pantry alone* takes the groups away.
    expect(group(wrapper, 'گونه')).toBeTruthy()
  })

  it('carries no emoji', async () => {
    expect((await mountView()).text()).not.toMatch(/\p{Extended_Pictographic}/u)
  })
})

describe('ProductListView — mobile drawer', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    catalogApi.list.mockResolvedValue({ data: { results: [], count: 0, next: null } })
    catalogApi.facets.mockResolvedValue({ data: FACETS })
    document.body.style.overflow = ''
  })

  it('starts closed', async () => {
    const wrapper = await mountView()
    expect(wrapper.find('.catalog__rail--open').exists()).toBe(false)
    expect(wrapper.find('.catalog__scrim').exists()).toBe(false)
    expect(wrapper.find('.catalog__drawer-toggle').attributes('aria-expanded')).toBe('false')
  })

  it('opens from the hamburger and closes from the scrim', async () => {
    const wrapper = await mountView()
    await wrapper.find('.catalog__drawer-toggle').trigger('click')
    expect(wrapper.find('.catalog__rail--open').exists()).toBe(true)

    // The scrim only exists while open, so it never sits over the desktop grid.
    await wrapper.find('.catalog__scrim').trigger('click')
    expect(wrapper.find('.catalog__rail--open').exists()).toBe(false)
  })

  it('closes on Escape', async () => {
    const wrapper = await mountView()
    await wrapper.find('.catalog__drawer-toggle').trigger('click')
    expect(wrapper.find('.catalog__rail--open').exists()).toBe(true)

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.catalog__rail--open').exists()).toBe(false)
  })

  it('locks the page behind the open drawer and releases it after', async () => {
    const wrapper = await mountView()
    await wrapper.find('.catalog__drawer-toggle').trigger('click')
    await wrapper.vm.$nextTick()
    // Scrolling behind a full-screen drawer moves a grid nobody can see.
    expect(document.body.style.overflow).toBe('hidden')

    await wrapper.find('.catalog__rail-close').trigger('click')
    await wrapper.vm.$nextTick()
    expect(document.body.style.overflow).toBe('')
  })

  it('releases the page when the view unmounts while open', async () => {
    const wrapper = await mountView()
    await wrapper.find('.catalog__drawer-toggle').trigger('click')
    await wrapper.vm.$nextTick()

    wrapper.unmount()
    // Navigating away with the drawer open must not strand a locked body —
    // every later page would be unscrollable with nothing on screen to blame.
    expect(document.body.style.overflow).toBe('')
  })

  it('draws the hamburger as shapes, not as a pictograph', async () => {
    const wrapper = await mountView()
    expect(wrapper.findAll('.catalog__burger span')).toHaveLength(3)
    expect(wrapper.text()).not.toMatch(/\p{Extended_Pictographic}/u)
  })
})

describe('ProductListView — drawer scrolling', () => {
  /*
   * The bug: the desktop rail is a grid item with `align-self: start`, and
   * that declaration survived into the mobile block. A fixed element with
   * `align-self: start` sizes to its own content rather than to
   * `inset-block: 0`, so the panel grew taller than the screen — and an
   * element grown to fit its content never overflows itself, so
   * `overflow-y: auto` had nothing to scroll. The last filter group sat
   * below the fold with no way to reach it.
   *
   * There is no unit test for this. jsdom has no layout engine: it reports
   * `scrollHeight` and `clientHeight` as 0 whatever the CSS says, so it
   * cannot tell a panel that scrolls from one that does not. Asserting that
   * the stylesheet contains `height: 100%` would pass while the panel was
   * still broken by some other rule, which is worse than no test — it reads
   * like coverage.
   *
   * Verified in a real browser instead, at 390x844:
   *   before  height 970.5px, clientHeight 971, canScroll false,
   *           last group at top: 851 (off screen)
   *   after   height 844px,   clientHeight 844, canScroll true,
   *           scrolls to 127, last option fully visible at bottom 784
   *
   * If this breaks again, measure it the same way rather than trusting the
   * suite.
   */
  it.skip('cannot be tested here — see the comment above', () => {})
})
