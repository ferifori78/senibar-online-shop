<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'

import AdminLayout from '@/components/layout/AdminLayout.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import StatusLamp from '@/components/admin/StatusLamp.vue'
import { useSupportStore } from '@/stores/support'
import {
  TICKET_PRIORITY,
  formatDateTime,
  formatNumber,
  ticketStatusLabel,
  ticketStatusState,
  timeAgo,
} from '@/utils/format'

const support = useSupportStore()

const selected = ref(null)
const draft = ref('')
const internal = ref(false)
const thread = ref(null)

const TABS = [
  { value: 'needs_reply', label: 'NEEDS REPLY', key: 'open' },
  { value: 'open', label: 'ACTIVE', key: null },
  { value: 'all', label: 'ALL', key: 'total' },
  { value: 'closed', label: 'CLOSED', key: 'closed' },
]

const ticket = computed(() => support.ticket)

function countFor(tab) {
  if (!support.summary || !tab.key) return null
  return support.summary[tab.key]
}

async function open(reference) {
  selected.value = reference
  draft.value = ''
  internal.value = false
  await support.fetchTicket(reference)
  await scrollToLatest()
}

async function scrollToLatest() {
  await nextTick()
  const box = thread.value
  if (box) box.scrollTop = box.scrollHeight
}

async function send() {
  const body = draft.value.trim()
  if (!body) return

  const { ok } = await support.reply(selected.value, body, { isInternal: internal.value })
  if (ok) {
    draft.value = ''
    internal.value = false
    support.fetchSummary()
    await scrollToLatest()
  }
}

/** Ctrl/Cmd+Enter sends — the operator's hands stay on the keyboard. */
function onKeydown(event) {
  if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
    event.preventDefault()
    send()
  }
}

async function toggleClosed() {
  const action = support.isClosed ? support.reopenTicket : support.closeTicket
  await action(selected.value)
  support.fetchSummary()
}

async function refresh() {
  await support.fetchTickets()
  support.fetchSummary()
}

watch(
  () => support.state,
  () => {
    selected.value = null
  },
)

onMounted(async () => {
  support.state = 'needs_reply'
  await refresh()
  // Open the oldest waiting ticket so the operator lands on work, not a blank.
  if (support.tickets.length) open(support.tickets[support.tickets.length - 1].reference)
})
</script>

<template>
  <AdminLayout>
    <!-- Tabs ----------------------------------------------------------- -->
    <div class="bar">
      <div class="bar__tabs" role="tablist" aria-label="فیلتر تیکت‌ها">
        <button
          v-for="tab in TABS"
          :key="tab.value"
          type="button"
          role="tab"
          class="bar__tab"
          :class="{ 'bar__tab--on': support.state === tab.value }"
          :aria-selected="support.state === tab.value"
          @click="support.setState(tab.value)"
        >
          {{ tab.label }}
          <span v-if="countFor(tab) !== null" class="bar__badge">{{ countFor(tab) }}</span>
        </button>
      </div>

      <span v-if="support.summary" class="bar__stat">
        <StatusLamp state="warn" :label="`${formatNumber(support.summary.unread)} UNREAD`" />
      </span>

      <button type="button" class="bar__refresh" @click="refresh">RELOAD</button>
    </div>

    <p v-if="support.error && !ticket" class="err" role="alert">{{ support.error }}</p>

    <!-- Two panes: the list, and the open conversation. ----------------- -->
    <div class="panes">
      <!-- Inbox list -->
      <aside class="inbox" aria-label="اینباکس تیکت‌ها">
        <p v-if="support.loading && !support.tickets.length" class="inbox__msg">LOADING…</p>
        <p v-else-if="support.isEmpty" class="inbox__msg">هیچ تیکتی در این نما نیست.</p>

        <button
          v-for="row in support.tickets"
          v-else
          :key="row.reference"
          type="button"
          class="row"
          :class="{ 'row--on': selected === row.reference, 'row--unread': row.unread }"
          @click="open(row.reference)"
        >
          <span class="row__top">
            <span class="row__ref">{{ row.reference }}</span>
            <span class="row__time">{{ timeAgo(row.last_message_at || row.created_at) }}</span>
          </span>

          <span class="row__subject">{{ row.subject }}</span>
          <span class="row__preview">{{ row.preview }}</span>

          <span class="row__foot">
            <StatusLamp :status="row.status" />
            <span class="row__customer">{{ row.customer }}</span>
            <span v-if="row.priority !== 'normal'" class="row__priority">
              {{ TICKET_PRIORITY[row.priority]?.label }}
            </span>
          </span>
        </button>
      </aside>

      <!-- Conversation -->
      <section class="conv">
        <p v-if="!selected" class="conv__blank">یک تیکت را از فهرست انتخاب کنید.</p>

        <p v-else-if="support.detailLoading" class="conv__blank">LOADING…</p>

        <template v-else-if="ticket">
          <header class="conv__head">
            <div class="conv__id">
              <span class="conv__ref">{{ ticket.reference }}</span>
              <StatusLamp :status="ticket.status" />
            </div>

            <div class="conv__meta">
              <span>{{ ticket.customer }}</span>
              <span class="conv__dim">{{ ticket.customer_email }}</span>
              <span v-if="ticket.order_number" class="conv__dim">
                سفارش {{ ticket.order_number }}
              </span>
            </div>
          </header>

          <h2 class="conv__subject">{{ ticket.subject }}</h2>
          <p class="conv__topic">
            {{ ticket.topic_display }} · باز شده {{ formatDateTime(ticket.created_at) }}
          </p>

          <!-- Messages -->
          <div ref="thread" class="conv__thread">
            <article
              v-for="message in support.messages"
              :key="message.id"
              class="m"
              :class="[`m--${message.author_role}`, { 'm--internal': message.is_internal }]"
            >
              <header class="m__head">
                <span class="m__author">
                  {{ message.author_name }}
                  <span v-if="message.is_internal" class="m__tag">INTERNAL</span>
                </span>
                <span class="m__time">{{ formatDateTime(message.created_at) }}</span>
              </header>
              <p class="m__body">{{ message.body }}</p>
            </article>
          </div>

          <!-- Quick reply -->
          <footer class="conv__reply">
            <p v-if="support.error" class="err" role="alert">{{ support.error }}</p>

            <textarea
              v-model="draft"
              class="conv__input"
              :class="{ 'conv__input--internal': internal }"
              rows="3"
              :placeholder="
                internal
                  ? 'یادداشت داخلی — مشتری این را نمی‌بیند'
                  : 'پاسخ سریع — Ctrl+Enter برای ارسال'
              "
              @keydown="onKeydown"
            />

            <div class="conv__actions">
              <BaseButton
                variant="primary"
                size="sm"
                inverse
                :loading="support.sending"
                :disabled="!draft.trim()"
                @click="send"
              >
                {{ internal ? 'ثبت یادداشت' : 'ارسال پاسخ' }}
              </BaseButton>

              <button
                type="button"
                class="toggle"
                :class="{ 'toggle--on': internal }"
                :aria-pressed="internal"
                @click="internal = !internal"
              >
                <span class="toggle__box" aria-hidden="true" />
                یادداشت داخلی
              </button>

              <button type="button" class="conv__close" @click="toggleClosed">
                {{ support.isClosed ? 'REOPEN' : 'CLOSE' }}
              </button>
            </div>
          </footer>
        </template>
      </section>
    </div>
  </AdminLayout>
</template>

<style scoped>
/* ==========================================================================
   AdminSupportView — Terminal register
   Two panes: a dense inbox and the open conversation beside it.
   ========================================================================== */

.bar {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
}

.bar__tabs {
  display: flex;
}

.bar__tab {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  border: 2px solid var(--terminal-rule);
  border-inline-end-width: 0;
  background: none;
  color: var(--terminal-dim);
  font-family: var(--font-terminal);
  font-size: 0.5625rem;
  letter-spacing: 0.12em;
  padding: 0.375rem 0.5625rem;
  cursor: pointer;
}

.bar__tab:last-child {
  border-inline-end-width: 2px;
}

.bar__tab:hover {
  color: var(--terminal-text);
  background-color: var(--terminal-raised);
}

.bar__tab--on {
  background-color: var(--accent);
  border-color: var(--accent);
  color: var(--paper);
}

.bar__tab:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  position: relative;
}

.bar__badge {
  border: 1px solid currentColor;
  font-size: 0.5rem;
  padding: 0 0.1875rem;
}

.bar__stat {
  margin-inline-start: auto;
}

.bar__refresh {
  border: 2px solid var(--terminal-rule);
  background: none;
  color: var(--terminal-dim);
  font-family: var(--font-terminal);
  font-size: 0.5rem;
  letter-spacing: 0.14em;
  padding: 0.3125rem 0.5rem;
  cursor: pointer;
}

.bar__refresh:hover {
  border-color: var(--terminal-text);
  color: var(--terminal-text);
}

.err {
  border: 2px solid #a33224;
  background-color: #a33224;
  color: var(--paper);
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  padding: 0.5rem 0.625rem;
  margin: 0 0 0.75rem;
}

/* --- Panes ----------------------------------------------------------------- */
.panes {
  display: grid;
  grid-template-columns: 22rem minmax(0, 1fr);
  gap: 0;
  border: 3px solid var(--terminal-text);
  height: calc(100vh - 11rem);
  min-height: 32rem;
}

@media (max-width: 62rem) {
  .panes {
    grid-template-columns: 1fr;
    height: auto;
  }
}

/* --- Inbox ----------------------------------------------------------------- */
.inbox {
  border-inline-end: 3px solid var(--terminal-text);
  overflow-y: auto;
}

@media (max-width: 62rem) {
  .inbox {
    border-inline-end: 0;
    border-bottom: 3px solid var(--terminal-text);
    max-height: 22rem;
  }
}

.inbox__msg {
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.12em;
  color: var(--terminal-dim);
  padding: 2rem 1rem;
  text-align: center;
}

.row {
  display: flex;
  flex-direction: column;
  gap: 0.3125rem;
  width: 100%;
  border: 0;
  border-bottom: 1px solid var(--terminal-rule);
  /* A start-edge marker reserves space on every row, so selecting one never
     shifts the text. */
  border-inline-start: 3px solid transparent;
  background: none;
  color: var(--terminal-text);
  text-align: start;
  padding: 0.625rem 0.75rem;
  cursor: pointer;
}

.row:hover {
  background-color: var(--terminal-raised);
}

.row--on {
  background-color: var(--terminal-raised);
  border-inline-start-color: var(--accent);
}

.row--unread .row__subject {
  font-weight: 600;
}

.row--unread .row__ref {
  color: var(--accent);
}

.row:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: -2px;
}

.row__top {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
}

.row__ref {
  font-family: var(--font-terminal);
  font-size: 0.5625rem;
  letter-spacing: 0.08em;
  color: var(--terminal-dim);
}

.row__time {
  font-family: var(--font-terminal);
  font-size: 0.5rem;
  color: var(--terminal-dim);
  white-space: nowrap;
}

.row__subject {
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.row__preview {
  font-family: var(--font-terminal);
  font-size: 0.5625rem;
  line-height: 1.5;
  color: var(--terminal-dim);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.row__foot {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  margin-top: 0.1875rem;
}

.row__customer {
  font-family: var(--font-terminal);
  font-size: 0.5rem;
  color: var(--terminal-dim);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.row__priority {
  border: 1px solid var(--accent);
  color: var(--accent);
  font-family: var(--font-terminal);
  font-size: 0.4375rem;
  letter-spacing: 0.12em;
  padding: 0 0.1875rem;
  margin-inline-start: auto;
}

/* --- Conversation ---------------------------------------------------------- */
.conv {
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 0.875rem 1rem;
}

.conv__blank {
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.12em;
  color: var(--terminal-dim);
  margin: auto;
}

.conv__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  padding-bottom: 0.625rem;
  border-bottom: 1px solid var(--terminal-rule);
}

.conv__id {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.conv__ref {
  font-family: var(--font-terminal);
  font-size: 0.75rem;
  letter-spacing: 0.08em;
  font-weight: 600;
}

.conv__meta {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-family: var(--font-terminal);
  font-size: 0.5625rem;
}

.conv__dim {
  color: var(--terminal-dim);
}

.conv__subject {
  font-family: var(--font-terminal);
  font-size: 0.8125rem;
  line-height: 1.4;
  font-weight: 500;
  margin: 0.75rem 0 0.25rem;
}

.conv__topic {
  font-family: var(--font-terminal);
  font-size: 0.5rem;
  letter-spacing: 0.1em;
  color: var(--terminal-dim);
  margin: 0 0 0.75rem;
}

/* --- Thread ---------------------------------------------------------------- */
.conv__thread {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.625rem;
  padding: 0.625rem 0;
  border-top: 1px solid var(--terminal-rule);
  min-height: 8rem;
}

.m {
  border: 2px solid var(--terminal-rule);
  padding: 0.625rem 0.75rem;
}

/* The customer's messages sit raised; ours stay flat on the ground, so the
   operator's eye finds incoming text first. */
.m--customer {
  background-color: var(--terminal-raised);
  border-color: var(--terminal-text);
}

.m--staff {
  border-inline-start: 3px solid var(--accent);
}

/* Internal notes are visibly not part of the conversation. */
.m--internal {
  border-style: dashed;
  border-color: var(--terminal-dim);
  background: none;
  opacity: 0.85;
}

.m__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.4375rem;
}

.m__author {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  font-family: var(--font-terminal);
  font-size: 0.5625rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.m--staff .m__author {
  color: var(--accent);
}

.m__tag {
  border: 1px solid var(--terminal-dim);
  color: var(--terminal-dim);
  font-size: 0.4375rem;
  letter-spacing: 0.12em;
  padding: 0 0.1875rem;
}

.m__time {
  font-family: var(--font-terminal);
  font-size: 0.5rem;
  color: var(--terminal-dim);
  white-space: nowrap;
}

.m__body {
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  line-height: 1.7;
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

/* --- Reply ----------------------------------------------------------------- */
.conv__reply {
  padding-top: 0.75rem;
  border-top: 3px solid var(--terminal-text);
}

.conv__input {
  width: 100%;
  border: 2px solid var(--terminal-rule);
  background-color: var(--terminal);
  color: var(--terminal-text);
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  line-height: 1.7;
  padding: 0.5rem 0.625rem;
  resize: vertical;
}

.conv__input::placeholder {
  color: var(--terminal-dim);
}

.conv__input:focus {
  outline: none;
  border-color: var(--terminal-text);
  box-shadow: 3px 3px 0 var(--accent);
}

.conv__input--internal {
  border-style: dashed;
  border-color: var(--terminal-dim);
}

.conv__actions {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
  margin-top: 0.75rem;
}

.toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.4375rem;
  border: 0;
  background: none;
  color: var(--terminal-dim);
  font-family: var(--font-terminal);
  font-size: 0.5625rem;
  letter-spacing: 0.1em;
  cursor: pointer;
  padding: 0;
}

.toggle--on {
  color: var(--terminal-text);
}

.toggle__box {
  width: 0.75rem;
  height: 0.75rem;
  border: 2px solid var(--terminal-rule);
}

.toggle--on .toggle__box {
  background-color: var(--accent);
  border-color: var(--accent);
}

.toggle:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.conv__close {
  margin-inline-start: auto;
  border: 2px solid var(--terminal-rule);
  background: none;
  color: var(--terminal-dim);
  font-family: var(--font-terminal);
  font-size: 0.5rem;
  letter-spacing: 0.14em;
  padding: 0.25rem 0.5rem;
  cursor: pointer;
}

.conv__close:hover {
  border-color: var(--terminal-text);
  color: var(--terminal-text);
}
</style>
