<script setup>
import { computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'

import AdminLayout from '@/components/layout/AdminLayout.vue'
import StatusLamp from '@/components/admin/StatusLamp.vue'
import GrindIcon from '@/components/icons/GrindIcon.vue'
import { panelPath } from '@/constants/panel'
import { useAdminStore } from '@/stores/admin'
import {
  GRIND_METHODS,
  formatDate,
  formatNumber,
  formatPrice,
  formatWeight,
  freshnessLabel,
  freshnessState,
} from '@/utils/format'

const admin = useAdminStore()

const stats = computed(() => admin.stats)

function grindLabel(value) {
  return GRIND_METHODS.find((m) => m.value === value)?.label || value
}

/** Bar heights for the seven-day chart, scaled to the busiest day. */
const series = computed(() => {
  const rows = stats.value?.sales?.series || []
  const peak = Math.max(...rows.map((r) => Number(r.total)), 1)
  return rows.map((r) => ({
    ...r,
    total: Number(r.total),
    height: (Number(r.total) / peak) * 100,
  }))
})

onMounted(() => admin.fetchStats())
</script>

<template>
  <AdminLayout>
    <p v-if="admin.error" class="err" role="alert">{{ admin.error }}</p>

    <div v-if="admin.loading && !stats" class="loading">LOADING…</div>

    <template v-else-if="stats">
      <!-- ------------------------------------------------------ Headline -->
      <section class="cells" aria-label="آمار کلی">
        <div class="cell cell--accent">
          <span class="cell__label">فروش امروز</span>
          <span class="cell__value">{{ formatPrice(stats.sales.today) }}</span>
          <span class="cell__meta">{{ formatNumber(stats.sales.today_orders) }} سفارش</span>
        </div>

        <RouterLink :to="`${panelPath('orders')}?state=pending`" class="cell cell--link">
          <span class="cell__label">در انتظار رست</span>
          <span class="cell__value">{{ formatNumber(stats.queue.awaiting_roast) }}</span>
          <span class="cell__meta">
            <StatusLamp state="warn" label="نیازمند اقدام" />
          </span>
        </RouterLink>

        <div class="cell">
          <span class="cell__label">در تولید</span>
          <span class="cell__value">{{ formatNumber(stats.queue.in_production) }}</span>
          <span class="cell__meta">
            رست {{ formatNumber(stats.queue.roasting) }} · بسته
            {{ formatNumber(stats.queue.packed) }}
          </span>
        </div>

        <div class="cell">
          <span class="cell__label">فروش ۷ روز</span>
          <span class="cell__value">{{ formatPrice(stats.sales.week) }}</span>
          <span class="cell__meta">{{ formatNumber(stats.sales.week_orders) }} سفارش</span>
        </div>

        <div class="cell">
          <span class="cell__label">موجودی انبار</span>
          <span class="cell__value">{{ formatWeight(stats.stock.total_grams) }}</span>
          <span class="cell__meta">
            {{ formatNumber(stats.stock.available_batches) }} بچ تازه
          </span>
        </div>

        <div class="cell">
          <span class="cell__label">پرداخت نشده</span>
          <span class="cell__value">{{ formatNumber(stats.queue.unpaid) }}</span>
          <span class="cell__meta">
            <StatusLamp :state="stats.queue.unpaid ? 'error' : 'idle'" label="در انتظار پرداخت" />
          </span>
        </div>
      </section>

      <div class="grid">
        <!-- --------------------------------------------------- Sales bars -->
        <section class="panel">
          <h2 class="panel__title">فروش هفت روز گذشته</h2>
          <div class="chart">
            <div v-for="day in series" :key="day.date" class="chart__col">
              <span class="chart__bar-wrap">
                <span class="chart__bar" :style="{ height: `${day.height}%` }" />
              </span>
              <span class="chart__label">{{ formatDate(day.date).split(' ')[0] }}</span>
              <span class="chart__count">{{ formatNumber(day.count) }}</span>
            </div>
          </div>
        </section>

        <!-- ---------------------------------------------------- Roast plan -->
        <section class="panel">
          <h2 class="panel__title">برنامه رست</h2>
          <p v-if="!stats.roast_plan.length" class="panel__empty">صف رست خالی است.</p>
          <table v-else class="mini">
            <tbody>
              <tr v-for="row in stats.roast_plan" :key="row.slug || row.name">
                <td class="mini__name">{{ row.name }}</td>
                <td class="mini__num">{{ formatWeight(row.grams) }}</td>
                <td class="mini__dim">{{ formatNumber(row.lines) }} خط</td>
              </tr>
            </tbody>
          </table>
        </section>

        <!-- -------------------------------------------------- Grind queue -->
        <section class="panel">
          <h2 class="panel__title">صف آسیاب</h2>
          <p v-if="!stats.grind_queue.length" class="panel__empty">چیزی برای آسیاب نیست.</p>
          <table v-else class="mini">
            <tbody>
              <tr v-for="row in stats.grind_queue" :key="row.grind_type">
                <td class="mini__name">
                  <span class="mini__icon"><GrindIcon :method="row.grind_type" :size="15" /></span>
                  {{ grindLabel(row.grind_type) }}
                </td>
                <td class="mini__num">{{ formatWeight(row.grams) }}</td>
                <td class="mini__dim">{{ formatNumber(row.lines) }} خط</td>
              </tr>
            </tbody>
          </table>
        </section>

        <!-- -------------------------------------------------- Stock alerts -->
        <section class="panel">
          <h2 class="panel__title">هشدار موجودی</h2>

          <template v-if="stats.stock.low.length">
            <p class="panel__sub">رو به اتمام</p>
            <table class="mini">
              <tbody>
                <tr v-for="b in stats.stock.low" :key="b.batch_code">
                  <td class="mini__name">{{ b.product }}</td>
                  <td class="mini__dim">{{ b.batch_code }}</td>
                  <td class="mini__num">{{ formatWeight(b.available_grams) }}</td>
                </tr>
              </tbody>
            </table>
          </template>

          <template v-if="stats.stock.going_stale.length">
            <p class="panel__sub">در حال کهنه شدن</p>
            <table class="mini">
              <tbody>
                <tr v-for="b in stats.stock.going_stale" :key="b.batch_code">
                  <td class="mini__name">{{ b.product }}</td>
                  <td>
                    <StatusLamp
                      :state="freshnessState(b.freshness)"
                      :label="freshnessLabel(b.freshness)"
                    />
                  </td>
                  <td class="mini__num">{{ formatNumber(b.days_since_roast) }} روز</td>
                </tr>
              </tbody>
            </table>
          </template>

          <p
            v-if="!stats.stock.low.length && !stats.stock.going_stale.length"
            class="panel__empty"
          >
            موجودی سالم است.
          </p>
        </section>
      </div>
    </template>
  </AdminLayout>
</template>

<style scoped>
/* ==========================================================================
   AdminDashboardView — Terminal register
   ========================================================================== */

.loading,
.err {
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  color: var(--terminal-dim);
  padding: 3rem 0;
}

.err {
  border: 3px solid #a33224;
  background-color: #a33224;
  color: var(--paper);
  padding: 0.625rem 0.75rem;
  margin-bottom: 1.5rem;
}

/* --- Headline cells -------------------------------------------------------- */
.cells {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
  gap: 0;
  border: 3px solid var(--terminal-text);
}

.cell {
  display: flex;
  flex-direction: column;
  gap: 0.4375rem;
  padding: 1rem;
  /* Cells share rules rather than each carrying a full border — the grid
     reads as one instrument panel, not six cards. */
  border-inline-end: 3px solid var(--terminal-text);
  color: inherit;
  text-decoration: none;
}

.cell:last-child {
  border-inline-end: 0;
}

.cell--accent {
  background-color: var(--accent);
  color: var(--paper);
}

.cell--link:hover {
  background-color: var(--terminal-raised);
}

.cell--link:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: -3px;
}

.cell__label {
  font-family: var(--font-terminal);
  font-size: 0.5625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  opacity: 0.75;
}

.cell__value {
  font-family: var(--font-terminal);
  font-size: 1.375rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  line-height: 1.1;
}

.cell__meta {
  font-family: var(--font-terminal);
  font-size: 0.5625rem;
  letter-spacing: 0.1em;
  opacity: 0.7;
}

.cell--accent .cell__meta {
  opacity: 0.85;
}

@media (max-width: 60rem) {
  .cell {
    border-inline-end: 0;
    border-bottom: 3px solid var(--terminal-text);
  }
}

/* --- Panels ---------------------------------------------------------------- */
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(19rem, 1fr));
  gap: 1.25rem;
  margin-top: 1.25rem;
}

.panel {
  border: 3px solid var(--terminal-text);
  padding: 1rem;
}

.panel__title {
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-weight: 500;
  margin: 0 0 1rem;
  padding-bottom: 0.625rem;
  border-bottom: 3px solid var(--terminal-text);
}

.panel__sub {
  font-family: var(--font-terminal);
  font-size: 0.5625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--terminal-dim);
  margin: 1rem 0 0.5rem;
}

.panel__sub:first-of-type {
  margin-top: 0;
}

.panel__empty {
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.08em;
  color: var(--terminal-dim);
  margin: 0;
}

/* --- Chart ----------------------------------------------------------------- */
.chart {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 0.375rem;
  align-items: end;
  height: 10rem;
}

.chart__col {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.3125rem;
  height: 100%;
  justify-content: flex-end;
}

.chart__bar-wrap {
  display: flex;
  align-items: flex-end;
  width: 100%;
  flex: 1;
  border-bottom: 3px solid var(--terminal-text);
}

/* Square bars, flat accent. No rounding, no gradient. */
.chart__bar {
  width: 100%;
  background-color: var(--accent);
  min-height: 3px;
}

.chart__label,
.chart__count {
  font-family: var(--font-terminal);
  font-size: 0.5rem;
  letter-spacing: 0.06em;
  color: var(--terminal-dim);
}

/* --- Mini tables ----------------------------------------------------------- */
.mini {
  width: 100%;
  border-collapse: collapse;
  font-family: var(--font-terminal);
  font-size: 0.625rem;
}

.mini tr {
  border-bottom: 1px solid var(--terminal-rule);
}

.mini td {
  padding: 0.4375rem 0.25rem;
  vertical-align: middle;
}

.mini__name {
  color: var(--terminal-text);
}

.mini__icon {
  display: inline-flex;
  vertical-align: middle;
  margin-inline-end: 0.375rem;
  color: var(--accent);
}

.mini__num {
  text-align: end;
  white-space: nowrap;
}

.mini__dim {
  color: var(--terminal-dim);
  white-space: nowrap;
}
</style>
