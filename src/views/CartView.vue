<script setup>
import { onMounted } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import BaseButton from '@/components/base/BaseButton.vue'
import GrindIcon from '@/components/icons/GrindIcon.vue'
import { useCartStore } from '@/stores/cart'
import { GRIND_METHODS, formatNumber, formatPrice, formatWeight } from '@/utils/format'

const cart = useCartStore()
const router = useRouter()

const WEIGHTS = [100, 250, 500, 1000]

function grindLabel(value) {
  return GRIND_METHODS.find((m) => m.value === value)?.label || value
}

function issuesFor(item) {
  return cart.issuesByProduct[item.slug] || []
}

onMounted(() => {
  if (!cart.isEmpty) cart.refreshQuote()
})
</script>

<template>
  <main class="register-editorial cart">
    <header class="cart__header">
      <p class="cart__eyebrow">SENOBAR / CART</p>
      <h1 class="cart__title">سبد خرید</h1>
    </header>

    <!-- Empty ------------------------------------------------------------- -->
    <section v-if="cart.isEmpty" class="cart__empty">
      <p class="cart__empty-text">سبد خرید شما خالی است.</p>
      <RouterLink to="/products">
        <BaseButton variant="primary">دیدن قهوه‌ها</BaseButton>
      </RouterLink>
    </section>

    <div v-else class="cart__layout">
      <!-- Lines ----------------------------------------------------------- -->
      <section class="cart__lines" aria-label="آیتم‌های سبد">
        <p v-if="cart.error" class="cart__error" role="alert">{{ cart.error }}</p>

        <article
          v-for="item in cart.items"
          :key="cart.lineKey(item)"
          class="line"
          :class="{ 'line--flagged': issuesFor(item).length }"
        >
          <RouterLink :to="`/products/${item.slug}`" class="line__plate">
            <img v-if="item.image" :src="item.image" :alt="item.name" class="line__image" />
            <div v-else class="line__placeholder" aria-hidden="true">
              <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.5">
                <ellipse cx="24" cy="24" rx="13" ry="18" transform="rotate(-35 24 24)" />
                <path d="M15 33C20 28 28 20 33 15" />
              </svg>
            </div>
          </RouterLink>

          <div class="line__body">
            <div class="line__head">
              <div>
                <RouterLink :to="`/products/${item.slug}`" class="line__name">
                  {{ item.name }}
                </RouterLink>
                <p class="line__origin">{{ item.origin }}</p>
              </div>

              <button
                type="button"
                class="line__remove"
                :aria-label="`حذف ${item.name}`"
                @click="cart.remove(cart.lineKey(item))"
              >
                <svg width="16" height="16" viewBox="0 0 16 16" stroke="currentColor" stroke-width="2">
                  <path d="M3 3l10 10M13 3L3 13" />
                </svg>
              </button>
            </div>

            <!-- Weight: square segmented control, accent marks the choice. -->
            <div class="line__control">
              <span class="line__control-label">وزن</span>
              <div class="line__weights" role="radiogroup" :aria-label="`وزن ${item.name}`">
                <button
                  v-for="w in WEIGHTS"
                  :key="w"
                  type="button"
                  role="radio"
                  class="line__weight"
                  :class="{ 'line__weight--on': w === item.weight_grams }"
                  :aria-checked="w === item.weight_grams"
                  @click="cart.setWeight(cart.lineKey(item), w)"
                >
                  {{ formatWeight(w) }}
                </button>
              </div>
            </div>

            <!-- Grind: shown as its icon; changing it goes back to the product. -->
            <div class="line__control">
              <span class="line__control-label">آسیاب</span>
              <span class="line__grind">
                <GrindIcon :method="item.grind_type" :size="18" />
                {{ grindLabel(item.grind_type) }}
              </span>
            </div>

            <p v-for="issue in issuesFor(item)" :key="issue.code" class="line__issue" role="alert">
              {{ issue.detail }}
            </p>

            <div class="line__foot">
              <div class="line__stepper">
                <button
                  type="button"
                  class="line__step"
                  aria-label="کاهش"
                  @click="cart.setQuantity(cart.lineKey(item), item.quantity - 1)"
                >
                  <svg width="12" height="12" viewBox="0 0 12 12" stroke="currentColor" stroke-width="2">
                    <path d="M2 6h8" />
                  </svg>
                </button>
                <span class="line__qty" aria-live="polite">{{ formatNumber(item.quantity) }}</span>
                <button
                  type="button"
                  class="line__step"
                  aria-label="افزایش"
                  :disabled="item.quantity >= 20"
                  @click="cart.setQuantity(cart.lineKey(item), item.quantity + 1)"
                >
                  <svg width="12" height="12" viewBox="0 0 12 12" stroke="currentColor" stroke-width="2">
                    <path d="M2 6h8M6 2v8" />
                  </svg>
                </button>
              </div>

              <span class="line__total">{{ formatPrice(item.unit_price * item.quantity) }}</span>
            </div>
          </div>
        </article>

        <button type="button" class="cart__clear" @click="cart.clear()">خالی کردن سبد</button>
      </section>

      <!-- Summary --------------------------------------------------------- -->
      <aside class="summary" aria-label="خلاصه سفارش">
        <h2 class="summary__title">خلاصه</h2>

        <dl class="summary__rows">
          <div class="summary__row">
            <dt>جمع اقلام</dt>
            <dd>{{ formatPrice(cart.subtotal) }}</dd>
          </div>
          <div class="summary__row">
            <dt>وزن کل</dt>
            <dd>{{ formatWeight(cart.totalGrams) }}</dd>
          </div>
          <div v-if="cart.quote" class="summary__row">
            <dt>ارسال</dt>
            <dd>{{ cart.shippingCost ? formatPrice(cart.shippingCost) : 'رایگان' }}</dd>
          </div>
        </dl>

        <div class="summary__rule" aria-hidden="true" />

        <div class="summary__total">
          <span>مبلغ قابل پرداخت</span>
          <strong>{{ formatPrice(cart.total) }}</strong>
        </div>

        <p v-if="cart.quoteLoading" class="summary__note">در حال محاسبه…</p>
        <p v-else-if="cart.issues.length" class="summary__warn" role="alert">
          برای ادامه، موارد مشخص‌شده را اصلاح کنید.
        </p>

        <BaseButton
          variant="primary"
          size="lg"
          block
          :disabled="!cart.canCheckout || cart.quoteLoading"
          @click="router.push('/checkout')"
        >
          ادامه و تسویه
        </BaseButton>

        <RouterLink to="/products" class="summary__back">ادامه خرید</RouterLink>
      </aside>
    </div>
  </main>
</template>

<style scoped>
/* ==========================================================================
   CartView — Editorial register
   ========================================================================== */

.cart {
  padding: clamp(2rem, 6vw, 4rem) clamp(1.25rem, 5vw, 4rem) 6rem;
}

.cart__eyebrow {
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
  margin: 0;
}

.cart__title {
  font-family: var(--font-editorial);
  font-size: clamp(2.25rem, 7vw, 3.5rem);
  line-height: 1.1;
  font-weight: 600;
  margin: 0.75rem 0 0;
}

/* --- Empty ----------------------------------------------------------------- */
.cart__empty {
  margin-top: 4rem;
  padding-top: 3rem;
  border-top: 3px solid var(--divider);
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 1.75rem;
}

.cart__empty-text {
  font-family: var(--font-editorial);
  font-size: 1.25rem;
  color: var(--ink-muted);
  margin: 0;
}

/* --- Layout ---------------------------------------------------------------- */
.cart__layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 21rem;
  gap: clamp(2rem, 4vw, 3.5rem);
  align-items: start;
  margin-top: 3rem;
  padding-top: 2.5rem;
  border-top: 3px solid var(--divider);
}

@media (max-width: 56rem) {
  .cart__layout {
    grid-template-columns: 1fr;
  }
}

.cart__error {
  border: 3px solid #a33224;
  background-color: #a33224;
  color: var(--paper);
  font-family: var(--font-terminal);
  font-size: 0.75rem;
  padding: 0.75rem 0.875rem;
  margin: 0 0 1.5rem;
}

/* --- Line ------------------------------------------------------------------ */
.line {
  display: grid;
  grid-template-columns: 7rem minmax(0, 1fr);
  gap: 1.25rem;
  border: 3px solid var(--ink);
  padding: 1rem;
  margin-bottom: 1.5rem;
}

.line--flagged {
  border-color: #a33224;
}

@media (max-width: 34rem) {
  .line {
    grid-template-columns: 4.5rem minmax(0, 1fr);
    gap: 0.875rem;
  }
}

.line__plate {
  aspect-ratio: 1;
  border: 3px solid var(--ink);
  background-color: var(--paper-sunk);
  overflow: hidden;
  display: block;
}

.line__image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.line__placeholder {
  width: 100%;
  height: 100%;
  display: grid;
  place-items: center;
  color: var(--rule);
}
.line__placeholder svg {
  width: 45%;
  height: 45%;
}

.line__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.line__name {
  font-family: var(--font-editorial);
  font-size: 1.1875rem;
  font-weight: 600;
  color: var(--ink);
  text-decoration: none;
}
.line__name:hover {
  border-bottom: 2px solid var(--accent);
}

.line__origin {
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
  margin: 0.25rem 0 0;
}

.line__remove {
  display: grid;
  place-items: center;
  width: 1.75rem;
  height: 1.75rem;
  border: 3px solid var(--ink);
  background-color: var(--paper);
  color: var(--ink);
  cursor: pointer;
  flex: none;
}
.line__remove:hover {
  background-color: #a33224;
  border-color: #a33224;
  color: var(--paper);
}
.line__remove:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: 2px;
}

/* --- Controls -------------------------------------------------------------- */
.line__control {
  display: flex;
  align-items: center;
  gap: 0.875rem;
  flex-wrap: wrap;
  margin-top: 0.875rem;
}

.line__control-label {
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
  min-width: 2.5rem;
}

.line__weights {
  display: flex;
  border: 3px solid var(--ink);
}

.line__weight {
  border: 0;
  border-inline-end: 3px solid var(--ink);
  background-color: var(--paper);
  color: var(--ink);
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.06em;
  padding: 0.3125rem 0.5rem;
  cursor: pointer;
}
.line__weight:last-child {
  border-inline-end: 0;
}
.line__weight--on {
  background-color: var(--accent);
  color: var(--paper);
}
.line__weight:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: -3px;
}

.line__grind {
  display: inline-flex;
  align-items: center;
  gap: 0.4375rem;
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  letter-spacing: 0.06em;
}

.line__issue {
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  line-height: 1.6;
  color: #a33224;
  margin: 0.75rem 0 0;
}

/* --- Foot ------------------------------------------------------------------ */
.line__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-top: 1.125rem;
  padding-top: 0.875rem;
  border-top: 1px solid var(--rule);
}

.line__stepper {
  display: inline-flex;
  border: 3px solid var(--ink);
}

.line__step {
  display: grid;
  place-items: center;
  width: 1.875rem;
  border: 0;
  background-color: var(--paper);
  color: var(--ink);
  cursor: pointer;
}
.line__step:hover:not(:disabled) {
  background-color: var(--ink);
  color: var(--paper);
}
.line__step:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.line__qty {
  display: grid;
  place-items: center;
  min-width: 2.25rem;
  border-inline: 3px solid var(--ink);
  font-family: var(--font-terminal);
  font-size: 0.8125rem;
}

.line__total {
  font-family: var(--font-editorial);
  font-size: 1.125rem;
  font-weight: 600;
}

.cart__clear {
  border: 0;
  background: none;
  padding: 0;
  color: var(--ink-muted);
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  cursor: pointer;
  border-bottom: 2px solid var(--rule);
}
.cart__clear:hover {
  color: #a33224;
  border-bottom-color: #a33224;
}

/* --- Summary --------------------------------------------------------------- */
.summary {
  border: 3px solid var(--ink);
  box-shadow: 8px 8px 0 var(--shadow);
  padding: 1.5rem;
  position: sticky;
  top: 2rem;
}

.summary__title {
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-weight: 500;
  margin: 0 0 1.25rem;
  padding-bottom: 0.75rem;
  border-bottom: 3px solid var(--ink);
}

.summary__rows {
  margin: 0;
}

.summary__row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.5rem 0;
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  letter-spacing: 0.06em;
}

.summary__row dt {
  color: var(--ink-muted);
  text-transform: uppercase;
  font-size: 0.625rem;
  letter-spacing: 0.14em;
}

.summary__row dd {
  margin: 0;
}

.summary__rule {
  height: 3px;
  background-color: var(--ink);
  margin: 1rem 0;
}

.summary__total {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.summary__total span {
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
}

.summary__total strong {
  font-family: var(--font-editorial);
  font-size: 1.375rem;
  font-weight: 600;
}

.summary__note,
.summary__warn {
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.06em;
  line-height: 1.6;
  margin: 0 0 1rem;
}
.summary__note {
  color: var(--ink-muted);
}
.summary__warn {
  color: #a33224;
}

.summary__back {
  display: block;
  text-align: center;
  margin-top: 1rem;
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
  text-decoration: none;
}
.summary__back:hover {
  color: var(--ink);
}
</style>
