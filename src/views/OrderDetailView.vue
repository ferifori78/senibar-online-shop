<script setup>
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import BaseButton from '@/components/base/BaseButton.vue'
import GrindIcon from '@/components/icons/GrindIcon.vue'
import OrderTimeline from '@/components/orders/OrderTimeline.vue'
import { useOrdersStore } from '@/stores/orders'
import {
  GRIND_METHODS,
  PAYMENT_STATUS,
  formatDateTime,
  formatNumber,
  formatPrice,
  formatWeight,
  orderStatusLabel,
  orderStatusState,
} from '@/utils/format'

const route = useRoute()
const store = useOrdersStore()

const confirmingCancel = ref(false)
const cancelReason = ref('')

const order = computed(() => store.order)

function grindLabel(value) {
  return GRIND_METHODS.find((m) => m.value === value)?.label || value
}

async function confirmCancel() {
  const { ok } = await store.cancelOrder(order.value.number, cancelReason.value)
  if (ok) {
    confirmingCancel.value = false
    cancelReason.value = ''
  }
}

watch(
  () => route.params.number,
  (number) => {
    if (number) store.fetchOrder(number)
  },
  { immediate: true },
)
</script>

<template>
  <main class="register-editorial order">
    <div v-if="store.detailLoading" class="order__loading">در حال بارگذاری…</div>

    <div v-else-if="!order" class="order__missing">
      <p>{{ store.error || 'این سفارش پیدا نشد.' }}</p>
      <RouterLink to="/orders"><BaseButton variant="secondary">سفارش‌های من</BaseButton></RouterLink>
    </div>

    <template v-else>
      <nav class="order__crumbs" aria-label="مسیر">
        <RouterLink to="/orders" class="order__crumb">سفارش‌های من</RouterLink>
        <span aria-hidden="true">/</span>
        <span>{{ order.number }}</span>
      </nav>

      <header class="order__header">
        <div>
          <p class="order__eyebrow">SENOBAR / ORDER</p>
          <h1 class="order__title">{{ order.number }}</h1>
          <p class="order__placed">ثبت شده در {{ formatDateTime(order.placed_at) }}</p>
        </div>

        <div class="order__badges">
          <span class="order__status">
            <span class="status-light" :data-state="orderStatusState(order.status)" />
            {{ orderStatusLabel(order.status) }}
          </span>
          <span class="order__payment">{{ PAYMENT_STATUS[order.payment_status] }}</span>
        </div>
      </header>

      <div class="order__layout">
        <!-- ------------------------------------------------- Timeline register -->
        <section class="order__panel order__panel--timeline">
          <h2 class="order__panel-title">وضعیت سفارش</h2>

          <OrderTimeline :stages="order.timeline" :order="order" />

          <div v-if="order.tracking_code" class="order__tracking">
            <span class="order__tracking-label">کد رهگیری پستی</span>
            <span class="order__tracking-code">{{ order.tracking_code }}</span>
          </div>
        </section>

        <!-- ------------------------------------------------------------ Items -->
        <section class="order__panel">
          <h2 class="order__panel-title">اقلام سفارش</h2>

          <ul class="items">
            <li v-for="item in order.items" :key="item.id" class="items__row">
              <span class="items__qty">{{ formatNumber(item.quantity) }}×</span>

              <div class="items__body">
                <span class="items__name">{{ item.product_name }}</span>
                <span class="items__origin">{{ item.product_origin }}</span>

                <span class="items__config">
                  <GrindIcon :method="item.grind_type" :size="16" />
                  {{ formatWeight(item.weight_grams) }} · {{ grindLabel(item.grind_type) }}
                </span>

                <span v-if="item.batch_code" class="items__batch">لات {{ item.batch_code }}</span>
              </div>

              <span class="items__price">{{ formatPrice(item.line_total) }}</span>
            </li>
          </ul>

          <dl class="totals">
            <div class="totals__row">
              <dt>جمع اقلام</dt>
              <dd>{{ formatPrice(order.subtotal) }}</dd>
            </div>
            <div class="totals__row">
              <dt>ارسال</dt>
              <dd>{{ Number(order.shipping_cost) ? formatPrice(order.shipping_cost) : 'رایگان' }}</dd>
            </div>
            <div v-if="Number(order.discount_amount)" class="totals__row">
              <dt>تخفیف</dt>
              <dd>−{{ formatPrice(order.discount_amount) }}</dd>
            </div>
          </dl>

          <div class="order__rule" aria-hidden="true" />

          <div class="totals__grand">
            <span>مبلغ کل</span>
            <strong>{{ formatPrice(order.total_amount) }}</strong>
          </div>

          <!-- Below the total, deliberately: the shop pays this, the customer
               does not. Placing it in the totals list above would read as a
               line added to what they owe. -->
          <p v-if="Number(order.gateway_fee)" class="fee">
            <span class="fee__amount">{{ formatPrice(order.gateway_fee) }}</span>
            کارمزد درگاه پرداخت، که توسط صنوبر پرداخت می‌شود و به مبلغ سفارش شما
            اضافه نشده است.
          </p>
        </section>

        <!-- ---------------------------------------------------------- Address -->
        <section class="order__panel">
          <h2 class="order__panel-title">نشانی ارسال</h2>

          <address class="address">
            <span class="address__name">{{ order.recipient_name }}</span>
            <span>{{ order.recipient_phone }}</span>
            <span>{{ order.province }}، {{ order.city }}</span>
            <span>{{ order.street_address }}</span>
            <span class="address__postal">کد پستی: {{ order.postal_code }}</span>
          </address>

          <p v-if="order.customer_note" class="address__note">
            <span class="address__note-label">یادداشت شما</span>
            {{ order.customer_note }}
          </p>
        </section>

        <!-- ---------------------------------------------------------- History -->
        <section v-if="order.history?.length" class="order__panel">
          <h2 class="order__panel-title">تاریخچه</h2>

          <ul class="history">
            <li v-for="entry in order.history" :key="entry.id" class="history__row">
              <span class="history__time">{{ formatDateTime(entry.created_at) }}</span>
              <span class="history__change">
                {{ orderStatusLabel(entry.from_status) }} ← {{ orderStatusLabel(entry.to_status) }}
              </span>
              <span v-if="entry.note" class="history__note">{{ entry.note }}</span>
            </li>
          </ul>
        </section>
      </div>

      <!-- ----------------------------------------------------------- Actions -->
      <section v-if="order.can_be_cancelled" class="order__actions">
        <p v-if="store.error" class="order__error" role="alert">{{ store.error }}</p>

        <template v-if="!confirmingCancel">
          <BaseButton variant="ghost" @click="confirmingCancel = true">لغو سفارش</BaseButton>
        </template>

        <div v-else class="cancel">
          <p class="cancel__question">این سفارش لغو شود؟ این کار برگشت‌پذیر نیست.</p>
          <input
            v-model="cancelReason"
            class="cancel__input"
            type="text"
            placeholder="دلیل لغو (اختیاری)"
          />
          <div class="cancel__actions">
            <BaseButton variant="danger" :loading="store.acting" @click="confirmCancel">
              بله، لغو کن
            </BaseButton>
            <BaseButton variant="ghost" :disabled="store.acting" @click="confirmingCancel = false">
              بازگشت
            </BaseButton>
          </div>
        </div>
      </section>
    </template>
  </main>
</template>

<style scoped>
/* ==========================================================================
   OrderDetailView — Editorial register, with the Timeline register inside.
   ========================================================================== */

.order {
  padding: clamp(2rem, 6vw, 4rem) clamp(1.25rem, 5vw, 4rem) 6rem;
}

.order__loading,
.order__missing {
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

.order__crumbs {
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

.order__crumb {
  color: var(--ink-muted);
  text-decoration: none;
  border-bottom: 2px solid transparent;
}
.order__crumb:hover {
  color: var(--ink);
  border-bottom-color: var(--accent);
}

/* --- Header ---------------------------------------------------------------- */
.order__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1.5rem;
  flex-wrap: wrap;
  padding-bottom: 2rem;
  border-bottom: 3px solid var(--divider);
}

.order__eyebrow {
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
  margin: 0;
}

.order__title {
  font-family: var(--font-terminal);
  font-size: clamp(1.75rem, 5vw, 2.5rem);
  letter-spacing: 0.04em;
  font-weight: 600;
  margin: 0.625rem 0 0;
}

.order__placed {
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.1em;
  color: var(--ink-muted);
  margin: 0.5rem 0 0;
}

.order__badges {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.625rem;
}

.order__status {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  border: 3px solid var(--ink);
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  padding: 0.4375rem 0.75rem;
}

.order__payment {
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
}

/* --- Layout ---------------------------------------------------------------- */
.order__layout {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(19rem, 1fr));
  gap: clamp(1.75rem, 3vw, 2.75rem);
  margin-top: 2.5rem;
  align-items: start;
}

.order__panel {
  border: 3px solid var(--ink);
  padding: 1.5rem;
}

/* The timeline gets the hard shadow — it is what the page is for. */
.order__panel--timeline {
  box-shadow: 8px 8px 0 var(--shadow);
}

.order__panel-title {
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-weight: 500;
  margin: 0 0 1.5rem;
  padding-bottom: 0.75rem;
  border-bottom: 3px solid var(--ink);
}

.order__rule {
  height: 3px;
  background-color: var(--ink);
  margin: 1rem 0;
}

/* --- Tracking -------------------------------------------------------------- */
.order__tracking {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  margin-top: 1.75rem;
  padding-top: 1.25rem;
  border-top: 1px solid var(--rule);
}

.order__tracking-label {
  font-family: var(--font-terminal);
  font-size: 0.5625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
}

.order__tracking-code {
  font-family: var(--font-terminal);
  font-size: 0.875rem;
  letter-spacing: 0.1em;
  font-weight: 500;
}

/* --- Items ----------------------------------------------------------------- */
.items {
  list-style: none;
  padding: 0;
  margin: 0 0 1.25rem;
}

.items__row {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.75rem 0;
  border-bottom: 1px solid var(--rule);
}

.items__qty {
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  color: var(--ink-muted);
  flex: none;
  padding-top: 0.125rem;
}

.items__body {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  flex: 1;
  min-width: 0;
}

.items__name {
  font-family: var(--font-editorial);
  font-size: 1rem;
  line-height: 1.35;
  font-weight: 600;
}

.items__origin {
  font-family: var(--font-terminal);
  font-size: 0.5625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
}

.items__config {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.06em;
  margin-top: 0.25rem;
}

.items__batch {
  font-family: var(--font-terminal);
  font-size: 0.5625rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--ink-muted);
}

.items__price {
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  flex: none;
  padding-top: 0.125rem;
}

/* --- Totals ---------------------------------------------------------------- */
.totals {
  margin: 0;
}

.totals__row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.375rem 0;
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
}

.totals__row dt {
  color: var(--ink-muted);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.totals__row dd {
  margin: 0;
}

/* --- Gateway fee ----------------------------------------------------------- */
.fee {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 0.875rem;
  line-height: 1.9;
  color: var(--ink-muted);
  margin: 1rem 0 0;
  padding-block-start: 0.875rem;
  border-block-start: 2px solid var(--rule);
}

.fee__amount {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.75rem;
  letter-spacing: 0.08em;
  color: var(--ink);
  margin-inline-end: 0.375rem;
}

.totals__grand {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
}

.totals__grand span {
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
}

.totals__grand strong {
  font-family: var(--font-editorial);
  font-size: 1.375rem;
  font-weight: 600;
}

/* --- Address --------------------------------------------------------------- */
.address {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  font-style: normal;
  font-family: var(--font-editorial);
  font-size: 0.9375rem;
  line-height: 1.6;
}

.address__name {
  font-weight: 600;
}

.address__postal {
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.1em;
  color: var(--ink-muted);
  margin-top: 0.25rem;
}

.address__note {
  margin: 1.5rem 0 0;
  padding-top: 1.25rem;
  border-top: 1px solid var(--rule);
  font-family: var(--font-editorial);
  font-size: 0.9375rem;
  line-height: 1.7;
}

.address__note-label {
  display: block;
  font-family: var(--font-terminal);
  font-size: 0.5625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
  margin-bottom: 0.375rem;
}

/* --- History --------------------------------------------------------------- */
.history {
  list-style: none;
  padding: 0;
  margin: 0;
}

.history__row {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.625rem 0;
  border-bottom: 1px solid var(--rule);
}

.history__time {
  font-family: var(--font-terminal);
  font-size: 0.5625rem;
  letter-spacing: 0.1em;
  color: var(--ink-muted);
}

.history__change {
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.history__note {
  font-family: var(--font-editorial);
  font-size: 0.875rem;
  line-height: 1.6;
  color: var(--ink-muted);
}

/* --- Actions --------------------------------------------------------------- */
.order__actions {
  margin-top: 3rem;
  padding-top: 2rem;
  border-top: 3px solid var(--ink);
}

.order__error {
  border: 3px solid #a33224;
  background-color: #a33224;
  color: var(--paper);
  font-family: var(--font-terminal);
  font-size: 0.75rem;
  padding: 0.75rem 0.875rem;
  margin: 0 0 1.5rem;
}

.cancel {
  border: 3px solid #a33224;
  padding: 1.25rem;
  max-width: 32rem;
}

.cancel__question {
  font-family: var(--font-editorial);
  font-size: 1rem;
  line-height: 1.6;
  margin: 0 0 1rem;
}

.cancel__input {
  width: 100%;
  border: 3px solid var(--ink);
  background-color: var(--paper);
  color: var(--ink);
  padding: 0.625rem 0.75rem;
  font-family: var(--font-terminal);
  font-size: 0.8125rem;
  margin-bottom: 1.25rem;
}

.cancel__input:focus {
  outline: none;
  box-shadow: 4px 4px 0 #a33224;
}

.cancel__actions {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}
</style>
