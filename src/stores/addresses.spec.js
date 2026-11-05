import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/auth', () => ({
  default: {
    addresses: vi.fn(),
    createAddress: vi.fn(),
    updateAddress: vi.fn(),
    deleteAddress: vi.fn(),
  },
}))

import authApi from '@/api/auth'
import { blankAddress, useAddressStore } from './addresses'

const HOME = {
  id: 1,
  label: 'خانه',
  recipient_name: 'سپیده',
  phone: '09120000000',
  province: 'تهران',
  city: 'تهران',
  street_address: 'خیابان یکم',
  postal_code: '1234567890',
  is_default: true,
}

const WORK = { ...HOME, id: 2, label: 'محل کار', is_default: false }

describe('addresses store', () => {
  /** The endpoint may answer with a bare list or a paginated envelope. */
  function resolveWith(list) {
    authApi.addresses.mockResolvedValue({ data: list })
  }

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('reads both a bare list and a paginated envelope', async () => {
    const store = useAddressStore()
    resolveWith([HOME, WORK])
    await store.fetchAddresses()
    expect(store.addresses).toHaveLength(2)

    setActivePinia(createPinia())
    const paged = useAddressStore()
    authApi.addresses.mockResolvedValue({ data: { count: 1, results: [HOME] } })
    await paged.fetchAddresses()
    expect(paged.addresses).toHaveLength(1)
  })

  it('does not refetch once loaded, unless forced', async () => {
    const store = useAddressStore()
    resolveWith([HOME])

    await store.fetchAddresses()
    await store.fetchAddresses()
    expect(authApi.addresses).toHaveBeenCalledTimes(1)

    await store.fetchAddresses({ force: true })
    expect(authApi.addresses).toHaveBeenCalledTimes(2)
  })

  it('demotes the previous default locally, so two are never shown at once', async () => {
    const store = useAddressStore()
    resolveWith([HOME, WORK])
    await store.fetchAddresses()

    // The server demotes HOME when WORK becomes the default; mirror it.
    authApi.updateAddress.mockResolvedValue({ data: { ...WORK, is_default: true } })
    await store.makeDefault(2)

    const defaults = store.addresses.filter((a) => a.is_default)
    expect(defaults).toHaveLength(1)
    expect(defaults[0].id).toBe(2)
  })

  it('appends a new address rather than replacing the list', async () => {
    const store = useAddressStore()
    resolveWith([HOME])
    await store.fetchAddresses()

    authApi.createAddress.mockResolvedValue({ data: WORK })
    const result = await store.save({ ...blankAddress(), city: 'کرج' })

    expect(result.ok).toBe(true)
    expect(store.addresses.map((a) => a.id)).toEqual([1, 2])
  })

  it('updates in place when editing', async () => {
    const store = useAddressStore()
    resolveWith([HOME, WORK])
    await store.fetchAddresses()

    authApi.updateAddress.mockResolvedValue({ data: { ...WORK, city: 'کرج' } })
    await store.save({ city: 'کرج' }, 2)

    expect(store.addresses).toHaveLength(2)
    expect(store.addresses[1].city).toBe('کرج')
  })

  it('drops a removed address from the list', async () => {
    const store = useAddressStore()
    resolveWith([HOME, WORK])
    await store.fetchAddresses()

    authApi.deleteAddress.mockResolvedValue({})
    await store.remove(1)

    expect(store.addresses.map((a) => a.id)).toEqual([2])
  })

  it('keeps the list intact when a delete fails', async () => {
    const store = useAddressStore()
    resolveWith([HOME])
    await store.fetchAddresses()

    authApi.deleteAddress.mockRejectedValue({ response: { status: 500, data: {} } })
    const result = await store.remove(1)

    expect(result.ok).toBe(false)
    expect(store.addresses).toHaveLength(1)
    expect(store.error).toBeTruthy()
  })

  it('surfaces field errors for the form to render', async () => {
    const store = useAddressStore()
    authApi.createAddress.mockRejectedValue({
      response: { status: 400, data: { postal_code: ['کد پستی باید ۱۰ رقم باشد.'] } },
    })

    await store.save(blankAddress())

    expect(store.fieldErrors.postal_code).toContain('۱۰ رقم')
  })

  it('reports the default address, falling back to the first', async () => {
    const store = useAddressStore()
    resolveWith([WORK, HOME])
    await store.fetchAddresses()
    expect(store.defaultAddress.id).toBe(1) // HOME is flagged default

    setActivePinia(createPinia())
    const noDefault = useAddressStore()
    authApi.addresses.mockResolvedValue({ data: [WORK] })
    await noDefault.fetchAddresses()
    expect(noDefault.defaultAddress.id).toBe(2)
  })

  it('is only empty after a load has actually happened', async () => {
    const store = useAddressStore()
    // Before loading, an empty list must not render the empty state.
    expect(store.isEmpty).toBe(false)

    resolveWith([])
    await store.fetchAddresses()
    expect(store.isEmpty).toBe(true)
  })
})
