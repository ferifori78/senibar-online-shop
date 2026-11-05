import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import authApi from '@/api/auth'
import { useApiErrors } from './errors'

/** The shape a blank address form starts from. */
export function blankAddress() {
  return {
    label: '',
    recipient_name: '',
    phone: '',
    province: '',
    city: '',
    street_address: '',
    postal_code: '',
    is_default: false,
  }
}

export const useAddressStore = defineStore('addresses', () => {
  const addresses = ref([])
  const loaded = ref(false)

  const loading = ref(false)
  const acting = ref(false)
  const error = ref('')
  const fieldErrors = ref({})

  // The address form shows each error under its own field, so folding them
  // into the banner would print every message twice.
  const { capture, reset: resetErrors } = useApiErrors(error, fieldErrors)

  const isEmpty = computed(() => loaded.value && addresses.value.length === 0)

  const defaultAddress = computed(
    () => addresses.value.find((a) => a.is_default) || addresses.value[0] || null,
  )

  async function fetchAddresses({ force = false } = {}) {
    if (loaded.value && !force) return addresses.value
    loading.value = true
    resetErrors()
    try {
      const { data } = await authApi.addresses()
      // The endpoint is paginated by the global DRF setting; a user will never
      // have 24 addresses, but read both shapes rather than assume.
      addresses.value = Array.isArray(data) ? data : data.results || []
      loaded.value = true
      return addresses.value
    } catch (err) {
      capture(err, 'دریافت آدرس‌ها ناموفق بود.')
      return []
    } finally {
      loading.value = false
    }
  }

  /** Only one address is default; mirror the server's demotion locally so the
   *  list does not briefly show two. */
  function applyDefault(saved) {
    if (!saved.is_default) return
    addresses.value = addresses.value.map((a) =>
      a.id === saved.id ? a : { ...a, is_default: false },
    )
  }

  async function save(payload, id = null) {
    acting.value = true
    resetErrors()
    try {
      const { data } = id
        ? await authApi.updateAddress(id, payload)
        : await authApi.createAddress(payload)

      const index = addresses.value.findIndex((a) => a.id === data.id)
      if (index === -1) addresses.value.push(data)
      else addresses.value[index] = data

      applyDefault(data)
      return { ok: true, data }
    } catch (err) {
      capture(err, id ? 'ذخیره آدرس ناموفق بود.' : 'افزودن آدرس ناموفق بود.')
      return { ok: false, error: err }
    } finally {
      acting.value = false
    }
  }

  async function remove(id) {
    acting.value = true
    resetErrors()
    try {
      await authApi.deleteAddress(id)
      addresses.value = addresses.value.filter((a) => a.id !== id)
      return { ok: true }
    } catch (err) {
      capture(err, 'حذف آدرس ناموفق بود.')
      return { ok: false, error: err }
    } finally {
      acting.value = false
    }
  }

  async function makeDefault(id) {
    // The serializer demotes the previous default for us, so a single PATCH
    // is enough.
    return save({ is_default: true }, id)
  }

  return {
    addresses,
    loaded,
    loading,
    acting,
    error,
    fieldErrors,
    isEmpty,
    defaultAddress,
    resetErrors,
    fetchAddresses,
    save,
    remove,
    makeDefault,
  }
})
