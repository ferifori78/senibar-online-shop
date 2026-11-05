<script setup>
import { onMounted, reactive, ref } from 'vue'

import AdminLayout from '@/components/layout/AdminLayout.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import LoadingState from '@/components/base/LoadingState.vue'
import StatusLamp from '@/components/admin/StatusLamp.vue'
import { useAdminStore } from '@/stores/admin'
import {
  formatDate,
  formatNumber,
  formatWeight,
  freshnessLabel,
  freshnessState,
} from '@/utils/format'

const admin = useAdminStore()

const creating = ref(false)
// The id being edited, or null for a new batch. The same form serves both.
const editingId = ref(null)
const confirmingDelete = ref(null)
const today = new Date().toISOString().slice(0, 10)

const STATUSES = [
  { value: 'resting', label: 'در حال استراحت' },
  { value: 'available', label: 'موجود' },
  { value: 'depleted', label: 'تمام شده' },
  { value: 'withdrawn', label: 'خارج شده' },
]

const STATUS_LAMP = {
  resting: 'warn',
  available: 'ok',
  depleted: 'idle',
  withdrawn: 'error',
}

const form = reactive({
  product: '',
  batch_code: '',
  roast_date: today,
  initial_grams: null,
  roast_profile: '',
  development_time_ratio: null,
  status: 'resting',
  notes: '',
})

const localErrors = ref({})

function reset() {
  Object.assign(form, {
    product: '',
    batch_code: '',
    roast_date: today,
    initial_grams: null,
    roast_profile: '',
    development_time_ratio: null,
    status: 'resting',
    notes: '',
  })
  localErrors.value = {}
}

function errorFor(field) {
  return admin.fieldErrors[field] || localErrors.value[field] || ''
}

function validate() {
  const errors = {}
  if (!form.product) errors.product = 'محصول را انتخاب کنید.'
  if (!form.batch_code.trim()) errors.batch_code = 'کد لات لازم است.'
  if (!form.initial_grams || form.initial_grams < 1) {
    errors.initial_grams = 'مقدار باید بزرگ‌تر از صفر باشد.'
  }
  if (form.roast_date > today) errors.roast_date = 'تاریخ رست نمی‌تواند در آینده باشد.'
  localErrors.value = errors
  return Object.keys(errors).length === 0
}

/** Suggest a code from the product and today's date, e.g. ETH-260830-01. */
function suggestCode() {
  const product = admin.products.find((p) => p.id === form.product)
  if (!product) return
  const prefix = product.origin_country.slice(0, 3).toUpperCase()
  const stamp = form.roast_date.replaceAll('-', '').slice(2)
  const seq = String(
    admin.batches.filter((b) => b.batch_code.startsWith(`${prefix}-${stamp}`)).length + 1,
  ).padStart(2, '0')
  form.batch_code = `${prefix}-${stamp}-${seq}`
}

async function submit() {
  localErrors.value = {}
  if (!validate()) return

  const { ok } = await admin.saveBatch({ ...form }, editingId.value)
  if (ok) {
    creating.value = false
    editingId.value = null
    reset()
    admin.fetchBatches()
  }
}

/** Load a batch into the form. Quantities are not editable here: stock moves
 *  through orders and the inventory screen's audited adjustments, never by
 *  retyping a number on a form. */
function edit(batch) {
  editingId.value = batch.id
  creating.value = true
  Object.assign(form, {
    product: batch.product,
    batch_code: batch.batch_code,
    roast_date: batch.roast_date,
    initial_grams: batch.initial_grams,
    roast_profile: batch.roast_profile || '',
    development_time_ratio: batch.development_time_ratio,
    status: batch.status,
    notes: batch.notes || '',
  })
  localErrors.value = {}
  admin.resetErrors()
}

function cancelForm() {
  creating.value = false
  editingId.value = null
  reset()
  admin.resetErrors()
}

async function confirmDelete() {
  const { ok } = await admin.deleteBatch(confirmingDelete.value.id)
  if (ok) confirmingDelete.value = null
}

/** Publish a resting batch so the storefront can sell from it. */
async function release(batch) {
  await admin.saveBatch({ status: 'available' }, batch.id)
}

async function withdraw(batch) {
  await admin.saveBatch({ status: 'withdrawn' }, batch.id)
}

onMounted(() => {
  admin.fetchBatches()
  admin.fetchProducts()
})
</script>

<template>
  <AdminLayout>
    <div class="bar">
      <span class="bar__count">{{ formatNumber(admin.batches.length) }} BATCHES</span>
      <BaseButton variant="primary" size="sm" inverse @click="creating ? cancelForm() : (creating = true)">
        {{ creating ? 'بستن فرم' : '+ بچ جدید' }}
      </BaseButton>
    </div>

    <p v-if="admin.error" class="err" role="alert">{{ admin.error }}</p>

    <!-- Inline create form. A batch is small enough not to need a modal. -->
    <form v-if="creating" class="new" novalidate @submit.prevent="submit">
      <p class="new__mode">
        {{ editingId ? `ویرایش بچ ${form.batch_code}` : 'بچ جدید' }}
      </p>

      <div class="new__grid">
        <label class="f">
          <span class="f__label">محصول<i>*</i></span>
          <select
            v-model="form.product"
            class="f__input"
            :class="{ 'f__input--err': errorFor('product') }"
            @change="suggestCode"
          >
            <option value="" disabled>— انتخاب کنید —</option>
            <option v-for="p in admin.products" :key="p.id" :value="p.id">
              {{ p.name }} — {{ p.origin_country }}
            </option>
          </select>
          <span v-if="errorFor('product')" class="f__err">{{ errorFor('product') }}</span>
        </label>

        <label class="f">
          <span class="f__label">کد لات<i>*</i></span>
          <input
            v-model="form.batch_code"
            class="f__input"
            :class="{ 'f__input--err': errorFor('batch_code') }"
            placeholder="ETH-260830-01"
          />
          <span v-if="errorFor('batch_code')" class="f__err">{{ errorFor('batch_code') }}</span>
        </label>

        <label class="f">
          <span class="f__label">تاریخ رست<i>*</i></span>
          <input
            v-model="form.roast_date"
            type="date"
            :max="today"
            class="f__input"
            :class="{ 'f__input--err': errorFor('roast_date') }"
          />
          <span v-if="errorFor('roast_date')" class="f__err">{{ errorFor('roast_date') }}</span>
        </label>

        <label class="f">
          <span class="f__label">مقدار (گرم)<i>*</i></span>
          <input
            v-digits
            v-model.number="form.initial_grams"
            type="number"
            class="f__input"
            :class="{ 'f__input--err': errorFor('initial_grams') }"
          />
          <span v-if="errorFor('initial_grams')" class="f__err">
            {{ errorFor('initial_grams') }}
          </span>
        </label>

        <label class="f">
          <span class="f__label">پروفایل رست</span>
          <input v-model="form.roast_profile" class="f__input" placeholder="Filter / Omni" />
        </label>

        <label class="f">
          <span class="f__label">DTR (٪)</span>
          <input
            v-digits
            v-model.number="form.development_time_ratio"
            type="number"
            step="0.01"
            class="f__input"
            placeholder="21.50"
          />
        </label>

        <label class="f">
          <span class="f__label">وضعیت</span>
          <select v-model="form.status" class="f__input">
            <option v-for="s in STATUSES" :key="s.value" :value="s.value">{{ s.label }}</option>
          </select>
        </label>

        <label class="f f--full">
          <span class="f__label">یادداشت</span>
          <input v-model="form.notes" class="f__input" />
        </label>
      </div>

      <div class="new__actions">
        <BaseButton type="submit" variant="primary" size="sm" inverse :loading="admin.acting">
          {{ editingId ? 'ذخیره تغییرات' : 'ثبت بچ' }}
        </BaseButton>
        <BaseButton
          type="button"
          variant="ghost"
          size="sm"
          inverse
          @click="cancelForm()"
        >
          انصراف
        </BaseButton>
      </div>
    </form>

    <!-- Table ---------------------------------------------------------- -->
    <div class="wrap">
      <table class="tbl tbl-responsive">
        <thead>
          <tr>
            <th scope="col">کد لات</th>
            <th scope="col">قهوه</th>
            <th scope="col">تاریخ رست</th>
            <th scope="col" class="tbl__num">اولیه</th>
            <th scope="col" class="tbl__num">باقی</th>
            <th scope="col" class="tbl__num">رزرو</th>
            <th scope="col">تازگی</th>
            <th scope="col">وضعیت</th>
            <th scope="col">اکشن</th>
          </tr>
        </thead>

        <tbody>
          <tr v-if="admin.loading && !admin.batches.length">
            <td colspan="9" class="tbl__state">
                <LoadingState variant="inline" code="LOADING" inverse />
              </td>
          </tr>

          <tr v-else-if="!admin.batches.length">
            <td colspan="9" class="tbl__state">
                <EmptyState icon="box" code="NO BATCHES LOGGED"
                            message="هنوز بچی ثبت نشده است. بدون بچ رست، محصول موجودی ندارد." inverse compact />
              </td>
          </tr>

          <tr v-for="batch in admin.batches" v-else :key="batch.id" class="tbl__row">
            <td data-label="کد لات" class="tbl__code">{{ batch.batch_code }}</td>
            <td data-label="قهوه">{{ batch.product_name }}</td>
            <td data-label="تاریخ رست" class="tbl__dim-cell">{{ formatDate(batch.roast_date) }}</td>
            <td data-label="اولیه" class="tbl__num">{{ formatWeight(batch.initial_grams) }}</td>
            <td data-label="باقی" class="tbl__num">{{ formatWeight(batch.remaining_grams) }}</td>
            <td data-label="رزرو" class="tbl__num tbl__dim-cell">{{ formatWeight(batch.reserved_grams) }}</td>
            <td data-label="تازگی">
              <StatusLamp
                :state="freshnessState(batch.freshness)"
                :label="freshnessLabel(batch.freshness)"
              />
            </td>
            <td data-label="وضعیت">
              <StatusLamp
                :state="STATUS_LAMP[batch.status]"
                :label="batch.status_display"
              />
            </td>
            <td data-label="اکشن" class="tbl__actions">
              <button
                v-if="batch.status === 'resting'"
                type="button"
                class="tbl__action"
                @click="release(batch)"
              >
                RELEASE
              </button>
              <button
                v-if="batch.status === 'available'"
                type="button"
                class="tbl__action"
                @click="withdraw(batch)"
              >
                WITHDRAW
              </button>
              <button type="button" class="tbl__action" @click="edit(batch)">EDIT</button>
              <button
                type="button"
                class="tbl__action tbl__action--danger"
                @click="confirmingDelete = batch"
              >
                DELETE
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <!-- Deleting a batch is only offered for one nobody has bought from; the
         API refuses the rest with a sentence shown here. -->
    <div
      v-if="confirmingDelete"
      class="modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="del-title"
    >
      <div class="modal__panel">
        <h2 id="del-title" class="modal__title">حذف بچ</h2>
        <p class="modal__body">
          بچ <strong>{{ confirmingDelete.batch_code }}</strong> برای همیشه حذف شود؟
          اگر از این بچ فروشی انجام شده باشد، سرور حذف را رد می‌کند و باید به‌جای
          آن «خارج شده»‌اش کنید.
        </p>

        <p v-if="admin.error" class="err" role="alert">{{ admin.error }}</p>

        <div class="modal__actions">
          <BaseButton variant="primary" size="sm" inverse :loading="admin.acting" @click="confirmDelete">
            حذف
          </BaseButton>
          <BaseButton variant="ghost" size="sm" inverse @click="confirmingDelete = null">
            انصراف
          </BaseButton>
        </div>
      </div>
    </div>
  </AdminLayout>
</template>

<style scoped>
/* ==========================================================================
   AdminBatchesView — Terminal register
   ========================================================================== */

.bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
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

/* --- New batch form -------------------------------------------------------- */
.new {
  border: 3px solid var(--accent);
  padding: 1rem;
  margin-bottom: 1.25rem;
}

.new__mode {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent);
  margin: 0 0 0.875rem;
}

.new__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
  gap: 0.75rem;
}

.new__actions {
  display: flex;
  gap: 0.75rem;
  margin-top: 1rem;
}

.f {
  display: flex;
  flex-direction: column;
  gap: 0.3125rem;
  min-width: 0;
}

.f--full {
  grid-column: 1 / -1;
}

.f__label {
  font-family: var(--font-terminal);
  font-size: 0.5rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--terminal-dim);
}

.f__label i {
  color: var(--accent);
  font-style: normal;
  margin-inline-start: 0.1875rem;
}

.f__input {
  width: 100%;
  border: 2px solid var(--terminal-rule);
  background-color: var(--terminal);
  color: var(--terminal-text);
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  padding: 0.4375rem 0.5rem;
}

.f__input:focus {
  outline: none;
  border-color: var(--terminal-text);
  box-shadow: 3px 3px 0 var(--accent);
}

.f__input--err {
  border-color: #a33224;
}

.f__err {
  font-family: var(--font-terminal);
  font-size: 0.5rem;
  color: #d4614f;
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
  padding: 0.5rem;
  border-bottom: 3px solid var(--terminal-text);
}

.tbl__row {
  border-bottom: 1px solid var(--terminal-rule);
}

.tbl__row:hover {
  background-color: var(--terminal-raised);
}

.tbl td {
  padding: 0.375rem 0.5rem;
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

.tbl__code {
  font-weight: 500;
  letter-spacing: 0.06em;
}

.tbl__dim-cell {
  color: var(--terminal-dim);
}

.tbl__num {
  text-align: end;
}

.tbl__actions {
  display: flex;
  gap: 0.375rem;
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

.tbl__action--danger:hover {
  background-color: #a33224;
  border-color: #a33224;
}

.tbl__action:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

/* --- Delete confirmation --------------------------------------------------- */
.modal {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: grid;
  place-items: center;
  padding: 1.25rem;
  background-color: rgb(0 0 0 / 0.6);
}

.modal__panel {
  width: min(28rem, 100%);
  border: 3px solid var(--term-rule, #2a2a28);
  background-color: var(--term-paper, #1c1c1a);
  box-shadow: 6px 6px 0 #000;
  padding: 1.25rem;
}

.modal__title {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.8125rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  margin: 0 0 0.875rem;
}

.modal__body {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.75rem;
  line-height: 1.8;
  color: var(--term-dim, #8a8a85);
  margin: 0;
}

.modal__actions {
  display: flex;
  gap: 0.75rem;
  margin-block-start: 1.25rem;
}
</style>