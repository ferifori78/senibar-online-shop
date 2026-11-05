<script setup>
import { nextTick, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import BaseButton from '@/components/base/BaseButton.vue'
import { useSupportStore } from '@/stores/support'
import {
  formatDateTime,
  ticketStatusLabel,
  ticketStatusState,
  timeAgo,
} from '@/utils/format'

const route = useRoute()
const support = useSupportStore()

const draft = ref('')
const thread = ref(null)

async function send() {
  const body = draft.value.trim()
  if (!body) return

  const { ok } = await support.reply(route.params.reference, body)
  if (ok) {
    draft.value = ''
    await scrollToLatest()
  }
}

/** Enter sends; Shift+Enter breaks the line. */
function onKeydown(event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    send()
  }
}

async function scrollToLatest() {
  await nextTick()
  const last = thread.value?.lastElementChild
  last?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
}

watch(
  () => route.params.reference,
  async (reference) => {
    if (!reference) return
    await support.fetchTicket(reference)
    await scrollToLatest()
  },
  { immediate: true },
)
</script>

<template>
  <main class="register-editorial ticket">
    <div v-if="support.detailLoading" class="ticket__loading">در حال بارگذاری…</div>

    <div v-else-if="!support.ticket" class="ticket__missing">
      <p>{{ support.error || 'این تیکت پیدا نشد.' }}</p>
      <RouterLink to="/support"><BaseButton variant="secondary">تیکت‌های من</BaseButton></RouterLink>
    </div>

    <template v-else>
      <nav class="ticket__crumbs" aria-label="مسیر">
        <RouterLink to="/support" class="ticket__crumb">پشتیبانی</RouterLink>
        <span aria-hidden="true">/</span>
        <span>{{ support.ticket.reference }}</span>
      </nav>

      <header class="ticket__header">
        <div>
          <p class="ticket__eyebrow">
            {{ support.ticket.reference }} · {{ support.ticket.topic_display }}
          </p>
          <h1 class="ticket__subject">{{ support.ticket.subject }}</h1>
          <p class="ticket__opened">
            باز شده در {{ formatDateTime(support.ticket.created_at) }}
            <template v-if="support.ticket.order_number">
              · درباره سفارش
              <RouterLink
                :to="`/orders/${support.ticket.order_number}`"
                class="ticket__order-link"
              >
                {{ support.ticket.order_number }}
              </RouterLink>
            </template>
          </p>
        </div>

        <span class="ticket__status">
          <span class="status-light" :data-state="ticketStatusState(support.ticket.status)" />
          {{ ticketStatusLabel(support.ticket.status) }}
        </span>
      </header>

      <!-- Thread ------------------------------------------------------- -->
      <div ref="thread" class="thread">
        <article
          v-for="message in support.messages"
          :key="message.id"
          class="msg"
          :class="`msg--${message.author_role}`"
        >
          <header class="msg__head">
            <span class="msg__author">{{ message.author_name }}</span>
            <span class="msg__time" :title="formatDateTime(message.created_at)">
              {{ timeAgo(message.created_at) }}
            </span>
          </header>
          <p class="msg__body">{{ message.body }}</p>
        </article>
      </div>

      <!-- Composer ----------------------------------------------------- -->
      <section class="reply">
        <p v-if="support.error" class="err" role="alert">{{ support.error }}</p>

        <template v-if="!support.isClosed">
          <label class="reply__label" for="reply-body">پاسخ شما</label>
          <textarea
            id="reply-body"
            v-model="draft"
            class="reply__input"
            rows="4"
            placeholder="پیام خود را بنویسید — Enter برای ارسال، Shift+Enter برای خط جدید"
            @keydown="onKeydown"
          />
          <div class="reply__actions">
            <BaseButton
              variant="primary"
              :loading="support.sending"
              :disabled="!draft.trim()"
              @click="send"
            >
              ارسال پیام
            </BaseButton>
            <BaseButton
              variant="ghost"
              :disabled="support.sending"
              @click="support.closeTicket(support.ticket.reference)"
            >
              بستن تیکت
            </BaseButton>
          </div>
        </template>

        <div v-else class="closed">
          <p class="closed__text">
            این تیکت بسته شده است. اگر همچنان سؤالی دارید، آن را باز کنید یا پیام تازه‌ای
            بفرستید.
          </p>
          <BaseButton
            variant="secondary"
            :loading="support.sending"
            @click="support.reopenTicket(support.ticket.reference)"
          >
            بازگشایی تیکت
          </BaseButton>
        </div>
      </section>
    </template>
  </main>
</template>

<style scoped>
/* ==========================================================================
   TicketDetailView — Editorial register
   A conversation on paper: messages are ruled blocks, not chat bubbles.
   The customer's own messages sit inset and framed; ours sit flush.
   ========================================================================== */

.ticket {
  padding: clamp(2rem, 6vw, 4rem) clamp(1.25rem, 5vw, 4rem) 6rem;
  max-width: 52rem;
  margin-inline: auto;
}

.ticket__loading,
.ticket__missing {
  font-family: var(--font-terminal);
  font-size: 0.75rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
  padding: 6rem 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 1.5rem;
}

.ticket__crumbs {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
  margin-bottom: 2rem;
}

.ticket__crumb {
  color: var(--ink-muted);
  text-decoration: none;
  border-bottom: 2px solid transparent;
}
.ticket__crumb:hover {
  color: var(--ink);
  border-bottom-color: var(--accent);
}

/* --- Header ---------------------------------------------------------------- */
.ticket__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1.5rem;
  flex-wrap: wrap;
  padding-bottom: 1.75rem;
  border-bottom: 3px solid var(--divider);
}

.ticket__eyebrow {
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
  margin: 0;
}

.ticket__subject {
  font-family: var(--font-editorial);
  font-size: clamp(1.5rem, 4vw, 2.125rem);
  line-height: 1.25;
  font-weight: 600;
  margin: 0.625rem 0 0;
}

.ticket__opened {
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.08em;
  color: var(--ink-muted);
  margin: 0.625rem 0 0;
}

.ticket__order-link {
  color: var(--accent);
  text-decoration: none;
  border-bottom: 2px solid var(--accent);
}

.ticket__status {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  border: 3px solid var(--ink);
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  padding: 0.4375rem 0.75rem;
  flex: none;
}

/* --- Thread ---------------------------------------------------------------- */
.thread {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  margin: 2.5rem 0;
}

.msg {
  border: 3px solid var(--ink);
  padding: 1.125rem 1.25rem;
}

/* The customer's own words sit on a recessed ground and indent from the
   start edge — the roastery's replies sit flush on paper. Direction, not
   colour, marks who is speaking. */
.msg--customer {
  background-color: var(--paper-sunk);
  margin-inline-start: clamp(0rem, 8vw, 4rem);
}

.msg--staff {
  background-color: var(--paper);
  margin-inline-end: clamp(0rem, 8vw, 4rem);
  box-shadow: 5px 5px 0 var(--shadow);
}

.msg--system {
  border-style: dashed;
  border-color: var(--rule);
  background: none;
}

.msg__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.75rem;
  padding-bottom: 0.625rem;
  border-bottom: 1px solid var(--rule);
}

.msg__author {
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-weight: 500;
}

/* Support's name carries the accent — the only colour in the thread. */
.msg--staff .msg__author {
  color: var(--accent);
}

.msg__time {
  font-family: var(--font-terminal);
  font-size: 0.5625rem;
  letter-spacing: 0.08em;
  color: var(--ink-muted);
  white-space: nowrap;
}

.msg__body {
  font-family: var(--font-editorial);
  font-size: 1rem;
  line-height: 1.8;
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

/* --- Reply ----------------------------------------------------------------- */
.reply {
  padding-top: 2rem;
  border-top: 3px solid var(--ink);
}

.reply__label {
  display: block;
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-weight: 500;
  margin-bottom: 0.75rem;
}

.reply__input {
  width: 100%;
  border: 3px solid var(--ink);
  background-color: var(--paper);
  color: var(--ink);
  font-family: var(--font-editorial);
  font-size: 1rem;
  line-height: 1.75;
  padding: 0.875rem 1rem;
  resize: vertical;
}

.reply__input::placeholder {
  font-family: var(--font-terminal);
  font-size: 0.75rem;
  color: var(--ink-muted);
}

.reply__input:focus {
  outline: none;
  box-shadow: 4px 4px 0 var(--accent);
}

.reply__actions {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  margin-top: 1.25rem;
}

.err {
  border: 3px solid #a33224;
  background-color: #a33224;
  color: var(--paper);
  font-family: var(--font-terminal);
  font-size: 0.75rem;
  padding: 0.75rem 0.875rem;
  margin: 0 0 1.25rem;
}

/* --- Closed ---------------------------------------------------------------- */
.closed {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 1.25rem;
  border: 3px dashed var(--rule);
  padding: 1.5rem;
}

.closed__text {
  font-family: var(--font-editorial);
  font-size: 1rem;
  line-height: 1.75;
  color: var(--ink-muted);
  margin: 0;
}
</style>
