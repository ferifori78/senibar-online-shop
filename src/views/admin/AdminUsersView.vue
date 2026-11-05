<script setup>
import { onMounted, ref, watch } from 'vue'

import AdminLayout from '@/components/layout/AdminLayout.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import LoadingState from '@/components/base/LoadingState.vue'
import StatusLamp from '@/components/admin/StatusLamp.vue'
import { useAuthStore } from '@/stores/auth'
import { useUsersStore } from '@/stores/users'
import { formatDate, formatNumber, formatPrice } from '@/utils/format'

const users = useUsersStore()
const auth = useAuthStore()

const search = ref('')
const expanded = ref(null)

const ROLES = [
  { value: 'customer', label: 'مشتری', lamp: 'idle' },
  { value: 'roaster', label: 'رستر', lamp: 'ok' },
  { value: 'admin', label: 'ادمین', lamp: 'active' },
]

const ROLE_LABEL = Object.fromEntries(ROLES.map((r) => [r.value, r.label]))
const ROLE_LAMP = Object.fromEntries(ROLES.map((r) => [r.value, r.lamp]))

// Debounced: the list refetches server-side on every filter change.
let timer
watch(search, (value) => {
  clearTimeout(timer)
  timer = setTimeout(() => users.applyFilters({ search: value }), 300)
})

async function toggleRow(user) {
  if (expanded.value === user.id) {
    expanded.value = null
    return
  }
  expanded.value = user.id
  await users.fetchUserOrders(user.id)
}

function clearAll() {
  search.value = ''
  users.resetFilters()
}

/** The panel must not let someone strand themselves. The API refuses these
 *  too — this only avoids offering a control that would fail. */
function canDemote(user) {
  return user.id !== auth.userId
}

async function changeRole(user, role) {
  if (role === user.role) return
  await users.setRole(user.id, role)
}

onMounted(() => users.fetchUsers())
</script>

<template>
  <AdminLayout>
    <div class="bar">
      <h1 class="bar__title">USERS</h1>
      <span class="bar__count">{{ formatNumber(users.count) }} حساب</span>
    </div>

    <p v-if="users.error" class="err" role="alert">{{ users.error }}</p>

    <!-- Filters -->
    <section class="filters" aria-label="فیلترها">
      <label class="f">
        <span class="f__label">SEARCH</span>
        <input
          v-model="search"
          type="search"
          class="f__input"
          placeholder="ایمیل، نام، شماره"
        />
      </label>

      <label class="f">
        <span class="f__label">ROLE</span>
        <select
          class="f__input"
          :value="users.filters.role"
          @change="users.applyFilters({ role: $event.target.value })"
        >
          <option value="">همه</option>
          <option v-for="r in ROLES" :key="r.value" :value="r.value">{{ r.label }}</option>
        </select>
      </label>

      <label class="f">
        <span class="f__label">STANDING</span>
        <select
          class="f__input"
          :value="users.filters.is_active"
          @change="users.applyFilters({ is_active: $event.target.value })"
        >
          <option value="">همه</option>
          <option value="true">فعال</option>
          <option value="false">غیرفعال</option>
        </select>
      </label>

      <label class="f">
        <span class="f__label">BOUGHT</span>
        <select
          class="f__input"
          :value="users.filters.buyers"
          @change="users.applyFilters({ buyers: $event.target.value })"
        >
          <option value="">همه</option>
          <option value="true">خرید کرده</option>
          <option value="false">هنوز نخریده</option>
        </select>
      </label>

      <button
        v-if="users.activeFilterCount || search"
        type="button"
        class="filters__clear"
        @click="clearAll"
      >
        پاک کردن
      </button>
    </section>

    <LoadingState
      v-if="users.loading && !users.users.length"
      variant="rows"
      code="READING THE LEDGER"
      :count="8"
      inverse
    />

    <EmptyState
      v-else-if="users.isEmpty"
      icon="search"
      :code="users.activeFilterCount || search ? 'NO MATCH' : 'NO ACCOUNTS'"
      :message="
        users.activeFilterCount || search
          ? 'کاربری با این فیلترها پیدا نشد.'
          : 'هنوز کسی ثبت‌نام نکرده است.'
      "
      inverse
    >
      <BaseButton
        v-if="users.activeFilterCount || search"
        variant="secondary"
        @click="clearAll"
      >
        پاک کردن فیلترها
      </BaseButton>
    </EmptyState>

    <div v-else class="wrap">
      <table class="tbl">
        <thead>
          <tr>
            <th scope="col">حساب</th>
            <th scope="col">نقش</th>
            <th scope="col">وضعیت</th>
            <th scope="col">سفارش</th>
            <th scope="col">خرید کل</th>
            <th scope="col">عضویت</th>
            <th scope="col">اکشن</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="user in users.users" :key="user.id">
            <tr class="tbl__row" :class="{ 'tbl__row--off': !user.is_active }">
              <td data-label="حساب">
                <button type="button" class="who" @click="toggleRow(user)">
                  <span class="who__name">{{ user.display_name }}</span>
                  <span class="who__mail">{{ user.email }}</span>
                </button>
              </td>

              <td data-label="نقش">
                <StatusLamp :state="ROLE_LAMP[user.role]" :label="ROLE_LABEL[user.role]" />
              </td>

              <td data-label="وضعیت">
                <StatusLamp
                  :state="user.is_active ? 'ok' : 'error'"
                  :label="user.is_active ? 'فعال' : 'غیرفعال'"
                />
              </td>

              <td data-label="سفارش" class="tbl__num">
                {{ formatNumber(user.paid_order_count) }}
                <span v-if="user.order_count !== user.paid_order_count" class="dim">
                  / {{ formatNumber(user.order_count) }}
                </span>
              </td>

              <td data-label="خرید کل" class="tbl__num">{{ formatPrice(user.total_spent) }}</td>

              <td data-label="عضویت" class="tbl__dim-cell">{{ formatDate(user.date_joined) }}</td>

              <td data-label="اکشن">
                <div class="tbl__actions">
                  <select
                    class="mini"
                    :value="user.role"
                    :disabled="users.acting || !canDemote(user)"
                    :aria-label="`نقش ${user.display_name}`"
                    @change="changeRole(user, $event.target.value)"
                  >
                    <option v-for="r in ROLES" :key="r.value" :value="r.value">
                      {{ r.label }}
                    </option>
                  </select>

                  <button
                    type="button"
                    class="tbl__action"
                    :class="{ 'tbl__action--danger': user.is_active }"
                    :disabled="users.acting || user.id === auth.userId"
                    @click="users.setActive(user.id, !user.is_active)"
                  >
                    {{ user.is_active ? 'تعلیق' : 'بازگردانی' }}
                  </button>
                </div>
              </td>
            </tr>

            <!-- Drill-down: this customer's orders. -->
            <tr v-if="expanded === user.id" class="drill">
              <td colspan="7">
                <div v-if="!users.ordersByUser[user.id]" class="drill__wait">
                  در حال دریافت سفارش‌ها
                </div>
                <p v-else-if="!users.ordersByUser[user.id].length" class="drill__none">
                  این کاربر هنوز سفارشی ثبت نکرده است.
                </p>
                <ul v-else class="drill__list">
                  <li v-for="o in users.ordersByUser[user.id]" :key="o.number" class="drill__row">
                    <span class="drill__num">{{ o.number }}</span>
                    <span class="drill__status">{{ o.status }}</span>
                    <span class="drill__pay">{{ o.payment_status }}</span>
                    <span class="drill__total">{{ formatPrice(o.total_amount) }}</span>
                    <span class="drill__date">{{ formatDate(o.placed_at) }}</span>
                  </li>
                </ul>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <div v-if="users.hasNext" class="more">
      <BaseButton variant="secondary" :loading="users.loading" @click="users.loadMore()">
        نمایش بیشتر
      </BaseButton>
    </div>
  </AdminLayout>
</template>

<style scoped>
/* ==========================================================================
   AdminUsersView — Terminal register
   ========================================================================== */

.bar {
  display: flex;
  align-items: baseline;
  gap: 1rem;
  padding-block-end: 0.875rem;
  border-block-end: 3px solid var(--term-rule, #2a2a28);
  margin-block-end: 1.25rem;
}

.bar__title {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  margin: 0;
}

.bar__count {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  color: var(--term-dim, #8a8a85);
  margin-inline-start: auto;
}

.err {
  border: 3px solid #a33224;
  background-color: #a33224;
  color: #f4f1ea;
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.75rem;
  padding: 0.625rem 0.75rem;
  margin-block-end: 1rem;
}

/* --- Filters --------------------------------------------------------------- */
.filters {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 0.875rem;
  margin-block-end: 1.5rem;
}

.f {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.f__label {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.5625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--term-dim, #8a8a85);
}

.f__input {
  border: 3px solid var(--term-rule, #2a2a28);
  border-radius: 0;
  background-color: var(--term-sunk, #171715);
  color: inherit;
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.75rem;
  padding: 0.4375rem 0.5625rem;
  min-width: 9rem;
}

.f__input:focus {
  outline: none;
  box-shadow: 3px 3px 0 var(--accent);
}

.filters__clear {
  border: 0;
  background: none;
  color: var(--accent);
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  cursor: pointer;
  padding: 0 0 2px;
  border-block-end: 2px solid var(--accent);
}

/* --- Table ----------------------------------------------------------------- */
.wrap {
  overflow-x: auto;
}

.tbl {
  width: 100%;
  border-collapse: collapse;
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.75rem;
}

.tbl thead th {
  text-align: start;
  font-size: 0.5625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--term-dim, #8a8a85);
  font-weight: 500;
  padding: 0 0.625rem 0.5rem;
  border-block-end: 3px solid var(--term-rule, #2a2a28);
  white-space: nowrap;
}

.tbl__row {
  border-block-end: 2px solid var(--term-rule, #2a2a28);
}

.tbl__row:hover {
  background-color: var(--term-sunk, #171715);
}

/* A suspended account stays legible but visibly stood down. */
.tbl__row--off {
  opacity: 0.55;
}

.tbl td {
  padding: 0.625rem;
  vertical-align: middle;
}

.tbl__num {
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.tbl__dim-cell {
  color: var(--term-dim, #8a8a85);
  white-space: nowrap;
}

.dim {
  color: var(--term-dim, #8a8a85);
}

/* --- Identity cell --------------------------------------------------------- */
.who {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.1875rem;
  border: 0;
  background: none;
  color: inherit;
  font: inherit;
  text-align: start;
  cursor: pointer;
  padding: 0;
}

.who__name {
  border-block-end: 2px solid transparent;
}

.who:hover .who__name {
  border-block-end-color: var(--accent);
}

.who:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: 3px;
}

.who__mail {
  font-size: 0.625rem;
  color: var(--term-dim, #8a8a85);
}

/* --- Actions --------------------------------------------------------------- */
.tbl__actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.mini {
  border: 2px solid var(--term-rule, #2a2a28);
  border-radius: 0;
  background-color: var(--term-sunk, #171715);
  color: inherit;
  font-family: inherit;
  font-size: 0.625rem;
  padding: 0.25rem 0.375rem;
}

.mini:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.tbl__action {
  border: 2px solid var(--term-rule, #2a2a28);
  border-radius: 0;
  background: none;
  color: inherit;
  font-family: inherit;
  font-size: 0.625rem;
  letter-spacing: 0.08em;
  padding: 0.25rem 0.4375rem;
  cursor: pointer;
}

.tbl__action:hover:not(:disabled) {
  border-color: var(--accent);
}

.tbl__action--danger:hover:not(:disabled) {
  background-color: #a33224;
  border-color: #a33224;
}

.tbl__action:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.tbl__action:focus-visible,
.mini:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: 2px;
}

/* --- Drill-down ------------------------------------------------------------ */
.drill td {
  background-color: var(--term-sunk, #171715);
  padding: 0.75rem 0.875rem;
  border-block-end: 2px solid var(--term-rule, #2a2a28);
}

.drill__wait,
.drill__none {
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--term-dim, #8a8a85);
  margin: 0;
}

.drill__list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.drill__row {
  display: grid;
  grid-template-columns: 8rem 7rem 7rem 1fr 7rem;
  gap: 0.75rem;
  font-size: 0.6875rem;
}

@media (max-width: 56rem) {
  .drill__row {
    grid-template-columns: 1fr 1fr;
  }
}

.drill__num {
  color: var(--accent);
}

.drill__status,
.drill__pay,
.drill__date {
  color: var(--term-dim, #8a8a85);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.drill__total {
  font-variant-numeric: tabular-nums;
}

.more {
  display: flex;
  justify-content: center;
  margin-block-start: 2rem;
}
</style>
