<script setup>
import { computed, onMounted, reactive, ref } from 'vue'

import AdminLayout from '@/components/layout/AdminLayout.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import LoadingState from '@/components/base/LoadingState.vue'
import StatusLamp from '@/components/admin/StatusLamp.vue'
import { useInventoryStore } from '@/stores/inventory'
import {
  formatDate,
  formatNumber,
  formatWeight,
  freshnessLabel,
  freshnessState,
} from '@/utils/format'

const inv = useInventoryStore()

const expanded = ref(null)
const adjusting = ref(null) // the batch being corrected

const VIEWS = [
  { value: 'all', label: 'همه' },
  { value: 'low', label: 'رو به اتمام' },
  { value: 'out', label: 'ناموجود' },
]

const REASONS = [
  { value: 'recount', label: 'شمارش مجدد' },
  { value: 'spillage', label: 'ریختن / تلف' },
  { value: 'sample', label: 'نمونه / کاپینگ' },
  { value: 'return', label: 'مرجوعی مشتری' },
  { value: 'correction', label: 'اصلاح داده' },
  { value: 'other', label: 'سایر' },
]

const LEVEL_LAMP = { ok: 'ok', low: 'warn', out: 'error' }
const LEVEL_TEXT = { ok: 'موجود', low: 'رو به اتمام', out: 'ناموجود' }

const form = reactive({ direction: '-', grams: null, reason: 'recount', note: '' })
const formError = ref('')

// Signed delta: the API takes one number, the form takes a direction and a
// magnitude, because "-250" typed into a box is easy to get wrong.
const delta = computed(() => {
  const grams = Number(form.grams)
  if (!grams || grams <= 0) return 0
  return form.direction === '-' ? -grams : grams
})

function openAdjust(batch) {
  adjusting.value = batch
  formError.value = ''
  Object.assign(form, { direction: '-', grams: null, reason: 'recount', note: '' })
  inv.resetErrors()
}

function closeAdjust() {
  adjusting.value = null
  formError.value = ''
}

async function submitAdjust() {
  formError.value = ''

  if (!delta.value) {
    formError.value = 'مقدار را وارد کنید.'
    return
  }
  if (form.reason === 'other' && !form.note.trim()) {
    formError.value = 'برای دلیل «سایر» توضیح لازم است.'
    return
  }

  const result = await inv.adjust(adjusting.value.id, {
    delta_grams: delta.value,
    reason: form.reason,
    note: form.note.trim(),
  })

  // On failure the store holds the server's sentence, which names the actual
  // grams involved — leave the dialog open so it can be read and corrected.
  if (result.ok) closeAdjust()
}

function toggleRow(row) {
  expanded.value = expanded.value === row.product_id ? null : row.product_id
}

onMounted(() => {
  inv.fetchInventory()
  inv.fetchLog()
})
</script>

<template>
  <AdminLayout>
    <div class="bar">
      <h1 class="bar__title">INVENTORY</h1>
      <span v-if="inv.totals" class="bar__count">
        {{ formatWeight(inv.totals.total_sellable_grams) }} قابل فروش
      </span>
    </div>

    <p v-if="inv.error && !adjusting" class="err" role="alert">{{ inv.error }}</p>

    <!-- Totals -->
    <section v-if="inv.totals" class="stats" aria-label="خلاصه">
      <div class="stat">
        <span class="stat__label">SELLABLE</span>
        <span class="stat__value">{{ formatWeight(inv.totals.total_sellable_grams) }}</span>
      </div>
      <div class="stat">
        <span class="stat__label">RESERVED</span>
        <span class="stat__value">{{ formatWeight(inv.totals.total_reserved_grams) }}</span>
        <span class="stat__note">به سفارش‌های باز تعهد شده</span>
      </div>
      <div class="stat" :class="{ 'stat--warn': inv.totals.low_stock }">
        <span class="stat__label">LOW</span>
        <span class="stat__value">{{ formatNumber(inv.totals.low_stock) }}</span>
        <span class="stat__note">زیر {{ formatWeight(inv.totals.low_stock_threshold) }}</span>
      </div>
      <div class="stat" :class="{ 'stat--bad': inv.totals.out_of_stock }">
        <span class="stat__label">OUT</span>
        <span class="stat__value">{{ formatNumber(inv.totals.out_of_stock) }}</span>
        <span class="stat__note">قابل فروش نیست</span>
      </div>
    </section>

    <!-- Batches past peak that still hold stock. -->
    <section v-if="inv.fading.length" class="fading" aria-labelledby="fading-title">
      <h2 id="fading-title" class="fading__title">PAST PEAK — بفروشید یا خارج کنید</h2>
      <ul class="fading__list">
        <li v-for="b in inv.fading" :key="b.id" class="fading__row">
          <span class="fading__code">{{ b.batch_code }}</span>
          <span class="fading__name">{{ b.product_name }}</span>
          <span class="fading__days">{{ formatNumber(b.days_since_roast) }} روز</span>
          <span class="fading__grams">{{ formatWeight(b.sellable_grams) }}</span>
        </li>
      </ul>
    </section>

    <!-- Controls -->
    <section class="filters" aria-label="فیلترها">
      <div class="views" role="group" aria-label="نما">
        <button
          v-for="v in VIEWS"
          :key="v.value"
          type="button"
          class="views__btn"
          :class="{ 'views__btn--on': inv.view === v.value }"
          :aria-pressed="inv.view === v.value"
          @click="inv.view = v.value"
        >
          {{ v.label }}
        </button>
      </div>

      <label class="f">
        <span class="f__label">SEARCH</span>
        <input
          v-model="inv.search"
          type="search"
          class="f__input"
          placeholder="نام قهوه یا کد بچ"
        />
      </label>
    </section>

    <LoadingState
      v-if="inv.loading && !inv.products.length"
      variant="rows"
      code="COUNTING THE SHELF"
      :count="6"
      inverse
    />

    <EmptyState
      v-else-if="inv.isEmpty"
      icon="box"
      :code="inv.search || inv.view !== 'all' ? 'NO MATCH' : 'NOTHING TRACKED'"
      :message="
        inv.search || inv.view !== 'all'
          ? 'قهوه‌ای با این فیلترها پیدا نشد.'
          : 'هنوز محصول منتشرشده‌ای برای ردیابی موجودی نیست.'
      "
      inverse
    />

    <div v-else class="wrap">
      <table class="tbl">
        <thead>
          <tr>
            <th scope="col">قهوه</th>
            <th scope="col">وضعیت</th>
            <th scope="col">قابل فروش</th>
            <th scope="col">رزرو</th>
            <th scope="col">کل</th>
            <th scope="col">بچ</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="row in inv.visible" :key="row.product_id">
            <tr class="tbl__row">
              <td data-label="قهوه">
                <button type="button" class="who" @click="toggleRow(row)">
                  <span class="who__name">{{ row.name }}</span>
                  <span v-if="!row.batch_count" class="who__flag">بدون بچ فعال</span>
                </button>
              </td>
              <td data-label="وضعیت">
                <StatusLamp
                  :state="LEVEL_LAMP[inv.levelOf(row)]"
                  :label="LEVEL_TEXT[inv.levelOf(row)]"
                />
              </td>
              <td data-label="قابل فروش" class="tbl__num tbl__strong">
                {{ formatWeight(row.sellable_grams) }}
              </td>
              <td data-label="رزرو" class="tbl__num dim">{{ formatWeight(row.reserved_grams) }}</td>
              <td data-label="کل" class="tbl__num dim">{{ formatWeight(row.remaining_grams) }}</td>
              <td data-label="بچ" class="tbl__num dim">{{ formatNumber(row.batch_count) }}</td>
            </tr>

            <!-- Batches behind the number. -->
            <tr v-if="expanded === row.product_id" class="drill">
              <td colspan="6">
                <p v-if="!row.batches.length" class="drill__none">
                  هیچ بچ فعالی برای این قهوه ثبت نشده است.
                </p>
                <ul v-else class="drill__list">
                  <li v-for="b in row.batches" :key="b.id" class="drill__row">
                    <span class="drill__code">{{ b.batch_code }}</span>
                    <StatusLamp
                      :state="freshnessState(b.freshness)"
                      :label="freshnessLabel(b.freshness)"
                    />
                    <span class="drill__date">{{ formatDate(b.roast_date) }}</span>
                    <span class="drill__grams">
                      {{ formatWeight(b.sellable_grams) }}
                      <span class="dim">/ {{ formatWeight(b.initial_grams) }}</span>
                    </span>
                    <button type="button" class="tbl__action" @click="openAdjust(b)">
                      تعدیل
                    </button>
                  </li>
                </ul>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <!-- Recent hand corrections -->
    <section v-if="inv.log.length" class="log" aria-labelledby="log-title">
      <h2 id="log-title" class="log__title">ADJUSTMENT LOG</h2>
      <ul class="log__list">
        <li v-for="entry in inv.log.slice(0, 12)" :key="entry.id" class="log__row">
          <span class="log__delta" :class="entry.delta_grams < 0 ? 'log__delta--down' : 'log__delta--up'">
            {{ entry.delta_grams > 0 ? '+' : '' }}{{ formatNumber(entry.delta_grams) }}g
          </span>
          <span class="log__code">{{ entry.batch_code }}</span>
          <span class="log__reason">{{ entry.reason_display }}</span>
          <span class="log__note">{{ entry.note }}</span>
          <span class="log__who">{{ entry.actor_name }}</span>
          <span class="log__when">{{ formatDate(entry.created_at) }}</span>
        </li>
      </ul>
    </section>

    <!-- --- Adjust dialog --------------------------------------------------- -->
    <div v-if="adjusting" class="modal" role="dialog" aria-modal="true" aria-labelledby="adj-title">
      <div class="modal__panel">
        <header class="modal__head">
          <h2 id="adj-title" class="modal__title">تعدیل موجودی</h2>
          <span class="modal__code">{{ adjusting.batch_code }}</span>
        </header>

        <p class="modal__now">
          موجودی فعلی: <strong>{{ formatWeight(adjusting.remaining_grams) }}</strong>
          <span v-if="adjusting.reserved_grams" class="dim">
            — {{ formatWeight(adjusting.reserved_grams) }} رزرو شده و قابل برداشت نیست
          </span>
        </p>

        <div class="modal__grid">
          <label class="f">
            <span class="f__label">جهت</span>
            <select v-model="form.direction" class="f__input">
              <option value="-">کاهش</option>
              <option value="+">افزایش</option>
            </select>
          </label>

          <label class="f">
            <span class="f__label">مقدار (گرم)</span>
            <input v-digits v-model.number="form.grams" type="number" min="1" class="f__input" />
          </label>

          <label class="f">
            <span class="f__label">دلیل</span>
            <select v-model="form.reason" class="f__input">
              <option v-for="r in REASONS" :key="r.value" :value="r.value">{{ r.label }}</option>
            </select>
          </label>

          <label class="f f--full">
            <span class="f__label">
              توضیح
              <i v-if="form.reason === 'other'" class="f__req">الزامی</i>
            </span>
            <input v-model="form.note" type="text" maxlength="200" class="f__input" />
          </label>
        </div>

        <p v-if="delta" class="modal__preview">
          {{ formatWeight(adjusting.remaining_grams) }}
          <span class="modal__arrow" aria-hidden="true">&#8592;</span>
          <strong>{{ formatWeight(adjusting.remaining_grams + delta) }}</strong>
        </p>

        <p v-if="formError || inv.error" class="err" role="alert">
          {{ formError || inv.error }}
        </p>

        <div class="modal__actions">
          <BaseButton variant="primary" :loading="inv.acting" @click="submitAdjust">
            ثبت تعدیل
          </BaseButton>
          <BaseButton variant="secondary" @click="closeAdjust">انصراف</BaseButton>
        </div>
      </div>
    </div>
  </AdminLayout>
</template>

<style scoped>
/* ==========================================================================
   AdminInventoryView — Terminal register
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
  margin-block: 1rem;
}

/* --- Totals ---------------------------------------------------------------- */
.stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
  gap: 0;
  border: 3px solid var(--term-rule, #2a2a28);
  margin-block-end: 1.5rem;
}

.stat {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.875rem 1rem;
  border-inline-end: 3px solid var(--term-rule, #2a2a28);
}

.stat:last-child {
  border-inline-end: 0;
}

.stat__label {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.5625rem;
  letter-spacing: 0.14em;
  color: var(--term-dim, #8a8a85);
}

.stat__value {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 1.25rem;
  font-variant-numeric: tabular-nums;
}

.stat__note {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.5625rem;
  color: var(--term-dim, #8a8a85);
}

.stat--warn .stat__value {
  color: #d19a2a;
}

.stat--bad .stat__value {
  color: var(--accent);
}

/* --- Past peak ------------------------------------------------------------- */
.fading {
  border: 3px solid #d19a2a;
  padding: 0.875rem 1rem;
  margin-block-end: 1.5rem;
}

.fading__title {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #d19a2a;
  margin: 0 0 0.625rem;
}

.fading__list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.fading__row {
  display: grid;
  grid-template-columns: 8rem 1fr 6rem 7rem;
  gap: 0.75rem;
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
}

@media (max-width: 52rem) {
  .fading__row {
    grid-template-columns: 1fr 1fr;
  }
}

.fading__code {
  color: #d19a2a;
}

.fading__days,
.fading__grams {
  font-variant-numeric: tabular-nums;
  color: var(--term-dim, #8a8a85);
}

/* --- Filters --------------------------------------------------------------- */
.filters {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 0.875rem;
  margin-block-end: 1.25rem;
}

.views {
  display: flex;
}

.views__btn {
  border: 3px solid var(--term-rule, #2a2a28);
  border-inline-start-width: 0;
  border-radius: 0;
  background: none;
  color: inherit;
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  padding: 0.4375rem 0.75rem;
  cursor: pointer;
}

.views__btn:first-child {
  border-inline-start-width: 3px;
}

.views__btn--on {
  background-color: var(--accent);
  border-color: var(--accent);
  color: #f4f1ea;
}

.views__btn:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: 2px;
}

.f {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.f--full {
  grid-column: 1 / -1;
}

.f__label {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.5625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--term-dim, #8a8a85);
}

.f__req {
  color: var(--accent);
  font-style: normal;
  margin-inline-start: 0.375rem;
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
  width: 100%;
}

.f__input:focus {
  outline: none;
  box-shadow: 3px 3px 0 var(--accent);
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

.tbl td {
  padding: 0.625rem;
  vertical-align: middle;
}

.tbl__num {
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.tbl__strong {
  font-size: 0.8125rem;
}

.dim {
  color: var(--term-dim, #8a8a85);
}

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

.who__flag {
  font-size: 0.5625rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--accent);
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

.tbl__action:hover {
  border-color: var(--accent);
}

.tbl__action:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: 2px;
}

/* --- Drill-down ------------------------------------------------------------ */
.drill td {
  background-color: var(--term-sunk, #171715);
  padding: 0.75rem 0.875rem;
  border-block-end: 2px solid var(--term-rule, #2a2a28);
}

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
  gap: 0.5rem;
}

.drill__row {
  display: grid;
  grid-template-columns: 8rem 9rem 7rem 1fr auto;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.6875rem;
}

@media (max-width: 56rem) {
  .drill__row {
    grid-template-columns: 1fr 1fr;
  }
}

.drill__code {
  color: var(--accent);
}

.drill__date {
  color: var(--term-dim, #8a8a85);
}

.drill__grams {
  font-variant-numeric: tabular-nums;
}

/* --- Log ------------------------------------------------------------------- */
.log {
  margin-block-start: 2.5rem;
  border-block-start: 3px solid var(--term-rule, #2a2a28);
  padding-block-start: 1rem;
}

.log__title {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--term-dim, #8a8a85);
  margin: 0 0 0.75rem;
}

.log__list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.log__row {
  display: grid;
  grid-template-columns: 5rem 7rem 8rem 1fr 8rem 6rem;
  gap: 0.75rem;
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
}

@media (max-width: 62rem) {
  .log__row {
    grid-template-columns: 1fr 1fr;
  }
}

.log__delta {
  font-variant-numeric: tabular-nums;
}

.log__delta--down {
  color: var(--accent);
}

.log__delta--up {
  color: #5c8a3a;
}

.log__code {
  color: var(--term-dim, #8a8a85);
}

.log__reason,
.log__note,
.log__who,
.log__when {
  color: var(--term-dim, #8a8a85);
}

/* --- Modal ----------------------------------------------------------------- */
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
  width: min(34rem, 100%);
  max-height: 90vh;
  overflow-y: auto;
  border: 3px solid var(--term-rule, #2a2a28);
  background-color: var(--term-paper, #1c1c1a);
  box-shadow: 6px 6px 0 #000;
  padding: 1.25rem;
}

.modal__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  padding-block-end: 0.75rem;
  border-block-end: 3px solid var(--term-rule, #2a2a28);
}

.modal__title {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.8125rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  margin: 0;
}

.modal__code {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  color: var(--accent);
}

.modal__now {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  color: var(--term-dim, #8a8a85);
  margin: 0.875rem 0;
}

.modal__now strong {
  color: inherit;
}

.modal__grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.875rem;
}

@media (max-width: 34rem) {
  .modal__grid {
    grid-template-columns: 1fr;
  }
}

.modal__preview {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.8125rem;
  margin: 1.125rem 0 0;
  padding: 0.625rem 0.75rem;
  border: 3px solid var(--term-rule, #2a2a28);
  font-variant-numeric: tabular-nums;
}

/* RTL: the arrow points from the old value to the new one. */
.modal__arrow {
  color: var(--accent);
  margin-inline: 0.5rem;
}

.modal__actions {
  display: flex;
  gap: 0.75rem;
  margin-block-start: 1.25rem;
}
</style>
