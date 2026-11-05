<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import AdminLayout from '@/components/layout/AdminLayout.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import LoadingState from '@/components/base/LoadingState.vue'
import OrderStatusModal from '@/components/admin/OrderStatusModal.vue'
import StatusLamp from '@/components/admin/StatusLamp.vue'
import GrindIcon from '@/components/icons/GrindIcon.vue'
import { useAdminStore } from '@/stores/admin'
import {
  GRIND_METHODS,
  formatDate,
  formatNumber,
  formatPrice,
  formatWeight,
} from '@/utils/format'

const admin = useAdminStore()
const route = useRoute()

const openOrder = ref(null)

const FILTERS = [
  { value: 'queue', label: 'QUEUE' },
  { value: 'pending', label: 'PENDING' },
  { value: 'roasting', label: 'ROASTING' },
  { value: 'ground', label: 'GROUND' },
  { value: 'packed', label: 'PACKED' },
  { value: 'shipped', label: 'SHIPPED' },
  { value: 'all', label: 'ALL' },
]

function grindLabel(value) {
  return GRIND_METHODS.find((m) => m.value === value)?.label || value
}

/** Rows of the same order share a number; only the first prints it, so the
 *  eye groups them without needing a border. */
function isFirstOfOrder(row, index) {
  return index === 0 || admin.board[index - 1].order_number !== row.order_number
}

let searchTimer
watch(
  () => admin.boardSearch,
  () => {
    clearTimeout(searchTimer)
    searchTimer = setTimeout(() => admin.fetchBoard(), 300)
  },
)

function onUpdated() {
  admin.fetchBoard()
}

onMounted(() => {
  if (route.query.state) admin.boardFilter = route.query.state
  admin.fetchBoard()
})
</script>

<template>
  <AdminLayout>
    <!-- Controls ------------------------------------------------------- -->
    <div class="bar">
      <div class="bar__filters" role="tablist" aria-label="فیلتر وضعیت">
        <button
          v-for="filter in FILTERS"
          :key="filter.value"
          type="button"
          role="tab"
          class="bar__filter"
          :class="{ 'bar__filter--on': admin.boardFilter === filter.value }"
          :aria-selected="admin.boardFilter === filter.value"
          @click="admin.setBoardFilter(filter.value)"
        >
          {{ filter.label }}
        </button>
      </div>

      <input
        v-model="admin.boardSearch"
        type="search"
        class="bar__search"
        placeholder="SEARCH — شماره، مشتری، قهوه"
        aria-label="جستجو"
      />

      <span class="bar__count">{{ formatNumber(admin.board.length) }} ROWS</span>
    </div>

    <p v-if="admin.error" class="err" role="alert">{{ admin.error }}</p>

    <!-- Table ---------------------------------------------------------- -->
    <div class="wrap">
      <table class="tbl tbl-responsive">
        <thead>
          <tr>
            <th scope="col">ID</th>
            <th scope="col">مشتری</th>
            <th scope="col">قهوه</th>
            <th scope="col">آسیاب</th>
            <th scope="col" class="tbl__num">وزن</th>
            <th scope="col" class="tbl__num">مبلغ</th>
            <th scope="col">وضعیت</th>
            <th scope="col">اکشن</th>
          </tr>
        </thead>

        <tbody>
          <tr v-if="admin.loading && !admin.board.length">
            <td colspan="8" class="tbl__state">
                <LoadingState variant="inline" code="LOADING" inverse />
              </td>
          </tr>

          <tr v-else-if="!admin.board.length">
            <td colspan="8" class="tbl__state">
                <EmptyState icon="inbox" code="NO ORDERS ON THE BOARD"
                            message="هیچ ردیفی مطابق این فیلتر نیست." inverse compact />
              </td>
          </tr>

          <tr
            v-for="(row, index) in admin.board"
            v-else
            :key="`${row.order_number}-${index}`"
            class="tbl__row"
            :class="{ 'tbl__row--head': isFirstOfOrder(row, index) }"
          >
            <td data-label="ID" class="tbl__id">
              <template v-if="isFirstOfOrder(row, index)">
                <span class="tbl__number">{{ row.order_number }}</span>
                <span class="tbl__date">{{ formatDate(row.placed_at) }}</span>
              </template>
              <span v-else class="tbl__cont" aria-hidden="true">↳</span>
            </td>

            <td data-label="مشتری">
              <template v-if="isFirstOfOrder(row, index)">
                <span class="tbl__customer">{{ row.customer }}</span>
                <span class="tbl__dim">{{ row.city }}</span>
              </template>
            </td>

            <td data-label="قهوه" class="tbl__product">{{ row.product_name }}</td>

            <td data-label="آسیاب" class="tbl__grind">
              <GrindIcon :method="row.grind_type" :size="14" />
              {{ grindLabel(row.grind_type) }}
            </td>

            <td data-label="وزن" class="tbl__num">
              {{ formatWeight(row.weight_grams) }}
              <span v-if="row.quantity > 1" class="tbl__mult">×{{ row.quantity }}</span>
            </td>

            <td data-label="مبلغ" class="tbl__num">
              <template v-if="isFirstOfOrder(row, index)">
                {{ formatPrice(row.total_amount) }}
              </template>
            </td>

            <td data-label="وضعیت">
              <StatusLamp v-if="isFirstOfOrder(row, index)" :status="row.order_status" />
            </td>

            <td data-label="اکشن">
              <button
                v-if="isFirstOfOrder(row, index)"
                type="button"
                class="tbl__action"
                @click="openOrder = row.order_number"
              >
                OPEN
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <OrderStatusModal
      v-if="openOrder"
      :order-number="openOrder"
      @close="openOrder = null"
      @updated="onUpdated"
    />
  </AdminLayout>
</template>

<style scoped>
/* ==========================================================================
   AdminOrdersView — Terminal register
   A dense table. Rows are 1.5 lines tall, hairline-ruled, monospace.
   ========================================================================== */

.bar {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
}

.bar__filters {
  display: flex;
}

.bar__filter {
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

.bar__filter:last-child {
  border-inline-end-width: 2px;
}

.bar__filter:hover {
  color: var(--terminal-text);
  background-color: var(--terminal-raised);
}

.bar__filter--on {
  background-color: var(--accent);
  border-color: var(--accent);
  color: var(--paper);
}

.bar__filter:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  position: relative;
}

.bar__search {
  flex: 1;
  min-width: 12rem;
  border: 2px solid var(--terminal-rule);
  background-color: var(--terminal);
  color: var(--terminal-text);
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.06em;
  padding: 0.375rem 0.5rem;
}

.bar__search::placeholder {
  color: var(--terminal-dim);
}

.bar__search:focus {
  outline: none;
  border-color: var(--terminal-text);
  box-shadow: 3px 3px 0 var(--accent);
}

.bar__count {
  font-family: var(--font-terminal);
  font-size: 0.5625rem;
  letter-spacing: 0.14em;
  color: var(--terminal-dim);
}

.err {
  border: 3px solid #a33224;
  background-color: #a33224;
  color: var(--paper);
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  padding: 0.625rem 0.75rem;
  margin-bottom: 1rem;
}

/* --- Table ----------------------------------------------------------------- */
.wrap {
  border: 3px solid var(--terminal-text);
  overflow-x: auto;
}

.tbl {
  width: 100%;
  border-collapse: collapse;
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  white-space: nowrap;
}

.tbl thead th {
  text-align: start;
  font-size: 0.5rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--terminal-dim);
  font-weight: 500;
  padding: 0.5rem 0.5rem;
  border-bottom: 3px solid var(--terminal-text);
  background-color: var(--terminal);
  position: sticky;
  top: 0;
}

.tbl__row {
  border-bottom: 1px solid var(--terminal-rule);
}

/* Alternating rows would fight the grouping; instead the first row of each
   order gets a slightly raised ground so orders read as blocks. */
.tbl__row--head {
  background-color: var(--terminal-raised);
}

.tbl__row:hover {
  background-color: var(--terminal-raised);
}

.tbl td {
  padding: 0.3125rem 0.5rem;
  vertical-align: middle;
}

.tbl__state {
  padding: 1.25rem 0.75rem;
}

.tbl__msg {
  text-align: center;
  color: var(--terminal-dim);
  letter-spacing: 0.14em;
  padding: 2.5rem 0;
}

.tbl__id {
  line-height: 1.3;
}

.tbl__number {
  display: block;
  letter-spacing: 0.06em;
  font-weight: 500;
}

.tbl__date,
.tbl__dim {
  display: block;
  font-size: 0.5rem;
  color: var(--terminal-dim);
}

.tbl__cont {
  color: var(--terminal-rule);
  padding-inline-start: 0.5rem;
}

.tbl__customer {
  display: block;
}

.tbl__product {
  color: var(--terminal-text);
}

.tbl__grind {
  color: var(--terminal-dim);
}

.tbl__grind svg {
  vertical-align: middle;
  margin-inline-end: 0.25rem;
  color: var(--accent);
}

.tbl__num {
  text-align: end;
}

.tbl__mult {
  color: var(--accent);
  margin-inline-start: 0.25rem;
}

.tbl__action {
  border: 2px solid var(--terminal-text);
  background: none;
  color: var(--terminal-text);
  font-family: var(--font-terminal);
  font-size: 0.5rem;
  letter-spacing: 0.14em;
  padding: 0.1875rem 0.4375rem;
  cursor: pointer;
}

.tbl__action:hover {
  background-color: var(--accent);
  border-color: var(--accent);
  color: var(--paper);
}

.tbl__action:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
</style>
