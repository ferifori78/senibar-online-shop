<script setup>
import { onMounted, reactive, ref } from 'vue'

import AdminLayout from '@/components/layout/AdminLayout.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import LoadingState from '@/components/base/LoadingState.vue'
import StatusLamp from '@/components/admin/StatusLamp.vue'
import { blankMethod, useSettingsStore } from '@/stores/settings'
import { formatNumber, formatPrice } from '@/utils/format'

const settings = useSettingsStore()

// null = closed. 'new' = adding. A number = editing that method.
const editing = ref(null)
const confirmingDelete = ref(null)
const form = reactive(blankMethod())

function openNew() {
  editing.value = 'new'
  Object.assign(form, blankMethod())
  settings.resetErrors()
}

function openEdit(method) {
  editing.value = method.id
  Object.assign(form, {
    key: method.key,
    label: method.label,
    description: method.description || '',
    days: method.days || '',
    cost: Number(method.cost),
    free_over: method.free_over === null ? null : Number(method.free_over),
    is_active: method.is_active,
    sort_order: method.sort_order,
  })
  settings.resetErrors()
}

function closeForm() {
  editing.value = null
  settings.resetErrors()
}

async function submit() {
  const payload = { ...form }
  // An empty threshold means "never free", which the API takes as null rather
  // than zero — zero would make every order ship free.
  if (payload.free_over === '' || payload.free_over === undefined) {
    payload.free_over = null
  }
  // The key identifies the method on existing orders and is read-only on
  // update; sending it back would be rejected.
  if (editing.value !== 'new') delete payload.key

  const { ok } = await settings.saveMethod(payload, editing.value === 'new' ? null : editing.value)
  if (ok) closeForm()
}

async function confirmDelete() {
  const { ok } = await settings.deleteMethod(confirmingDelete.value.id)
  if (ok) confirmingDelete.value = null
}

function errorFor(field) {
  return settings.fieldErrors[field] || ''
}

async function toggleGateway(gateway) {
  await settings.setGatewayEnabled(gateway.name, !gateway.is_enabled)
}

onMounted(() => settings.fetchAll())
</script>

<template>
  <AdminLayout>
    <div class="bar">
      <h1 class="bar__title">SETTINGS</h1>
    </div>

    <p v-if="settings.error && !editing" class="err" role="alert">{{ settings.error }}</p>

    <LoadingState
      v-if="settings.loading && !settings.gateways.length"
      variant="rows"
      code="READING CONFIG"
      :count="4"
      inverse
    />

    <template v-else>
      <!-- --- Gateways ----------------------------------------------------- -->
      <section class="sec" aria-labelledby="gw-title">
        <h2 id="gw-title" class="sec__title">PAYMENT GATEWAYS</h2>
        <p class="sec__note">
          کلیدهای درگاه در فایل .env روی سرور نگهداری می‌شوند و از اینجا قابل
          دیدن یا تغییر نیستند. این صفحه فقط تعیین می‌کند کدام درگاه در تسویه به
          مشتری نشان داده شود.
        </p>

        <div class="wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th scope="col">درگاه</th>
                <th scope="col">وضعیت</th>
                <th scope="col">کلید</th>
                <th scope="col">پرداخت موفق</th>
                <th scope="col">اکشن</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="gw in settings.gateways" :key="gw.name" class="tbl__row">
                <td data-label="درگاه">
                  <span class="gw__label">{{ gw.label }}</span>
                  <span class="gw__name">{{ gw.name }}</span>
                </td>

                <td data-label="وضعیت">
                  <StatusLamp
                    :state="gw.is_live ? 'ok' : gw.is_enabled ? 'warn' : 'idle'"
                    :label="gw.is_live ? 'فعال' : gw.is_enabled ? 'بدون کلید' : 'خاموش'"
                  />
                </td>

                <td data-label="کلید">
                  <span v-if="gw.is_configured" class="dim">تنظیم شده</span>
                  <span v-else class="warn">{{ gw.problem || 'تنظیم نشده' }}</span>
                </td>

                <td data-label="پرداخت موفق" class="tbl__num dim">
                  {{ formatNumber(gw.paid_count) }}
                </td>

                <td data-label="اکشن">
                  <button
                    type="button"
                    class="tbl__action"
                    :class="{ 'tbl__action--danger': gw.is_enabled }"
                    :disabled="settings.acting"
                    @click="toggleGateway(gw)"
                  >
                    {{ gw.is_enabled ? 'خاموش کن' : 'روشن کن' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <p v-if="!settings.liveGateways.length" class="alarm" role="alert">
          هیچ درگاه فعالی وجود ندارد — مشتری نمی‌تواند سفارشی را پرداخت کند.
        </p>
      </section>

      <!-- --- Shipping ----------------------------------------------------- -->
      <section class="sec" aria-labelledby="sm-title">
        <div class="sec__head">
          <h2 id="sm-title" class="sec__title">SHIPPING METHODS</h2>
          <BaseButton v-if="!editing" variant="primary" size="sm" inverse @click="openNew">
            + روش جدید
          </BaseButton>
        </div>

        <form v-if="editing" class="new" novalidate @submit.prevent="submit">
          <p class="new__mode">
            {{ editing === 'new' ? 'روش ارسال جدید' : `ویرایش ${form.label}` }}
          </p>

          <div class="new__grid">
            <label class="f">
              <span class="f__label">
                شناسه<i v-if="editing === 'new'">*</i>
              </span>
              <input
                v-model="form.key"
                class="f__input"
                :class="{ 'f__input--err': errorFor('key') }"
                :disabled="editing !== 'new'"
                placeholder="standard"
              />
              <span class="f__hint">
                {{ editing === 'new'
                  ? 'لاتین و بدون فاصله. روی سفارش‌ها ذخیره می‌شود.'
                  : 'قابل تغییر نیست — سفارش‌های ثبت‌شده به آن ارجاع می‌دهند.' }}
              </span>
              <span v-if="errorFor('key')" class="f__err">{{ errorFor('key') }}</span>
            </label>

            <label class="f">
              <span class="f__label">نام<i>*</i></span>
              <input
                v-model="form.label"
                class="f__input"
                :class="{ 'f__input--err': errorFor('label') }"
                placeholder="پست پیشتاز"
              />
              <span v-if="errorFor('label')" class="f__err">{{ errorFor('label') }}</span>
            </label>

            <label class="f">
              <span class="f__label">مدت</span>
              <input v-model="form.days" class="f__input" placeholder="۳ تا ۵ روز کاری" />
            </label>

            <label class="f">
              <span class="f__label">هزینه (ریال)<i>*</i></span>
              <input
                v-digits
                v-model.number="form.cost"
                type="number"
                min="0"
                class="f__input"
                :class="{ 'f__input--err': errorFor('cost') }"
              />
              <span v-if="form.cost > 0" class="f__hint">= {{ formatPrice(form.cost) }}</span>
              <span v-if="errorFor('cost')" class="f__err">{{ errorFor('cost') }}</span>
            </label>

            <label class="f">
              <span class="f__label">رایگان بالای (ریال)</span>
              <input
                v-digits
                v-model.number="form.free_over"
                type="number"
                min="0"
                class="f__input"
                :class="{ 'f__input--err': errorFor('free_over') }"
              />
              <span class="f__hint">
                {{ form.free_over > 0 ? `= ${formatPrice(form.free_over)}` : 'خالی یعنی هیچ‌وقت رایگان نمی‌شود' }}
              </span>
              <span v-if="errorFor('free_over')" class="f__err">{{ errorFor('free_over') }}</span>
            </label>

            <label class="f">
              <span class="f__label">ترتیب نمایش</span>
              <input v-digits v-model.number="form.sort_order" type="number" min="0" class="f__input" />
            </label>

            <label class="f f--full">
              <span class="f__label">توضیح</span>
              <input v-model="form.description" class="f__input" />
            </label>
          </div>

          <label class="check">
            <input v-model="form.is_active" type="checkbox" />
            <span class="check__box" aria-hidden="true" />
            <span class="check__label">در تسویه‌حساب نمایش داده شود</span>
          </label>

          <p v-if="settings.error" class="err" role="alert">{{ settings.error }}</p>

          <div class="new__actions">
            <BaseButton type="submit" variant="primary" size="sm" inverse :loading="settings.acting">
              {{ editing === 'new' ? 'ثبت روش' : 'ذخیره تغییرات' }}
            </BaseButton>
            <BaseButton type="button" variant="ghost" size="sm" inverse @click="closeForm">
              انصراف
            </BaseButton>
          </div>
        </form>

        <div class="wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th scope="col">روش</th>
                <th scope="col">وضعیت</th>
                <th scope="col">هزینه</th>
                <th scope="col">رایگان بالای</th>
                <th scope="col">سفارش</th>
                <th scope="col">اکشن</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="m in settings.methods" :key="m.id" class="tbl__row">
                <td data-label="روش">
                  <span class="gw__label">{{ m.label }}</span>
                  <span class="gw__name">{{ m.key }} · {{ m.days }}</span>
                </td>
                <td data-label="وضعیت">
                  <StatusLamp
                    :state="m.is_active ? 'ok' : 'idle'"
                    :label="m.is_active ? 'فعال' : 'غیرفعال'"
                  />
                </td>
                <td data-label="هزینه" class="tbl__num">{{ formatPrice(m.cost) }}</td>
                <td data-label="رایگان بالای" class="tbl__num dim">
                  {{ m.free_over ? formatPrice(m.free_over) : '—' }}
                </td>
                <td data-label="سفارش" class="tbl__num dim">
                  {{ formatNumber(m.order_count ?? 0) }}
                </td>
                <td data-label="اکشن">
                  <div class="tbl__actions">
                    <button type="button" class="tbl__action" @click="openEdit(m)">EDIT</button>
                    <button
                      type="button"
                      class="tbl__action"
                      :disabled="settings.acting"
                      @click="settings.saveMethod({ is_active: !m.is_active }, m.id)"
                    >
                      {{ m.is_active ? 'غیرفعال' : 'فعال' }}
                    </button>
                    <button
                      type="button"
                      class="tbl__action tbl__action--danger"
                      @click="confirmingDelete = m"
                    >
                      DELETE
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>

    <!-- --- Delete confirmation -------------------------------------------- -->
    <div
      v-if="confirmingDelete"
      class="modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="del-title"
    >
      <div class="modal__panel">
        <h2 id="del-title" class="modal__title">حذف روش ارسال</h2>
        <p class="modal__body">
          روش <strong>{{ confirmingDelete.label }}</strong> حذف شود؟ اگر سفارشی
          از آن استفاده کرده باشد، سرور حذف را رد می‌کند و باید به‌جای آن
          غیرفعالش کنید.
        </p>

        <p v-if="settings.error" class="err" role="alert">{{ settings.error }}</p>

        <div class="modal__actions">
          <BaseButton variant="primary" size="sm" inverse :loading="settings.acting" @click="confirmDelete">
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
   AdminSettingsView — Terminal register
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

.err {
  border: 3px solid #a33224;
  background-color: #a33224;
  color: #f4f1ea;
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.75rem;
  padding: 0.625rem 0.75rem;
  margin-block: 1rem;
}

.alarm {
  border: 3px solid #a33224;
  color: #e0745f;
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.75rem;
  padding: 0.625rem 0.75rem;
  margin-block-start: 1rem;
}

/* --- Sections -------------------------------------------------------------- */
.sec {
  margin-block-start: 2.5rem;
}

.sec:first-of-type {
  margin-block-start: 0;
}

.sec__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.sec__title {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.75rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  margin: 0 0 0.625rem;
}

.sec__note {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  line-height: 1.9;
  color: var(--term-dim, #8a8a85);
  max-width: 46rem;
  margin: 0 0 1.25rem;
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

.dim {
  color: var(--term-dim, #8a8a85);
}

.warn {
  color: #d19a2a;
}

.gw__label {
  display: block;
}

.gw__name {
  display: block;
  font-size: 0.625rem;
  color: var(--term-dim, #8a8a85);
  margin-block-start: 0.1875rem;
}

.tbl__actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
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

.tbl__action:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: 2px;
}

/* --- Form ------------------------------------------------------------------ */
.new {
  border: 3px solid var(--term-rule, #2a2a28);
  padding: 1.25rem;
  margin-block-end: 1.5rem;
}

.new__mode {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent);
  margin: 0 0 1rem;
}

.new__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
  gap: 0.875rem;
}

.new__actions {
  display: flex;
  gap: 0.75rem;
  margin-block-start: 1.25rem;
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

.f__label i {
  color: var(--accent);
  font-style: normal;
  margin-inline-start: 0.25rem;
}

.f__input {
  border: 3px solid var(--term-rule, #2a2a28);
  border-radius: 0;
  background-color: var(--term-sunk, #171715);
  color: inherit;
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.75rem;
  padding: 0.4375rem 0.5625rem;
  width: 100%;
}

.f__input:focus {
  outline: none;
  box-shadow: 3px 3px 0 var(--accent);
}

.f__input:disabled {
  opacity: 0.5;
}

.f__input--err {
  border-color: #a33224;
}

.f__hint {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.5625rem;
  color: var(--term-dim, #8a8a85);
}

.f__err {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.5625rem;
  color: #e0745f;
}

.check {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  margin-block-start: 1rem;
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
  width: 1rem;
  height: 1rem;
  border: 3px solid var(--term-rule, #2a2a28);
  background-color: var(--term-sunk, #171715);
}

.check input:checked + .check__box {
  background-color: var(--accent);
  border-color: var(--accent);
}

.check input:focus-visible + .check__box {
  outline: 3px solid var(--accent);
  outline-offset: 2px;
}

.check__label {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
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
  width: min(30rem, 100%);
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
  line-height: 1.9;
  color: var(--term-dim, #8a8a85);
  margin: 0;
}

.modal__actions {
  display: flex;
  gap: 0.75rem;
  margin-block-start: 1.25rem;
}
</style>
