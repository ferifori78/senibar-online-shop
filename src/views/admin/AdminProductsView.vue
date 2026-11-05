<script setup>
import { computed, onMounted, ref } from 'vue'

import AdminLayout from '@/components/layout/AdminLayout.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import LoadingState from '@/components/base/LoadingState.vue'
import ProductFormModal from '@/components/admin/ProductFormModal.vue'
import StatusLamp from '@/components/admin/StatusLamp.vue'
import { useAdminStore } from '@/stores/admin'
import { formatNumber, formatPrice, formatWeight } from '@/utils/format'

const admin = useAdminStore()

const editing = ref(null)     // the product being edited
const creating = ref(false)
const confirmDelete = ref(null)
const search = ref('')

const STATUS_LAMP = {
  published: { state: 'ok', label: 'منتشر شده' },
  draft: { state: 'warn', label: 'پیش‌نویس' },
  archived: { state: 'idle', label: 'بایگانی' },
}

const filtered = computed(() => {
  const term = search.value.trim().toLowerCase()
  if (!term) return admin.products
  return admin.products.filter(
    (p) =>
      p.name.toLowerCase().includes(term) || p.origin_country.toLowerCase().includes(term),
  )
})

function onSaved() {
  editing.value = null
  creating.value = false
  admin.fetchProducts()
}

/* --- Shelf order -----------------------------------------------------------
 * Dragging rewrites `sort_order` on the server. Only allowed on the unfiltered
 * list: while a search is active the visible rows are not the real order, so a
 * drop would renumber products against positions the roaster cannot see.
 */
const dragIndex = ref(null)
const overIndex = ref(null)
const reorderError = ref('')

const canReorder = computed(() => !search.value.trim() && !admin.loading)

function onDragStart(index, event) {
  if (!canReorder.value) return
  dragIndex.value = index
  // Firefox does not start a drag unless some data is set.
  event.dataTransfer?.setData('text/plain', String(index))
  if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move'
}

function onDragOver(index) {
  if (dragIndex.value === null) return
  overIndex.value = index
}

function onDragEnd() {
  dragIndex.value = null
  overIndex.value = null
}

async function onDrop() {
  const from = dragIndex.value
  const to = overIndex.value
  onDragEnd()
  if (from === null || to === null || from === to) return

  // Reorder locally first so the row lands under the cursor immediately; the
  // server call then confirms it. On failure the list is re-fetched, which
  // puts everything back the way the server has it.
  const rows = [...admin.products]
  const [moved] = rows.splice(from, 1)
  rows.splice(to, 0, moved)
  admin.products = rows

  reorderError.value = ''
  const { ok } = await admin.reorderProducts(rows.map((p) => p.slug))
  if (!ok) {
    reorderError.value = 'ترتیب ذخیره نشد.'
    admin.fetchProducts()
  }
}

/** What the last delete actually did — erased, or archived and why. */
const outcome = ref('')

async function remove(product) {
  const { ok, erased, detail } = await admin.deleteProduct(product.slug)
  if (!ok) return

  confirmDelete.value = null
  // Archiving is not what the roaster clicked, so it has to be said out loud;
  // an outright delete needs no announcement, the row simply goes.
  outcome.value = erased ? '' : detail || 'این محصول بایگانی شد.'
}

onMounted(() => admin.fetchProducts())
</script>

<template>
  <AdminLayout>
    <div class="bar">
      <input
        v-model="search"
        type="search"
        class="bar__search"
        placeholder="SEARCH — نام یا کشور"
        aria-label="جستجوی محصول"
      />
      <span class="bar__count">{{ formatNumber(filtered.length) }} ITEMS</span>
      <BaseButton variant="primary" size="sm" inverse @click="creating = true">
        + محصول جدید
      </BaseButton>
    </div>

    <!-- Shown when a delete became an archive: the roaster asked for one thing
         and got another, so the difference has to be stated. -->
    <div v-if="outcome" class="outcome" role="status">
      <p class="outcome__text">{{ outcome }}</p>
      <button type="button" class="outcome__close" aria-label="بستن" @click="outcome = ''">×</button>
    </div>

    <p v-if="admin.error" class="err" role="alert">{{ admin.error }}</p>
    <p v-if="reorderError" class="err" role="alert">{{ reorderError }}</p>

    <div class="wrap">
      <table class="tbl tbl-responsive">
        <thead>
          <tr>
            <th scope="col"><span class="sr-only">ترتیب</span></th>
            <th scope="col">نام</th>
            <th scope="col">مبدأ</th>
            <th scope="col">پروسس</th>
            <th scope="col">رست</th>
            <th scope="col" class="tbl__num">قیمت ۲۵۰g</th>
            <th scope="col" class="tbl__num">موجودی</th>
            <th scope="col">وضعیت</th>
            <th scope="col">اکشن</th>
          </tr>
        </thead>

        <tbody>
          <tr v-if="admin.loading && !admin.products.length">
            <td colspan="9" class="tbl__state">
                <LoadingState variant="inline" code="LOADING" inverse />
              </td>
          </tr>

          <tr v-else-if="!filtered.length">
            <td colspan="9" class="tbl__state">
              <EmptyState
                :icon="search ? 'search' : 'bean'"
                :code="search ? 'NO MATCH' : 'NO BEANS IN SIGHT'"
                :message="
                  search
                    ? 'محصولی با این عبارت پیدا نشد.'
                    : 'هنوز محصولی ساخته نشده است. با دکمه بالا اولین قهوه را اضافه کنید.'
                "
                inverse
                compact
              />
            </td>
          </tr>

          <tr
            v-for="(product, index) in filtered"
            v-else
            :key="product.slug"
            class="tbl__row"
            :class="{
              'tbl__row--dragging': dragIndex === index,
              'tbl__row--over': overIndex === index && dragIndex !== index,
            }"
            :draggable="canReorder"
            @dragstart="onDragStart(index, $event)"
            @dragover.prevent="onDragOver(index)"
            @dragend="onDragEnd"
            @drop.prevent="onDrop"
          >
            <td data-label="ترتیب" class="tbl__grip-cell">
              <!-- The handle is only a hint: the whole row is draggable, which
                   is a much larger target than a 12px icon. -->
              <span
                class="tbl__grip"
                :class="{ 'tbl__grip--off': !canReorder }"
                :title="canReorder ? 'برای جابه‌جایی بکشید' : 'برای جابه‌جایی، جست‌وجو را پاک کنید'"
                aria-hidden="true"
              >
                <svg width="10" height="14" viewBox="0 0 10 14" fill="currentColor">
                  <circle cx="2" cy="2" r="1.4" /><circle cx="8" cy="2" r="1.4" />
                  <circle cx="2" cy="7" r="1.4" /><circle cx="8" cy="7" r="1.4" />
                  <circle cx="2" cy="12" r="1.4" /><circle cx="8" cy="12" r="1.4" />
                </svg>
              </span>
            </td>
            <td data-label="نام">
              <span class="tbl__name">{{ product.name }}</span>
              <span v-if="product.subtitle" class="tbl__dim">{{ product.subtitle }}</span>
            </td>
            <td data-label="مبدأ">
              {{ product.origin_country }}
              <span v-if="product.origin_region" class="tbl__dim">{{ product.origin_region }}</span>
            </td>
            <!-- All of them, so a multi-process lot is visible without
                 opening the form. Falls back to the single display value for
                 a product read before the server had the new field. -->
            <td data-label="پروسس" class="tbl__dim-cell">
              {{
                (product.all_processes || []).map((p) => p.label).join('، ') ||
                product.process_display
              }}
            </td>
            <td data-label="رست" class="tbl__dim-cell">
              {{
                (product.all_roast_levels || []).map((r) => r.label).join('، ') ||
                product.roast_level_display
              }}
            </td>
            <td data-label="قیمت ۲۵۰g" class="tbl__num">{{ formatPrice(product.price_per_250g) }}</td>
            <td data-label="موجودی" class="tbl__num">
              <span :class="{ 'tbl__zero': !product.available_grams }">
                {{ formatWeight(product.available_grams || 0) }}
              </span>
            </td>
            <td data-label="وضعیت">
              <StatusLamp
                :state="STATUS_LAMP[product.status]?.state"
                :label="STATUS_LAMP[product.status]?.label"
              />
            </td>
            <td data-label="اکشن" class="tbl__actions">
              <button type="button" class="tbl__action" @click="editing = product">EDIT</button>
              <button
                type="button"
                class="tbl__action tbl__action--danger"
                @click="confirmDelete = product"
              >
                DEL
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Create / edit ------------------------------------------------- -->
    <ProductFormModal
      v-if="creating || editing"
      :product="editing"
      @close="((editing = null), (creating = false))"
      @saved="onSaved"
    />

    <!-- Delete confirmation -------------------------------------------- -->
    <div v-if="confirmDelete" class="scrim" @click.self="confirmDelete = null">
      <div class="confirm" role="alertdialog" aria-modal="true" aria-label="حذف محصول">
        <p class="confirm__text">
          «{{ confirmDelete.name }}» حذف شود؟
        </p>
        <p class="confirm__note">
          اگر سفارش یا بچ رستی به این قهوه وصل باشد، به‌جای پاک شدن بایگانی می‌شود:
          از فروشگاه خارج می‌شود ولی فاکتورهای قبلی مشتری‌ها سالم می‌مانند.
        </p>
        <p v-if="admin.error" class="confirm__err" role="alert">{{ admin.error }}</p>
        <div class="confirm__actions">
          <BaseButton
            variant="danger"
            size="sm"
            inverse
            :loading="admin.acting"
            @click="remove(confirmDelete)"
          >
            حذف کن
          </BaseButton>
          <BaseButton variant="ghost" size="sm" inverse @click="confirmDelete = null">
            انصراف
          </BaseButton>
        </div>
      </div>
    </div>
  </AdminLayout>
</template>

<style scoped>
/* ==========================================================================
   AdminProductsView — Terminal register
   ========================================================================== */

.bar {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
}

/* Notice, not an error: archiving instead of deleting is a correct outcome,
   so it takes the accent rule rather than the red one. */
.outcome {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  border: 3px solid var(--accent);
  padding: 0.75rem 1rem;
  margin-bottom: 1rem;
}

.outcome__text {
  flex: 1;
  margin: 0;
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.75rem;
  line-height: 1.7;
  color: var(--terminal-text);
}

.outcome__close {
  background: none;
  border: 0;
  border-radius: 0;
  color: var(--terminal-dim);
  cursor: pointer;
  font-size: 1.125rem;
  line-height: 1;
  padding: 0;
}

.outcome__close:hover {
  color: var(--accent);
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
  padding: 0.5rem;
  border-bottom: 3px solid var(--terminal-text);
}

.tbl__row {
  border-bottom: 1px solid var(--terminal-rule);
}

.tbl__row:hover {
  background-color: var(--terminal-raised);
}

/* --- Drag to reorder ------------------------------------------------------- */
.tbl__row--dragging {
  opacity: 0.4;
}

/* A hard rule where the row will land — no blur, no animation. */
.tbl__row--over td {
  box-shadow: inset 0 3px 0 var(--accent);
}

.tbl__grip-cell {
  width: 1.75rem;
  text-align: center;
}

.tbl__grip {
  display: inline-block;
  color: var(--terminal-dim);
  cursor: grab;
  line-height: 0;
}

.tbl__row:hover .tbl__grip {
  color: var(--accent);
}

.tbl__grip--off {
  cursor: not-allowed;
  opacity: 0.35;
}

.tbl__row:hover .tbl__grip--off {
  color: var(--terminal-dim);
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
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

.tbl__name {
  display: block;
  font-weight: 500;
}

.tbl__dim {
  display: block;
  font-size: 0.5rem;
  color: var(--terminal-dim);
}

.tbl__dim-cell {
  color: var(--terminal-dim);
}

.tbl__num {
  text-align: end;
}

/* Zero stock is worth noticing without shouting. */
.tbl__zero {
  color: #d4614f;
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

/* --- Confirm --------------------------------------------------------------- */
.scrim {
  position: fixed;
  inset: 0;
  background-color: rgb(0 0 0 / 0.7);
  display: grid;
  place-items: center;
  padding: 1.5rem;
  z-index: 50;
}

.confirm {
  width: 100%;
  max-width: 26rem;
  background-color: var(--terminal);
  color: var(--terminal-text);
  border: 3px solid #a33224;
  box-shadow: 8px 8px 0 #a33224;
  padding: 1.25rem;
}

.confirm__text {
  font-family: var(--font-terminal);
  font-size: 0.8125rem;
  margin: 0 0 0.75rem;
}

.confirm__note {
  font-family: var(--font-terminal);
  font-size: 0.5625rem;
  line-height: 1.7;
  color: var(--terminal-dim);
  margin: 0 0 1.25rem;
}

.confirm__err {
  border: 2px solid #a33224;
  font-family: var(--font-terminal);
  font-size: 0.5625rem;
  line-height: 1.6;
  color: #d4614f;
  padding: 0.5rem;
  margin: 0 0 1rem;
}

.confirm__actions {
  display: flex;
  gap: 0.75rem;
}
</style>
