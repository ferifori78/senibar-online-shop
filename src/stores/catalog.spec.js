import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/catalog', () => ({
  default: { list: vi.fn(), facets: vi.fn(), detail: vi.fn(), batches: vi.fn() },
}))

import catalogApi from '@/api/catalog'
import { useCatalogStore } from './catalog'

/*
 * These pin the query the store actually sends. The filters are multi-value
 * on the wire — a comma-separated list — and getting that wrong is invisible
 * on screen: the grid just quietly shows the wrong products.
 */

function listReply(results = []) {
  return { data: { results, count: results.length, next: null } }
}

describe('catalog store — filters', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    catalogApi.list.mockResolvedValue(listReply())
  })

  it('starts with every filter group empty', () => {
    const catalog = useCatalogStore()
    expect(catalog.filters.kind).toEqual([])
    expect(catalog.filters.species).toEqual([])
    expect(catalog.filters.origin_type).toEqual([])
    expect(catalog.activeFilterCount).toBe(0)
  })

  it('sends several values in one group as a comma-separated list', async () => {
    const catalog = useCatalogStore()
    await catalog.applyFilters({ species: ['arabica', 'blend'] })

    const params = catalogApi.list.mock.calls.at(-1)[0]
    // Not `species[]` and not two keys: django-filter's BaseInFilter splits
    // on the comma, and anything else silently matches nothing.
    expect(params.species).toBe('arabica,blend')
  })

  it('omits a group nobody has touched', async () => {
    const catalog = useCatalogStore()
    await catalog.applyFilters({ kind: ['pantry'] })

    const params = catalogApi.list.mock.calls.at(-1)[0]
    expect(params.kind).toBe('pantry')
    // An empty `?species=` is not the same as no species filter: it would
    // reach the backend as a request for products whose species is "".
    expect(params).not.toHaveProperty('species')
    expect(params).not.toHaveProperty('origin_type')
  })

  it('counts each active group once, ignoring search and ordering', async () => {
    const catalog = useCatalogStore()
    await catalog.applyFilters({
      kind: ['lot'],
      species: ['arabica', 'robusta'],
      search: 'یرگاچف',
      ordering: '-created_at',
    })

    // Two groups are narrowing the result, whatever the number of values in
    // them. Search has its own visible input and sorting narrows nothing.
    expect(catalog.activeFilterCount).toBe(2)
  })

  it('goes back to page one when a filter changes', async () => {
    const catalog = useCatalogStore()
    catalogApi.list.mockResolvedValue({
      data: { results: [{ id: 1 }], count: 40, next: 'page=2' },
    })
    await catalog.fetchProducts()
    await catalog.loadMore()
    expect(catalog.page).toBe(2)

    await catalog.applyFilters({ kind: ['pantry'] })
    // Staying on page 2 would page into the middle of a different, shorter
    // result set and show an empty grid over a non-empty catalogue.
    expect(catalog.page).toBe(1)
    expect(catalogApi.list.mock.calls.at(-1)[0].page).toBe(1)
  })

  it('clears every group on reset, including the newest ones', async () => {
    const catalog = useCatalogStore()
    await catalog.applyFilters({
      kind: ['pantry'],
      species: ['arabica'],
      origin_type: ['multi'],
      in_stock: true,
    })
    expect(catalog.activeFilterCount).toBe(4)

    await catalog.resetFilters()
    // The bug this pins: `resetFilters` used to repeat the filter shape as a
    // second literal, so a group added to one and not the other stayed
    // applied after "clear all" with nothing on screen to explain it.
    expect(catalog.activeFilterCount).toBe(0)
    expect(catalog.filters.species).toEqual([])
    expect(catalog.filters.origin_type).toEqual([])
  })
})
