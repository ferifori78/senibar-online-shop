<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import BaseButton from '@/components/base/BaseButton.vue'
import StatusLamp from '@/components/admin/StatusLamp.vue'
import GrindIcon from '@/components/icons/GrindIcon.vue'
import OrderTimeline from '@/components/orders/OrderTimeline.vue'
import { useAdminStore } from '@/stores/admin'
import {
  GRIND_METHODS,
  PAYMENT_STATUS,
  formatDateTime,
  formatNumber,
  formatPrice,
  formatWeight,
  orderStatusLabel,
} from '@/utils/format'

const props = defineProps({
  orderNumber: { type: String, required: true },
})

const emit = defineEmits(['close', 'updated'])

const admin = useAdminStore()
const note = ref('')
const dialog = ref(null)

const order = computed(() => admin.order)

// Which moves are legal from here. Mirrors ALLOWED_TRANSITIONS on the server,
// which is the real gate — this only keeps the operator from trying.
const TRANSITIONS = {
  pending: ['roasting', 'cancelled'],
  roasting: ['ground', 'packed', 'cancelled'],
  ground: ['packed', 'cancelled'],
  packed: ['shipped', 'cancelled'],
  shipped: ['delivered', 'refunded'],
  delivered: ['refunded'],
  cancelled: [],
  refunded: [],
}

const nextStates = computed(() => TRANSITIONS[order.value?.status] || [])

function grindLabel(value) {
  return GRIND_METHODS.find((m) => m.value === value)?.label || value
}

/** Destructive moves get the danger variant; forward moves get accent. */
function variantFor(status) {
  return ['cancelled', 'refunded'].includes(status) ? 'danger' : 'primary'
}

async function move(status) {
  const { ok } = await admin.setStatus(props.orderNumber, status, note.value)
  if (ok) {
    note.value = ''
    emit('updated')
  }
}

function onKeydown(event) {
  if (event.key === 'Escape') emit('close')
}

onMounted(() => {
  admin.fetchOrder(props.orderNumber)
  document.addEventListener('keydown', onKeydown)
  // Focus the panel so screen readers announce it and Escape works at once.
  requestAnimationFrame(() => dialog.value?.focus())
})

onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown)
  admin.resetErrors()
})

watch(() => props.orderNumber, (n) => n && admin.fetchOrder(n))
</script>

<template>
  <div class="scrim" @click.self="emit('close')">
    <div
      ref="dialog"
      class="modal"
      role="dialog"
      aria-modal="true"
      :aria-label="`سفارش ${orderNumber}`"
      tabindex="-1"
    >
      <header class="modal__head">
        <div class="modal__id">
          <span class="modal__number">{{ orderNumber }}</span>
          <StatusLamp v-if="order" :status="order.status" />
        </div>

        <button type="button" class="modal__close" aria-label="بستن" @click="emit('close')">
          <svg width="14" height="14" viewBox="0 0 14 14" stroke="currentColor" stroke-width="2">
            <path d="M2 2l10 10M12 2L2 12" />
          </svg>
        </button>
      </header>

      <div v-if="admin.loading && !order" class="modal__loading">LOADING…</div>

      <div v-else-if="order" class="modal__body">
        <p v-if="admin.error" class="modal__err" role="alert">{{ admin.error }}</p>

        <div class="modal__cols">
          <!-- Left: the order -->
          <div class="modal__col">
            <section class="block">
              <h3 class="block__title">مشتری</h3>
              <p class="block__line">{{ order.recipient_name }}</p>
              <p class="block__dim">{{ order.recipient_phone }}</p>
              <p class="block__dim">{{ order.province }}، {{ order.city }}</p>
              <p class="block__dim">{{ order.street_address }}</p>
              <p class="block__dim">{{ order.postal_code }}</p>
            </section>

            <section class="block">
              <h3 class="block__title">اقلام</h3>
              <table class="lines">
                <tbody>
                  <tr v-for="item in order.items" :key="item.id">
                    <td class="lines__qty">{{ formatNumber(item.quantity) }}×</td>
                    <td class="lines__name">{{ item.product_name }}</td>
                    <td class="lines__grind">
                      <GrindIcon :method="item.grind_type" :size="14" />
                      {{ grindLabel(item.grind_type) }}
                    </td>
                    <td class="lines__num">{{ formatWeight(item.weight_grams) }}</td>
                    <td class="lines__num">{{ formatPrice(item.line_total) }}</td>
                  </tr>
                </tbody>
              </table>

              <div class="block__total">
                <span>
                  {{ PAYMENT_STATUS[order.payment_status] }} ·
                  {{ formatWeight(order.total_grams) }}
                </span>
                <strong>{{ formatPrice(order.total_amount) }}</strong>
              </div>
            </section>

            <section v-if="order.customer_note" class="block">
              <h3 class="block__title">یادداشت مشتری</h3>
              <p class="block__line">{{ order.customer_note }}</p>
            </section>
          </div>

          <!-- Right: the timeline, in its inverse form -->
          <div class="modal__col">
            <section class="block">
              <h3 class="block__title">وضعیت</h3>
              <OrderTimeline :stages="order.timeline" :order="order" inverse />
            </section>

            <section v-if="order.history?.length" class="block">
              <h3 class="block__title">تاریخچه</h3>
              <ul class="hist">
                <li v-for="h in order.history.slice(-6)" :key="h.id" class="hist__row">
                  <span class="hist__time">{{ formatDateTime(h.created_at) }}</span>
                  <span class="hist__change">
                    {{ orderStatusLabel(h.from_status) }} ← {{ orderStatusLabel(h.to_status) }}
                  </span>
                  <span v-if="h.actor_name" class="hist__who">{{ h.actor_name }}</span>
                </li>
              </ul>
            </section>
          </div>
        </div>
      </div>

      <!-- Actions: the pipeline moves available from here. -->
      <footer v-if="order" class="modal__foot">
        <template v-if="nextStates.length">
          <input
            v-model="note"
            class="modal__note"
            type="text"
            placeholder="یادداشت (اختیاری) — در تاریخچه ثبت می‌شود"
          />
          <div class="modal__actions">
            <BaseButton
              v-for="status in nextStates"
              :key="status"
              :variant="variantFor(status)"
              size="sm"
              inverse
              :disabled="admin.acting"
              @click="move(status)"
            >
              {{ orderStatusLabel(status) }}
            </BaseButton>
          </div>
        </template>

        <p v-else class="modal__done">این سفارش به پایان رسیده است.</p>
      </footer>
    </div>
  </div>
</template>

<style scoped>
/* ==========================================================================
   OrderStatusModal — Terminal register
   ========================================================================== */

.scrim {
  position: fixed;
  inset: 0;
  background-color: rgb(0 0 0 / 0.7);
  display: grid;
  place-items: center;
  padding: 1.5rem;
  z-index: 50;
  overflow-y: auto;
}

.modal {
  width: 100%;
  max-width: 56rem;
  max-height: 90vh;
  overflow-y: auto;
  background-color: var(--terminal);
  color: var(--terminal-text);
  border: 3px solid var(--terminal-text);
  box-shadow: 10px 10px 0 var(--accent);
}

.modal:focus {
  outline: none;
}

/* --- Head ------------------------------------------------------------------ */
.modal__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.875rem 1rem;
  border-bottom: 3px solid var(--terminal-text);
  position: sticky;
  top: 0;
  background-color: var(--terminal);
}

.modal__id {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.modal__number {
  font-family: var(--font-terminal);
  font-size: 0.875rem;
  letter-spacing: 0.08em;
  font-weight: 600;
}

.modal__close {
  display: grid;
  place-items: center;
  width: 1.75rem;
  height: 1.75rem;
  border: 2px solid var(--terminal-text);
  background: none;
  color: var(--terminal-text);
  cursor: pointer;
}

.modal__close:hover {
  background-color: var(--terminal-text);
  color: var(--terminal);
}

.modal__close:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

/* --- Body ------------------------------------------------------------------ */
.modal__loading {
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  color: var(--terminal-dim);
  padding: 3rem;
  text-align: center;
}

.modal__body {
  padding: 1rem;
}

.modal__err {
  border: 3px solid #a33224;
  background-color: #a33224;
  color: var(--paper);
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  padding: 0.625rem 0.75rem;
  margin: 0 0 1rem;
}

.modal__cols {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr);
  gap: 1.5rem;
}

@media (max-width: 48rem) {
  .modal__cols {
    grid-template-columns: 1fr;
  }
}

.block {
  margin-bottom: 1.5rem;
}

.block__title {
  font-family: var(--font-terminal);
  font-size: 0.5625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--terminal-dim);
  font-weight: 500;
  margin: 0 0 0.625rem;
  padding-bottom: 0.4375rem;
  border-bottom: 1px solid var(--terminal-rule);
}

.block__line {
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  line-height: 1.6;
  margin: 0 0 0.25rem;
}

.block__dim {
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  line-height: 1.6;
  color: var(--terminal-dim);
  margin: 0 0 0.1875rem;
}

.block__total {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  margin-top: 0.75rem;
  padding-top: 0.625rem;
  border-top: 3px solid var(--terminal-text);
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  color: var(--terminal-dim);
}

.block__total strong {
  font-size: 0.9375rem;
  color: var(--terminal-text);
}

/* --- Lines ----------------------------------------------------------------- */
.lines {
  width: 100%;
  border-collapse: collapse;
  font-family: var(--font-terminal);
  font-size: 0.625rem;
}

.lines tr {
  border-bottom: 1px solid var(--terminal-rule);
}

.lines td {
  padding: 0.375rem 0.25rem;
  vertical-align: middle;
}

.lines__qty {
  color: var(--terminal-dim);
  white-space: nowrap;
}

.lines__grind {
  white-space: nowrap;
  color: var(--terminal-dim);
}

.lines__grind svg {
  vertical-align: middle;
  margin-inline-end: 0.25rem;
  color: var(--accent);
}

.lines__num {
  text-align: end;
  white-space: nowrap;
}

/* --- History --------------------------------------------------------------- */
.hist {
  list-style: none;
  padding: 0;
  margin: 0;
  font-family: var(--font-terminal);
  font-size: 0.5625rem;
}

.hist__row {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
  padding: 0.375rem 0;
  border-bottom: 1px solid var(--terminal-rule);
}

.hist__time,
.hist__who {
  color: var(--terminal-dim);
}

.hist__change {
  font-size: 0.625rem;
  letter-spacing: 0.06em;
}

/* --- Foot ------------------------------------------------------------------ */
.modal__foot {
  padding: 1rem;
  border-top: 3px solid var(--terminal-text);
  position: sticky;
  bottom: 0;
  background-color: var(--terminal);
}

.modal__note {
  width: 100%;
  border: 3px solid var(--terminal-text);
  background-color: var(--terminal);
  color: var(--terminal-text);
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  padding: 0.5rem 0.625rem;
  margin-bottom: 0.875rem;
}

.modal__note::placeholder {
  color: var(--terminal-dim);
}

.modal__note:focus {
  outline: none;
  box-shadow: 4px 4px 0 var(--accent);
}

.modal__actions {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.modal__done {
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.1em;
  color: var(--terminal-dim);
  margin: 0;
}
</style>
