<script setup>
import { onMounted } from 'vue'
import { RouterLink } from 'vue-router'

import BaseButton from '@/components/base/BaseButton.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import LoadingState from '@/components/base/LoadingState.vue'
import { useOrdersStore } from '@/stores/orders'
import {
  formatDate,
  formatNumber,
  formatPrice,
  formatWeight,
  orderStatusLabel,
  orderStatusState,
} from '@/utils/format'

const store = useOrdersStore()

const TABS = [
  { value: 'all', label: 'همه' },
  { value: 'open', label: 'در جریان' },
  { value: 'past', label: 'بایگانی' },
]

/** Progress through the pipeline, as a fraction the mini rail can draw. */
function progress(order) {
  if (order.pipeline_position === null || order.pipeline_position === undefined) return 0
  const gaps = (order.pipeline_length || 6) - 1
  return gaps <= 0 ? 100 : (order.pipeline_position / gaps) * 100
}

onMounted(() => store.fetchOrders())
</script>

<template>
  <main class="register-editorial orders">
    <header class="orders__header">
      <p class="orders__eyebrow">SENOBAR / ORDERS</p>
      <h1 class="orders__title">سفارش‌های من</h1>
    </header>

    <!-- Tabs: square segmented control, accent marks the active one. -->
    <div class="orders__tabs" role="tablist" aria-label="فیلتر سفارش‌ها">
      <button
        v-for="tab in TABS"
        :key="tab.value"
        type="button"
        role="tab"
        class="orders__tab"
        :class="{ 'orders__tab--on': store.state === tab.value }"
        :aria-selected="store.state === tab.value"
        @click="store.setState(tab.value)"
      >
        {{ tab.label }}
      </button>

      <span class="orders__count">
        {{ store.loading ? 'در حال بارگذاری' : `${formatNumber(store.count)} سفارش` }}
      </span>
    </div>

    <p v-if="store.error" class="orders__error" role="alert">{{ store.error }}</p>

    <!-- Loading ---------------------------------------------------------- -->
    <LoadingState
      v-if="store.loading && !store.orders.length"
      variant="rows"
      code="FETCHING ORDERS"
      :count="3"
      class="orders__loading"
    />

    <!-- Empty ------------------------------------------------------------ -->
    <EmptyState
      v-else-if="store.isEmpty"
      icon="box"
      :code="store.state === 'past' ? 'NOTHING ARCHIVED' : 'NO ORDERS YET'"
      :message="
        store.state === 'past'
          ? 'سفارش تمام‌شده یا لغوشده‌ای ندارید.'
          : 'هنوز سفارشی ثبت نکرده‌اید. هر لات پس از سفارش رست می‌شود.'
      "
      class="orders__empty"
    >
      <RouterLink to="/products">
        <BaseButton variant="primary">دیدن قهوه‌ها</BaseButton>
      </RouterLink>
    </EmptyState>

    <!-- List ------------------------------------------------------------- -->
    <div v-else class="orders__list">
      <RouterLink
        v-for="order in store.orders"
        :key="order.number"
        :to="`/orders/${order.number}`"
        class="card"
      >
        <header class="card__head">
          <div class="card__id">
            <span class="card__number">{{ order.number }}</span>
            <span class="card__date">{{ formatDate(order.placed_at) }}</span>
          </div>

          <span class="card__status">
            <span class="status-light" :data-state="orderStatusState(order.status)" />
            {{ orderStatusLabel(order.status) }}
          </span>
        </header>

        <p class="card__summary">{{ order.summary }}</p>

        <!-- A compressed horizontal rail: the same accent-fill idea as the
             detail page's timeline, laid on its side. -->
        <div v-if="order.is_open" class="card__rail" aria-hidden="true">
          <div class="card__rail-fill" :style="{ width: `${progress(order)}%` }" />
        </div>

        <footer class="card__foot">
          <span class="card__meta">
            {{ formatNumber(order.item_count) }} قلم · {{ formatWeight(order.total_grams) }}
          </span>
          <span class="card__total">{{ formatPrice(order.total_amount) }}</span>
        </footer>
      </RouterLink>
    </div>

    <div v-if="store.hasNext" class="orders__more">
      <BaseButton variant="secondary" :loading="store.loading" @click="store.loadMore()">
        نمایش بیشتر
      </BaseButton>
    </div>
  </main>
</template>

<style scoped>
/* ==========================================================================
   OrderListView — Editorial register
   ========================================================================== */

.orders {
  padding: clamp(2rem, 6vw, 4rem) clamp(1.25rem, 5vw, 4rem) 6rem;
}

.orders__eyebrow {
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
  margin: 0;
}

.orders__title {
  font-family: var(--font-editorial);
  font-size: clamp(2.25rem, 7vw, 3.5rem);
  line-height: 1.1;
  font-weight: 600;
  margin: 0.75rem 0 0;
}

/* --- Tabs ------------------------------------------------------------------ */
.orders__tabs {
  display: flex;
  align-items: center;
  gap: 0;
  margin-top: 2.5rem;
  padding-top: 2rem;
  border-top: 3px solid var(--divider);
}

.orders__tab {
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

.orders__tab:last-of-type {
  border-inline-end-width: 3px;
}

.orders__tab--on {
  background-color: var(--accent);
  color: var(--paper);
}

.orders__tab:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: 3px;
  position: relative;
}

.orders__count {
  margin-inline-start: auto;
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
}

/* --- List ------------------------------------------------------------------ */
.orders__list {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  margin-top: 2.5rem;
}

/* --- Card ------------------------------------------------------------------ */
.card {
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

.card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.card__id {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.card__number {
  font-family: var(--font-terminal);
  font-size: 0.8125rem;
  letter-spacing: 0.08em;
  font-weight: 500;
}

.card__date {
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.1em;
  color: var(--ink-muted);
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

.card__summary {
  font-family: var(--font-editorial);
  font-size: 1.0625rem;
  line-height: 1.6;
  margin: 1rem 0 0;
}

/* Horizontal mini-rail — the Timeline register, compressed to one line. */
.card__rail {
  height: 3px;
  background-color: var(--rule);
  margin-top: 1.125rem;
}

.card__rail-fill {
  height: 100%;
  background-color: var(--accent);
}

.card__foot {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  margin-top: 1.125rem;
  padding-top: 0.875rem;
  border-top: 1px solid var(--rule);
}

.card__meta {
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--ink-muted);
}

.card__total {
  font-family: var(--font-editorial);
  font-size: 1.125rem;
  font-weight: 600;
}

/* --- Empty / error --------------------------------------------------------- */
.orders__loading,
.orders__empty {
  margin-top: 2.5rem;
}

.orders__error {
  border: 3px solid #a33224;
  background-color: #a33224;
  color: var(--paper);
  font-family: var(--font-terminal);
  font-size: 0.75rem;
  padding: 0.75rem 0.875rem;
  margin: 2rem 0 0;
}

.orders__more {
  display: flex;
  justify-content: center;
  margin-top: 2.5rem;
}

@media (prefers-reduced-motion: reduce) {
  .card {
    transition: none;
  }
}
</style>
