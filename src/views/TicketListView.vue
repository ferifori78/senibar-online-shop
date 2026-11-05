<script setup>
import { onMounted, reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import BaseButton from '@/components/base/BaseButton.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import LoadingState from '@/components/base/LoadingState.vue'
import { useSupportStore } from '@/stores/support'
import {
  TICKET_TOPICS,
  formatNumber,
  ticketStatusLabel,
  ticketStatusState,
  timeAgo,
} from '@/utils/format'

const support = useSupportStore()
const router = useRouter()

const composing = ref(false)
const form = reactive({ subject: '', topic: 'other', body: '', order_number: '' })
const localErrors = ref({})

const TABS = [
  { value: 'all', label: 'همه' },
  { value: 'open', label: 'باز' },
  { value: 'closed', label: 'بسته' },
]

function errorFor(field) {
  return support.fieldErrors[field] || localErrors.value[field] || ''
}

function validate() {
  const errors = {}
  if (!form.subject.trim()) errors.subject = 'موضوع را بنویسید.'
  if (!form.body.trim()) errors.body = 'شرح مشکل را بنویسید.'
  localErrors.value = errors
  return Object.keys(errors).length === 0
}

async function submit() {
  localErrors.value = {}
  if (!validate()) return

  const { ok, data } = await support.createTicket({ ...form })
  if (ok) router.push(`/support/${data.reference}`)
}

onMounted(() => support.fetchTickets())
</script>

<template>
  <main class="register-editorial support">
    <header class="support__header">
      <div>
        <p class="support__eyebrow">SENOBAR / SUPPORT</p>
        <h1 class="support__title">پشتیبانی</h1>
        <p class="support__lede">
          سؤالی درباره سفارش، ارسال یا خود قهوه دارید؟ اینجا بپرسید.
        </p>
      </div>

      <BaseButton v-if="!composing" variant="primary" @click="composing = true">
        تیکت جدید
      </BaseButton>
    </header>

    <!-- Compose ---------------------------------------------------------- -->
    <section v-if="composing" class="compose">
      <h2 class="compose__title">تیکت جدید</h2>

      <p v-if="support.error" class="err" role="alert">{{ support.error }}</p>

      <form class="compose__form" novalidate @submit.prevent="submit">
        <BaseInput
          v-model="form.subject"
          label="موضوع"
          placeholder="خلاصه‌ای از موضوع"
          :error="errorFor('subject')"
          required
        />

        <div class="compose__row">
          <div class="field">
            <label class="field__label" for="topic">دسته</label>
            <select id="topic" v-model="form.topic" class="field__input">
              <option v-for="t in TICKET_TOPICS" :key="t.value" :value="t.value">
                {{ t.label }}
              </option>
            </select>
          </div>

          <BaseInput
            v-model="form.order_number"
            label="شماره سفارش (اختیاری)"
            placeholder="SB-260830-XXXX"
            :error="errorFor('order_number')"
          />
        </div>

        <div class="field">
          <label class="field__label" for="body">شرح</label>
          <textarea
            id="body"
            v-model="form.body"
            class="field__input field__textarea"
            rows="6"
            placeholder="هرچه بیشتر توضیح دهید، سریع‌تر کمکتان می‌کنیم."
          />
          <p v-if="errorFor('body')" class="field__err" role="alert">{{ errorFor('body') }}</p>
        </div>

        <div class="compose__actions">
          <BaseButton type="submit" variant="primary" :loading="support.sending">
            ارسال تیکت
          </BaseButton>
          <BaseButton
            type="button"
            variant="ghost"
            :disabled="support.sending"
            @click="composing = false"
          >
            انصراف
          </BaseButton>
        </div>
      </form>
    </section>

    <!-- Tabs ------------------------------------------------------------- -->
    <div class="support__tabs" role="tablist" aria-label="فیلتر تیکت‌ها">
      <button
        v-for="tab in TABS"
        :key="tab.value"
        type="button"
        role="tab"
        class="support__tab"
        :class="{ 'support__tab--on': support.state === tab.value }"
        :aria-selected="support.state === tab.value"
        @click="support.setState(tab.value)"
      >
        {{ tab.label }}
      </button>

      <span class="support__count">
        {{ support.loading ? 'در حال بارگذاری' : `${formatNumber(support.count)} تیکت` }}
      </span>
    </div>

    <p v-if="support.error && !composing" class="err" role="alert">{{ support.error }}</p>

    <!-- List ------------------------------------------------------------- -->
    <LoadingState
      v-if="support.loading && !support.tickets.length"
      variant="rows"
      code="OPENING THE FILE"
      :count="3"
      class="list-state"
    />

    <EmptyState
      v-else-if="support.isEmpty"
      icon="ticket"
      :code="support.state === 'closed' ? 'NOTHING CLOSED' : 'NO TICKETS OPEN'"
      :message="
        support.state === 'closed'
          ? 'تیکت بسته‌شده‌ای ندارید.'
          : 'سؤالی درباره سفارش، ارسال یا خود قهوه دارید؟ بپرسید.'
      "
      class="list-state"
    >
      <BaseButton v-if="!composing" variant="primary" @click="composing = true">
        اولین تیکت را بسازید
      </BaseButton>
    </EmptyState>

    <div v-else class="list">
      <RouterLink
        v-for="item in support.tickets"
        :key="item.reference"
        :to="`/support/${item.reference}`"
        class="card"
        :class="{ 'card--unread': item.unread }"
      >
        <header class="card__head">
          <div class="card__id">
            <span class="card__ref">{{ item.reference }}</span>
            <span class="card__topic">{{ item.topic_display }}</span>
          </div>

          <span class="card__status">
            <span class="status-light" :data-state="ticketStatusState(item.status)" />
            {{ ticketStatusLabel(item.status) }}
          </span>
        </header>

        <h3 class="card__subject">{{ item.subject }}</h3>
        <p v-if="item.preview" class="card__preview">{{ item.preview }}</p>

        <footer class="card__foot">
          <span class="card__meta">
            {{ formatNumber(item.message_count) }} پیام
            <template v-if="item.order_number"> · سفارش {{ item.order_number }}</template>
          </span>
          <span class="card__time">{{ timeAgo(item.last_message_at || item.created_at) }}</span>
        </footer>

        <!-- Unread is a filled square tab, not a round badge. -->
        <span v-if="item.unread" class="card__unread">
          {{ formatNumber(item.unread) }} پیام جدید
        </span>
      </RouterLink>
    </div>
  </main>
</template>

<style scoped>
/* ==========================================================================
   TicketListView — Editorial register
   ========================================================================== */

.support {
  padding: clamp(2rem, 6vw, 4rem) clamp(1.25rem, 5vw, 4rem) 6rem;
}

.support__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 2rem;
  flex-wrap: wrap;
}

.support__eyebrow {
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
  margin: 0;
}

.support__title {
  font-family: var(--font-editorial);
  font-size: clamp(2.25rem, 7vw, 3.5rem);
  line-height: 1.1;
  font-weight: 600;
  margin: 0.75rem 0 0;
}

.support__lede {
  font-family: var(--font-editorial);
  font-size: 1.0625rem;
  line-height: 1.7;
  color: var(--ink-muted);
  max-width: 32rem;
  margin: 0.875rem 0 0;
}

/* --- Compose --------------------------------------------------------------- */
.compose {
  border: 3px solid var(--ink);
  box-shadow: 8px 8px 0 var(--shadow);
  padding: 1.75rem;
  margin-top: 2.5rem;
}

.compose__title {
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-weight: 500;
  margin: 0 0 1.5rem;
  padding-bottom: 0.75rem;
  border-bottom: 3px solid var(--ink);
}

.compose__form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.compose__row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.25rem;
}

@media (max-width: 34rem) {
  .compose__row {
    grid-template-columns: 1fr;
  }
}

.compose__actions {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

/* --- Fields ---------------------------------------------------------------- */
.field {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.field__label {
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-weight: 500;
}

.field__input {
  width: 100%;
  border: 3px solid var(--ink);
  background-color: var(--paper);
  color: var(--ink);
  font-family: var(--font-terminal);
  font-size: 0.875rem;
  padding: 0.75rem 0.875rem;
}

.field__input:focus {
  outline: none;
  box-shadow: 4px 4px 0 var(--accent);
}

.field__textarea {
  resize: vertical;
  line-height: 1.75;
  font-family: var(--font-editorial);
  font-size: 1rem;
}

.field__err {
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  color: #a33224;
  margin: 0;
}

.err {
  border: 3px solid #a33224;
  background-color: #a33224;
  color: var(--paper);
  font-family: var(--font-terminal);
  font-size: 0.75rem;
  padding: 0.75rem 0.875rem;
  margin: 0 0 1.5rem;
}

/* --- Tabs ------------------------------------------------------------------ */
.support__tabs {
  display: flex;
  align-items: center;
  margin-top: 3rem;
  padding-top: 2rem;
  border-top: 3px solid var(--divider);
}

.support__tab {
  border: 3px solid var(--ink);
  border-inline-end-width: 0;
  background-color: var(--paper);
  color: var(--ink);
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  padding: 0.5rem 0.875rem;
  cursor: pointer;
}

.support__tab:last-of-type {
  border-inline-end-width: 3px;
}

.support__tab--on {
  background-color: var(--accent);
  color: var(--paper);
}

.support__tab:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: 3px;
  position: relative;
}

.support__count {
  margin-inline-start: auto;
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
}

/* --- List ------------------------------------------------------------------ */
.list {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  margin-top: 2.5rem;
}

.card {
  position: relative;
  display: block;
  border: 3px solid var(--ink);
  box-shadow: 6px 6px 0 var(--shadow);
  padding: 1.25rem;
  color: inherit;
  text-decoration: none;
  transition:
    transform 90ms cubic-bezier(0.2, 0, 0, 1),
    box-shadow 90ms cubic-bezier(0.2, 0, 0, 1);
}

@media (hover: hover) {
  .card:hover {
    transform: translate(-3px, -3px);
    box-shadow: 9px 9px 0 var(--shadow);
  }
}

.card:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: 3px;
}

/* An unread thread casts its shadow in accent — visible at a glance without
   adding a second colour to the card itself. */
.card--unread {
  box-shadow: 6px 6px 0 var(--accent);
}

@media (hover: hover) {
  .card--unread:hover {
    box-shadow: 9px 9px 0 var(--accent);
  }
}

.card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.card__id {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.card__ref {
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  letter-spacing: 0.08em;
  font-weight: 500;
}

.card__topic {
  font-family: var(--font-terminal);
  font-size: 0.5625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
  border: 2px solid var(--rule);
  padding: 0.125rem 0.375rem;
}

.card__status {
  display: inline-flex;
  align-items: center;
  gap: 0.4375rem;
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.card__subject {
  font-family: var(--font-editorial);
  font-size: 1.1875rem;
  line-height: 1.4;
  font-weight: 600;
  margin: 0.875rem 0 0;
}

.card__preview {
  font-family: var(--font-editorial);
  font-size: 0.9375rem;
  line-height: 1.6;
  color: var(--ink-muted);
  margin: 0.5rem 0 0;
}

.card__foot {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  margin-top: 1.125rem;
  padding-top: 0.875rem;
  border-top: 1px solid var(--rule);
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.08em;
  color: var(--ink-muted);
}

.card__unread {
  position: absolute;
  inset-block-start: -3px;
  inset-inline-end: 1.5rem;
  background-color: var(--accent);
  color: var(--paper);
  font-family: var(--font-terminal);
  font-size: 0.5625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  padding: 0.1875rem 0.4375rem;
}

/* --- Empty / loading ------------------------------------------------------- */
.list-state {
  margin-top: 2.5rem;
}

@media (prefers-reduced-motion: reduce) {
  .card {
    transition: none;
  }
}
</style>
