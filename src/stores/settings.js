import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import adminApi from '@/api/admin'
import { useApiErrors } from './errors'

/** A blank shipping method, as the form starts. */
export function blankMethod() {
  return {
    key: '',
    label: '',
    description: '',
    days: '',
    cost: null,
    free_over: null,
    is_active: true,
    sort_order: 0,
  }
}

export const useSettingsStore = defineStore('adminSettings', () => {
  const gateways = ref([])
  const methods = ref([])

  const loading = ref(false)
  const acting = ref(false)
  const error = ref('')
  const fieldErrors = ref({})

  // The gateway switch has no per-field UI, so a DRF validation error — such
  // as the refusal to disable the last live gateway — must reach the banner.
  const { capture, reset: resetErrors } = useApiErrors(error, fieldErrors, {
    foldFieldErrors: true,
  })

  const liveGateways = computed(() => gateways.value.filter((g) => g.is_live))

  async function fetchAll() {
    loading.value = true
    resetErrors()
    try {
      const [gw, sm] = await Promise.all([
        adminApi.gateways(),
        adminApi.shippingMethods(),
      ])
      gateways.value = gw.data.gateways || []
      methods.value = Array.isArray(sm.data) ? sm.data : sm.data.results || []
      return { ok: true }
    } catch (err) {
      capture(err, 'دریافت تنظیمات ناموفق بود.')
      return { ok: false, error: err }
    } finally {
      loading.value = false
    }
  }

  async function setGatewayEnabled(name, isEnabled, note = '') {
    acting.value = true
    resetErrors()
    try {
      const { data } = await adminApi.setGatewayEnabled(name, {
        is_enabled: isEnabled,
        note,
      })
      const index = gateways.value.findIndex((g) => g.name === name)
      if (index !== -1) gateways.value[index] = data
      return { ok: true, data }
    } catch (err) {
      // The server refuses to leave checkout with no gateway, in a sentence
      // worth showing verbatim.
      capture(err, 'تغییر وضعیت درگاه ناموفق بود.')
      return { ok: false, error: err }
    } finally {
      acting.value = false
    }
  }

  async function saveMethod(payload, id = null) {
    acting.value = true
    resetErrors()
    try {
      const { data } = id
        ? await adminApi.updateShippingMethod(id, payload)
        : await adminApi.createShippingMethod(payload)

      const index = methods.value.findIndex((m) => m.id === data.id)
      if (index === -1) methods.value.push(data)
      else methods.value[index] = data

      return { ok: true, data }
    } catch (err) {
      capture(err, 'ذخیره روش ارسال ناموفق بود.')
      return { ok: false, error: err }
    } finally {
      acting.value = false
    }
  }

  async function deleteMethod(id) {
    acting.value = true
    resetErrors()
    try {
      await adminApi.deleteShippingMethod(id)
      methods.value = methods.value.filter((m) => m.id !== id)
      return { ok: true }
    } catch (err) {
      // A method used by an order comes back 409 telling the roaster to
      // deactivate it instead.
      capture(err, 'حذف روش ارسال ناموفق بود.')
      return { ok: false, error: err }
    } finally {
      acting.value = false
    }
  }

  return {
    gateways,
    methods,
    loading,
    acting,
    error,
    fieldErrors,
    liveGateways,
    resetErrors,
    fetchAll,
    setGatewayEnabled,
    saveMethod,
    deleteMethod,
  }
})
