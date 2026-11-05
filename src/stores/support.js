import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import supportApi from '@/api/support'
import { parseApiError } from '@/api/client'

export const useSupportStore = defineStore('support', () => {
  const tickets = ref([])
  const ticket = ref(null)
  const summary = ref(null)

  const count = ref(0)
  const state = ref('all') // all | open | closed | needs_reply

  const loading = ref(false)
  const detailLoading = ref(false)
  const sending = ref(false)
  const error = ref('')
  const fieldErrors = ref({})

  const isEmpty = computed(() => !loading.value && tickets.value.length === 0)
  const messages = computed(() => ticket.value?.messages || [])
  const isClosed = computed(() => ticket.value?.status === 'closed')

  function resetErrors() {
    error.value = ''
    fieldErrors.value = {}
  }

  function captureError(err, fallback) {
    const parsed = parseApiError(err)
    const useful = parsed.message && parsed.message !== 'خطای ناشناخته.'
    error.value = useful ? parsed.message : fallback
    fieldErrors.value = parsed.fields
    return parsed
  }

  async function fetchTickets(params = {}) {
    loading.value = true
    resetErrors()
    try {
      const query = { ...params }
      if (state.value !== 'all') query.state = state.value

      const { data } = await supportApi.list(query)
      tickets.value = data.results
      count.value = data.count
    } catch (err) {
      captureError(err, 'دریافت تیکت‌ها ناموفق بود.')
      tickets.value = []
    } finally {
      loading.value = false
    }
  }

  function setState(next) {
    state.value = next
    return fetchTickets()
  }

  async function fetchTicket(reference) {
    detailLoading.value = true
    resetErrors()
    ticket.value = null
    try {
      const { data } = await supportApi.detail(reference)
      ticket.value = data

      // The server cleared our unread badge on read; mirror that locally so
      // the inbox row stops shouting without a refetch.
      const row = tickets.value.find((t) => t.reference === reference)
      if (row) row.unread = 0
    } catch (err) {
      captureError(err, 'این تیکت پیدا نشد.')
    } finally {
      detailLoading.value = false
    }
  }

  async function createTicket(payload) {
    sending.value = true
    resetErrors()
    try {
      const { data } = await supportApi.create(payload)
      ticket.value = data
      tickets.value.unshift(data)
      return { ok: true, data }
    } catch (err) {
      captureError(err, 'ثبت تیکت ناموفق بود.')
      return { ok: false, error: err }
    } finally {
      sending.value = false
    }
  }

  /** Post a message. The response carries the whole refreshed thread, so the
   *  view never has to guess what the new status is. */
  async function reply(reference, body, { isInternal = false } = {}) {
    sending.value = true
    resetErrors()
    try {
      const { data } = await supportApi.reply(reference, {
        body,
        is_internal: isInternal,
      })
      ticket.value = data.ticket
      syncRow(data.ticket)
      return { ok: true, data }
    } catch (err) {
      captureError(err, 'ارسال پیام ناموفق بود.')
      return { ok: false, error: err }
    } finally {
      sending.value = false
    }
  }

  /** Keep the matching inbox row in step with a changed thread. */
  function syncRow(updated) {
    const index = tickets.value.findIndex((t) => t.reference === updated.reference)
    if (index === -1) return
    tickets.value[index] = {
      ...tickets.value[index],
      status: updated.status,
      status_display: updated.status_display,
      last_message_at: updated.last_message_at,
      unread: 0,
    }
  }

  async function closeTicket(reference, note = '') {
    sending.value = true
    resetErrors()
    try {
      const { data } = await supportApi.close(reference, note)
      ticket.value = data
      syncRow(data)
      return { ok: true, data }
    } catch (err) {
      captureError(err, 'بستن تیکت ناموفق بود.')
      return { ok: false, error: err }
    } finally {
      sending.value = false
    }
  }

  async function reopenTicket(reference) {
    sending.value = true
    resetErrors()
    try {
      const { data } = await supportApi.reopen(reference)
      ticket.value = data
      syncRow(data)
      return { ok: true, data }
    } catch (err) {
      captureError(err, 'بازگشایی تیکت ناموفق بود.')
      return { ok: false, error: err }
    } finally {
      sending.value = false
    }
  }

  async function fetchSummary() {
    try {
      const { data } = await supportApi.inboxSummary()
      summary.value = data
    } catch {
      summary.value = null
    }
  }

  return {
    tickets,
    ticket,
    summary,
    count,
    state,
    loading,
    detailLoading,
    sending,
    error,
    fieldErrors,
    isEmpty,
    messages,
    isClosed,
    resetErrors,
    fetchTickets,
    fetchTicket,
    setState,
    createTicket,
    reply,
    closeTicket,
    reopenTicket,
    fetchSummary,
  }
})
