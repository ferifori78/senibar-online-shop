<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'

import BaseButton from '@/components/base/BaseButton.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import LoadingState from '@/components/base/LoadingState.vue'
import { blankAddress, useAddressStore } from '@/stores/addresses'
import { useAuthStore } from '@/stores/auth'
import { useOrdersStore } from '@/stores/orders'
import { useSupportStore } from '@/stores/support'
import {
  formatDate,
  formatNumber,
  formatPrice,
  orderStatusLabel,
  ticketStatusLabel,
} from '@/utils/format'

const auth = useAuthStore()
const store = useAddressStore()
const orders = useOrdersStore()
const support = useSupportStore()

// null = the form is closed. 'new' = adding. A number = editing that address.
const editing = ref(null)
const confirmingDelete = ref(null)
const form = reactive(blankAddress())

const isAdding = computed(() => editing.value === 'new')

// Only the most recent few: this is a summary, with links to the full lists.
const recentOrders = computed(() => orders.orders.slice(0, 4))
const openTickets = computed(() => support.tickets.slice(0, 4))

function openNew() {
  editing.value = 'new'
  Object.assign(form, blankAddress())
  // First address becomes the default without the customer having to think.
  form.is_default = store.addresses.length === 0
  // Prefill the name and phone from the profile: they are almost always the
  // recipient, and retyping them is the friction this page exists to remove.
  form.recipient_name = auth.user?.display_name || ''
  form.phone = auth.user?.phone || ''
  store.resetErrors()
}

function openEdit(address) {
  editing.value = address.id
  Object.assign(form, {
    label: address.label || '',
    recipient_name: address.recipient_name,
    phone: address.phone,
    province: address.province,
    city: address.city,
    street_address: address.street_address,
    postal_code: address.postal_code,
    is_default: address.is_default,
  })
  store.resetErrors()
}

function closeForm() {
  editing.value = null
  store.resetErrors()
}

async function submit() {
  const { ok } = await store.save({ ...form }, isAdding.value ? null : editing.value)
  if (ok) closeForm()
}

async function confirmDelete() {
  const { ok } = await store.remove(confirmingDelete.value.id)
  if (ok) confirmingDelete.value = null
}

function errorFor(field) {
  return store.fieldErrors[field] || ''
}

onMounted(() => {
  store.fetchAddresses()
  orders.fetchOrders()
  support.fetchTickets()
})
</script>

<template>
  <main class="register-editorial account">
    <header class="account__head">
      <p class="account__eyebrow">SENOBAR / ACCOUNT</p>
      <h1 class="account__title">حساب من</h1>
      <p v-if="auth.user" class="account__who">
        {{ auth.displayName }}
        <span class="account__mail">{{ auth.user.email }}</span>
      </p>
    </header>

    <!-- --- Addresses ------------------------------------------------------ -->
    <section class="block" aria-labelledby="addr-title">
      <div class="block__head">
        <h2 id="addr-title" class="block__title">آدرس‌های من</h2>
        <BaseButton v-if="!editing" variant="primary" size="sm" @click="openNew">
          آدرس جدید
        </BaseButton>
      </div>

      <p class="block__lede">
        آدرس‌های ذخیره‌شده در تکمیل سفارش قابل انتخاب‌اند، پس لازم نیست هر بار
        دوباره وارد کنید.
      </p>

      <p v-if="store.error && !editing" class="err" role="alert">{{ store.error }}</p>

      <!-- The form serves both adding and editing. -->
      <form v-if="editing" class="addr-form" novalidate @submit.prevent="submit">
        <p class="addr-form__mode">
          {{ isAdding ? 'آدرس جدید' : 'ویرایش آدرس' }}
        </p>

        <div class="addr-form__grid">
          <BaseInput
            v-model="form.label"
            label="عنوان"
            placeholder="خانه، محل کار"
            :error="errorFor('label')"
          />
          <BaseInput
            v-model="form.recipient_name"
            label="نام گیرنده"
            required
            :error="errorFor('recipient_name')"
          />
          <BaseInput
            v-model="form.phone"
            label="شماره تماس"
            inputmode="tel"
            digits="strict"
            placeholder="09120000000"
            required
            :error="errorFor('phone')"
          />
          <BaseInput
            v-model="form.province"
            label="استان"
            required
            :error="errorFor('province')"
          />
          <BaseInput v-model="form.city" label="شهر" required :error="errorFor('city')" />
          <BaseInput
            v-model="form.postal_code"
            label="کد پستی"
            inputmode="numeric"
            digits="strict"
            required
            :error="errorFor('postal_code')"
          />
          <div class="addr-form__wide">
            <BaseInput
              v-model="form.street_address"
              label="نشانی"
              digits="loose"
              required
              :error="errorFor('street_address')"
            />
          </div>
        </div>

        <label class="check">
          <input v-model="form.is_default" type="checkbox" />
          <span class="check__box" aria-hidden="true" />
          <span class="check__label">آدرس پیش‌فرض من باشد</span>
        </label>

        <p v-if="store.error" class="err" role="alert">{{ store.error }}</p>

        <div class="addr-form__actions">
          <BaseButton type="submit" variant="primary" :loading="store.acting">
            {{ isAdding ? 'افزودن آدرس' : 'ذخیره تغییرات' }}
          </BaseButton>
          <BaseButton type="button" variant="secondary" @click="closeForm">انصراف</BaseButton>
        </div>
      </form>

      <LoadingState v-if="store.loading && !store.addresses.length" variant="rows" code="LOADING ADDRESSES" :count="2" />

      <EmptyState
        v-else-if="store.isEmpty && !editing"
        icon="box"
        code="NO ADDRESS SAVED"
        message="هنوز آدرسی ذخیره نکرده‌اید. یکی اضافه کنید تا در سفارش‌های بعدی فقط انتخابش کنید."
      >
        <BaseButton variant="primary" @click="openNew">آدرس جدید</BaseButton>
      </EmptyState>

      <ul v-else-if="store.addresses.length" class="addr-list">
        <li v-for="address in store.addresses" :key="address.id" class="addr">
          <div class="addr__top">
            <span v-if="address.label" class="addr__label">{{ address.label }}</span>
            <span v-if="address.is_default" class="addr__default">پیش‌فرض</span>
          </div>

          <p class="addr__name">{{ address.recipient_name }}</p>
          <p class="addr__lines">
            {{ address.province }}، {{ address.city }}<br />
            {{ address.street_address }}<br />
            کد پستی {{ address.postal_code }} · {{ address.phone }}
          </p>

          <div class="addr__actions">
            <button type="button" class="addr__act" @click="openEdit(address)">ویرایش</button>
            <button
              v-if="!address.is_default"
              type="button"
              class="addr__act"
              :disabled="store.acting"
              @click="store.makeDefault(address.id)"
            >
              پیش‌فرض کن
            </button>
            <button
              type="button"
              class="addr__act addr__act--danger"
              @click="confirmingDelete = address"
            >
              حذف
            </button>
          </div>
        </li>
      </ul>
    </section>

    <!-- --- Orders --------------------------------------------------------- -->
    <section class="block" aria-labelledby="ord-title">
      <div class="block__head">
        <h2 id="ord-title" class="block__title">سفارش‌های من</h2>
        <RouterLink to="/orders" class="block__all">همه‌ی سفارش‌ها</RouterLink>
      </div>

      <LoadingState v-if="orders.loading && !orders.orders.length" variant="rows" code="LOADING ORDERS" :count="3" />

      <EmptyState
        v-else-if="!orders.orders.length"
        icon="bean"
        code="NO ORDERS YET"
        message="هنوز سفارشی ثبت نکرده‌اید."
      >
        <RouterLink to="/products"><BaseButton variant="primary">دیدن قهوه‌ها</BaseButton></RouterLink>
      </EmptyState>

      <ul v-else class="mini-list">
        <li v-for="order in recentOrders" :key="order.number" class="mini">
          <RouterLink :to="`/orders/${order.number}`" class="mini__link">
            <span class="mini__code">{{ order.number }}</span>
            <span class="mini__body">{{ order.summary }}</span>
            <span class="mini__state">{{ orderStatusLabel(order.status) }}</span>
            <span class="mini__amount">{{ formatPrice(order.total_amount) }}</span>
            <span class="mini__date">{{ formatDate(order.placed_at) }}</span>
          </RouterLink>
        </li>
      </ul>
    </section>

    <!-- --- Tickets -------------------------------------------------------- -->
    <section class="block" aria-labelledby="tk-title">
      <div class="block__head">
        <h2 id="tk-title" class="block__title">تیکت‌های پشتیبانی</h2>
        <RouterLink to="/support" class="block__all">همه‌ی تیکت‌ها</RouterLink>
      </div>

      <LoadingState v-if="support.loading && !support.tickets.length" variant="rows" code="LOADING TICKETS" :count="2" />

      <EmptyState
        v-else-if="!support.tickets.length"
        icon="ticket"
        code="NO TICKETS"
        message="تیکتی ثبت نشده است. اگر سؤالی دارید، از صفحه‌ی پشتیبانی بپرسید."
      >
        <RouterLink to="/support"><BaseButton variant="secondary">پشتیبانی</BaseButton></RouterLink>
      </EmptyState>

      <ul v-else class="mini-list">
        <li v-for="ticket in openTickets" :key="ticket.reference" class="mini">
          <RouterLink :to="`/support/${ticket.reference}`" class="mini__link">
            <span class="mini__code">{{ ticket.reference }}</span>
            <span class="mini__body">{{ ticket.subject }}</span>
            <span class="mini__state">{{ ticketStatusLabel(ticket.status) }}</span>
            <span v-if="ticket.unread_count" class="mini__badge">
              {{ formatNumber(ticket.unread_count) }} پیام نخوانده
            </span>
            <span class="mini__date">{{ formatDate(ticket.updated_at) }}</span>
          </RouterLink>
        </li>
      </ul>
    </section>

    <!-- --- Delete confirmation -------------------------------------------- -->
    <div
      v-if="confirmingDelete"
      class="modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="del-title"
    >
      <div class="modal__panel">
        <h2 id="del-title" class="modal__title">حذف آدرس</h2>
        <p class="modal__body">
          آدرس
          <strong>{{ confirmingDelete.label || confirmingDelete.city }}</strong>
          حذف شود؟ سفارش‌های گذشته تغییر نمی‌کنند — نشانی روی هر سفارش جداگانه
          ثبت شده است.
        </p>

        <p v-if="store.error" class="err" role="alert">{{ store.error }}</p>

        <div class="modal__actions">
          <BaseButton variant="primary" :loading="store.acting" @click="confirmDelete">
            حذف
          </BaseButton>
          <BaseButton variant="secondary" @click="confirmingDelete = null">انصراف</BaseButton>
        </div>
      </div>
    </div>
  </main>
</template>

<style scoped>
/* ==========================================================================
   AccountView — Editorial register
   ========================================================================== */

.account {
  padding: clamp(2rem, 6vw, 4.5rem) clamp(1.25rem, 5vw, 4rem) 5rem;
}

/* --- Header ---------------------------------------------------------------- */
.account__eyebrow {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
  margin: 0;
}

.account__title {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: clamp(2.25rem, 7vw, 3.5rem);
  line-height: 1.05;
  font-weight: 600;
  margin: 0.75rem 0 0;
}

.account__who {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 0.75rem;
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 1.0625rem;
  margin: 0.875rem 0 0;
}

.account__mail {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.08em;
  color: var(--ink-muted);
}

/* --- Blocks ---------------------------------------------------------------- */
.block {
  margin-block-start: clamp(2.5rem, 6vw, 4rem);
  padding-block-start: 1.5rem;
  border-block-start: 3px solid var(--divider);
}

.block__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.block__title {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: clamp(1.5rem, 4vw, 2rem);
  font-weight: 600;
  margin: 0;
}

.block__all {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent);
  text-decoration: none;
  border-block-end: 2px solid var(--accent);
}

.block__lede {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 0.9375rem;
  line-height: 1.8;
  color: var(--ink-muted);
  max-width: 40rem;
  margin: 0.625rem 0 1.5rem;
}

.err {
  border: 3px solid #a33224;
  background-color: #a33224;
  color: var(--paper);
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.75rem;
  padding: 0.625rem 0.75rem;
  margin-block: 1rem;
}

/* --- Address form ---------------------------------------------------------- */
.addr-form {
  border: 3px solid var(--ink);
  box-shadow: 6px 6px 0 var(--shadow);
  padding: clamp(1.25rem, 3vw, 1.75rem);
  margin-block-end: 2rem;
}

.addr-form__mode {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent);
  margin: 0 0 1.25rem;
}

.addr-form__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
  gap: 1rem;
}

.addr-form__wide {
  grid-column: 1 / -1;
}

.addr-form__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.875rem;
  margin-block-start: 1.5rem;
}

/* Square checkbox, matching the grind and gateway selectors. */
.check {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  margin-block-start: 1.25rem;
  cursor: pointer;
}

.check input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

.check__box {
  flex: none;
  width: 1.125rem;
  height: 1.125rem;
  border: 3px solid var(--ink);
  background-color: var(--paper);
}

.check input:checked + .check__box {
  background-color: var(--accent);
}

.check input:focus-visible + .check__box {
  outline: 3px solid var(--accent);
  outline-offset: 3px;
}

.check__label {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 0.9375rem;
}

/* --- Address list ---------------------------------------------------------- */
.addr-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(17rem, 1fr));
  gap: 1.25rem;
  list-style: none;
  padding: 0;
  margin: 0;
}

.addr {
  display: flex;
  flex-direction: column;
  border: 3px solid var(--ink);
  padding: 1rem 1.125rem 0.875rem;
}

.addr__top {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  min-height: 1.25rem;
}

.addr__label {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
}

.addr__default {
  background-color: var(--accent);
  color: var(--paper);
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.5625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  padding: 0.1875rem 0.375rem;
}

.addr__name {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 1.125rem;
  font-weight: 600;
  margin: 0.5rem 0 0;
}

.addr__lines {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 0.9375rem;
  line-height: 1.9;
  color: var(--ink-muted);
  margin: 0.375rem 0 0;
  flex: 1;
}

.addr__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-block-start: 1rem;
  padding-block-start: 0.75rem;
  border-block-start: 2px solid var(--rule);
}

.addr__act {
  border: 0;
  background: none;
  padding: 0;
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ink);
  cursor: pointer;
  border-block-end: 2px solid var(--rule);
}

.addr__act:hover:not(:disabled) {
  border-block-end-color: var(--accent);
}

.addr__act--danger {
  color: #a33224;
}

.addr__act:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.addr__act:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: 3px;
}

/* --- Compact lists (orders, tickets) --------------------------------------- */
.mini-list {
  list-style: none;
  padding: 0;
  margin: 0;
  border-block-start: 2px solid var(--rule);
}

.mini {
  border-block-end: 2px solid var(--rule);
}

.mini__link {
  display: grid;
  grid-template-columns: 8rem 1fr 8rem 8rem 7rem;
  align-items: baseline;
  gap: 1rem;
  padding: 0.875rem 0.25rem;
  color: inherit;
  text-decoration: none;
}

@media (max-width: 56rem) {
  .mini__link {
    grid-template-columns: 1fr 1fr;
  }
}

.mini__link:hover {
  background-color: var(--paper-sunk);
}

.mini__link:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: -3px;
}

.mini__code {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.08em;
  color: var(--accent);
}

.mini__body {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 0.9375rem;
}

.mini__state,
.mini__date {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ink-muted);
}

.mini__amount {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 0.9375rem;
  font-variant-numeric: tabular-nums;
}

.mini__badge {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.5625rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--accent);
}

/* --- Modal ----------------------------------------------------------------- */
.modal {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: grid;
  place-items: center;
  padding: 1.25rem;
  background-color: rgb(0 0 0 / 0.5);
}

.modal__panel {
  width: min(28rem, 100%);
  border: 3px solid var(--ink);
  background-color: var(--paper);
  box-shadow: 6px 6px 0 var(--shadow);
  padding: 1.5rem;
}

.modal__title {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 1.375rem;
  font-weight: 600;
  margin: 0 0 0.875rem;
}

.modal__body {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 0.9375rem;
  line-height: 1.8;
  color: var(--ink-muted);
  margin: 0;
}

.modal__actions {
  display: flex;
  gap: 0.875rem;
  margin-block-start: 1.5rem;
}
</style>
