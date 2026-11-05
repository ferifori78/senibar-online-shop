<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import BaseButton from '@/components/base/BaseButton.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import ordersApi, { paymentsApi } from '@/api/orders'
import { parseApiError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useAddressStore } from '@/stores/addresses'
import { useCartStore } from '@/stores/cart'
import { GRIND_METHODS, formatPrice, formatWeight } from '@/utils/format'

const cart = useCartStore()
const auth = useAuthStore()
const addressStore = useAddressStore()
const router = useRouter()

const form = reactive({
  recipient_name: '',
  recipient_phone: '',
  province: '',
  city: '',
  street_address: '',
  postal_code: '',
  customer_note: '',
})

const savedAddressId = ref(null)
// Which gateway the customer picked. Empty means "whatever the shop defaults
// to", which is what the API assumes when no gateway is sent.
// Offer to keep a hand-typed address, so the next order can just pick it.
const saveAddress = ref(true)
const gateway = ref('')
const gateways = ref([])
const submitting = ref(false)
const error = ref('')
const fieldErrors = ref({})

// From the store, not the login-time profile snapshot: an address added on
// the account page must appear here without a reload.
const addresses = computed(() =>
  addressStore.addresses.length ? addressStore.addresses : auth.user?.addresses || [],
)

function grindLabel(value) {
  return GRIND_METHODS.find((m) => m.value === value)?.label || value
}

/** Picking a saved address fills the form; "new address" clears it. */
function useAddress(address) {
  savedAddressId.value = address?.id ?? null
  if (!address) return
  form.recipient_name = address.recipient_name
  form.recipient_phone = address.phone
  form.province = address.province
  form.city = address.city
  form.street_address = address.street_address
  form.postal_code = address.postal_code
}

function validate() {
  const errors = {}
  const required = {
    recipient_name: 'نام گیرنده لازم است.',
    recipient_phone: 'شماره تماس لازم است.',
    province: 'استان لازم است.',
    city: 'شهر لازم است.',
    street_address: 'نشانی لازم است.',
    postal_code: 'کد پستی لازم است.',
  }

  for (const [field, message] of Object.entries(required)) {
    if (!form[field]?.trim()) errors[field] = message
  }
  if (form.postal_code && !/^\d{10}$/.test(form.postal_code.trim())) {
    errors.postal_code = 'کد پستی باید ۱۰ رقم باشد.'
  }
  if (form.recipient_phone && !/^0\d{10}$/.test(form.recipient_phone.trim())) {
    errors.recipient_phone = 'شماره تماس باید ۱۱ رقم و با ۰ شروع شود.'
  }

  fieldErrors.value = errors
  return Object.keys(errors).length === 0
}

/** Create the order, then open a gateway transaction and hand off. */
async function submit() {
  error.value = ''
  if (!validate()) return
  if (!cart.canCheckout) {
    error.value = 'سبد خرید قابل ثبت نیست. موارد مشخص‌شده را اصلاح کنید.'
    return
  }

  submitting.value = true
  try {
    const payload = {
      items: cart.items.map((i) => ({
        product: i.product_id,
        weight_grams: i.weight_grams,
        grind_type: i.grind_type,
        quantity: i.quantity,
      })),
      shipping_method: cart.shippingMethod,
      customer_note: form.customer_note,
      ...(savedAddressId.value
        ? { address_id: savedAddressId.value }
        : {
            recipient_name: form.recipient_name,
            recipient_phone: form.recipient_phone,
            province: form.province,
            city: form.city,
            street_address: form.street_address,
            postal_code: form.postal_code,
          }),
    }

    const { data: order } = await ordersApi.create(payload)

    // Only once the order is accepted: a rejected checkout should not leave a
    // stray address in the customer's account.
    if (savedAddressId.value === null && saveAddress.value) {
      // Failure here is not worth blocking the payment for — the order is
      // placed either way, and the address is a convenience.
      addressStore
        .save({
          label: '',
          recipient_name: form.recipient_name,
          phone: form.recipient_phone,
          province: form.province,
          city: form.city,
          street_address: form.street_address,
          postal_code: form.postal_code,
          is_default: addressStore.addresses.length === 0,
        })
        .catch(() => {})
    }

    // Remember the order so the callback page can recover if the gateway
    // returns the customer without a usable session.
    sessionStorage.setItem('senobar.pending_order', order.number)

    const { data: payment } = await paymentsApi.request({
      order_number: order.number,
      ...(gateway.value ? { gateway: gateway.value } : {}),
    })
    window.location.assign(payment.redirect_url)
  } catch (err) {
    const parsed = parseApiError(err)
    error.value = parsed.message || 'ثبت سفارش ناموفق بود.'
    fieldErrors.value = { ...fieldErrors.value, ...parsed.fields }
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  if (cart.isEmpty) {
    router.replace('/cart')
    return
  }
  await cart.refreshQuote()
  await addressStore.fetchAddresses()

  // The picker is only worth showing when there is a choice to make.
  try {
    const { data } = await paymentsApi.gateways()
    gateways.value = data.gateways || []
    gateway.value = data.default && gateways.value.some((g) => g.name === data.default)
      ? data.default
      : gateways.value[0]?.name || ''
  } catch {
    // Not fatal: sending no gateway lets the server use its own default.
    gateways.value = []
  }

  // Prefill from the default saved address, falling back to the profile.
  const preferred = addresses.value.find((a) => a.is_default) || addresses.value[0]
  if (preferred) {
    useAddress(preferred)
  } else if (auth.user) {
    form.recipient_name = auth.user.display_name || ''
    form.recipient_phone = auth.user.phone || ''
  }
})
</script>

<template>
  <main class="register-editorial checkout">
    <header class="checkout__header">
      <p class="checkout__eyebrow">SENOBAR / CHECKOUT</p>
      <h1 class="checkout__title">تسویه حساب</h1>
    </header>

    <form class="checkout__layout" novalidate @submit.prevent="submit">
      <!-- Address + shipping -------------------------------------------- -->
      <div class="checkout__main">
        <p v-if="error" class="checkout__error" role="alert">{{ error }}</p>

        <!-- Saved addresses -->
        <section v-if="addresses.length" class="checkout__section">
          <h2 class="checkout__section-title">آدرس‌های ذخیره‌شده</h2>
          <div class="checkout__addresses">
            <button
              v-for="address in addresses"
              :key="address.id"
              type="button"
              class="addr"
              :class="{ 'addr--on': savedAddressId === address.id }"
              :aria-pressed="savedAddressId === address.id"
              @click="useAddress(address)"
            >
              <span class="addr__name">{{ address.recipient_name }}</span>
              <span class="addr__text">{{ address.city }} — {{ address.street_address }}</span>
            </button>

            <button
              type="button"
              class="addr addr--new"
              :class="{ 'addr--on': savedAddressId === null }"
              :aria-pressed="savedAddressId === null"
              @click="useAddress(null)"
            >
              <span class="addr__name">آدرس جدید</span>
            </button>
          </div>

          <RouterLink to="/account" class="checkout__manage">
            مدیریت آدرس‌ها در حساب من
          </RouterLink>
        </section>

        <!-- Address form -->
        <section class="checkout__section">
          <h2 class="checkout__section-title">نشانی ارسال</h2>

          <div class="checkout__grid">
            <BaseInput
              v-model="form.recipient_name"
              label="نام گیرنده"
              autocomplete="name"
              :error="fieldErrors.recipient_name"
              required
            />
            <BaseInput
              v-model="form.recipient_phone"
              label="شماره تماس"
              type="tel"
              inputmode="tel"
              digits="strict"
              autocomplete="tel"
              placeholder="09xxxxxxxxx"
              :error="fieldErrors.recipient_phone"
              required
            />
            <BaseInput
              v-model="form.province"
              label="استان"
              :error="fieldErrors.province"
              required
            />
            <BaseInput v-model="form.city" label="شهر" :error="fieldErrors.city" required />
          </div>

          <div class="checkout__stack">
            <BaseInput
              v-model="form.street_address"
              label="نشانی کامل"
              digits="loose"
              autocomplete="street-address"
              :error="fieldErrors.street_address"
              required
            />
            <BaseInput
              v-model="form.postal_code"
              label="کد پستی"
              inputmode="numeric"
              digits="strict"
              autocomplete="postal-code"
              hint="۱۰ رقم، بدون خط تیره"
              :error="fieldErrors.postal_code"
              required
            />
            <BaseInput v-model="form.customer_note" label="یادداشت سفارش" />
          </div>
        </section>

        <label v-if="savedAddressId === null" class="keep">
          <input v-model="saveAddress" type="checkbox" />
          <span class="keep__box" aria-hidden="true" />
          <span class="keep__label">این نشانی را در حساب من ذخیره کن</span>
        </label>

        <!-- Shipping method -->
        <section class="checkout__section">
          <h2 class="checkout__section-title">روش ارسال</h2>

          <div class="ship" role="radiogroup" aria-label="روش ارسال">
            <button
              v-for="option in cart.shippingOptions"
              :key="option.value"
              type="button"
              role="radio"
              class="ship__option"
              :class="{ 'ship__option--on': cart.shippingMethod === option.value }"
              :aria-checked="cart.shippingMethod === option.value"
              @click="cart.setShippingMethod(option.value)"
            >
              <span class="ship__mark" aria-hidden="true" />
              <span class="ship__body">
                <span class="ship__label">{{ option.label }}</span>
                <span class="ship__desc">{{ option.description }}</span>
                <span class="ship__days">{{ option.days }}</span>
              </span>
              <span class="ship__cost">
                {{ Number(option.cost) === 0 ? 'رایگان' : formatPrice(option.cost) }}
              </span>
            </button>
          </div>
        </section>
      </div>

      <!-- Summary -------------------------------------------------------- -->
      <aside class="checkout__summary" aria-label="خلاصه سفارش">
        <h2 class="checkout__section-title">سفارش شما</h2>

        <ul class="mini">
          <li v-for="item in cart.items" :key="cart.lineKey(item)" class="mini__row">
            <span class="mini__qty">{{ item.quantity }}×</span>
            <span class="mini__body">
              <span class="mini__name">{{ item.name }}</span>
              <span class="mini__meta">
                {{ formatWeight(item.weight_grams) }} · {{ grindLabel(item.grind_type) }}
              </span>
            </span>
            <span class="mini__price">{{ formatPrice(item.unit_price * item.quantity) }}</span>
          </li>
        </ul>

        <div class="checkout__rule" aria-hidden="true" />

        <dl class="totals">
          <div class="totals__row">
            <dt>جمع اقلام</dt>
            <dd>{{ formatPrice(cart.subtotal) }}</dd>
          </div>
          <div class="totals__row">
            <dt>ارسال</dt>
            <dd>{{ cart.shippingCost ? formatPrice(cart.shippingCost) : 'رایگان' }}</dd>
          </div>
        </dl>

        <div class="checkout__rule" aria-hidden="true" />

        <div class="totals__grand">
          <span>مبلغ قابل پرداخت</span>
          <strong>{{ formatPrice(cart.total) }}</strong>
        </div>

        <fieldset v-if="gateways.length > 1" class="gw">
          <legend class="gw__legend">درگاه پرداخت</legend>
          <label v-for="g in gateways" :key="g.name" class="gw__opt">
            <input v-model="gateway" type="radio" :value="g.name" name="gateway" />
            <span class="gw__box" aria-hidden="true" />
            <span class="gw__label">{{ g.label }}</span>
          </label>
        </fieldset>

        <BaseButton
          type="submit"
          variant="primary"
          size="lg"
          block
          :loading="submitting"
          :disabled="!cart.canCheckout || cart.quoteLoading"
        >
          {{ submitting ? 'در حال انتقال' : 'پرداخت' }}
        </BaseButton>

        <p class="checkout__gateway-note">
          پس از تأیید، به درگاه پرداخت منتقل می‌شوید.
        </p>

        <RouterLink to="/cart" class="checkout__back">بازگشت به سبد</RouterLink>
      </aside>
    </form>
  </main>
</template>

<style scoped>
/* ==========================================================================
   CheckoutView — Editorial register
   ========================================================================== */

.checkout {
  padding: clamp(2rem, 6vw, 4rem) clamp(1.25rem, 5vw, 4rem) 6rem;
}

.checkout__eyebrow {
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
  margin: 0;
}

.checkout__title {
  font-family: var(--font-editorial);
  font-size: clamp(2.25rem, 7vw, 3.5rem);
  line-height: 1.1;
  font-weight: 600;
  margin: 0.75rem 0 0;
}

.checkout__layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 22rem;
  gap: clamp(2rem, 4vw, 3.5rem);
  align-items: start;
  margin-top: 3rem;
  padding-top: 2.5rem;
  border-top: 3px solid var(--divider);
}

@media (max-width: 56rem) {
  .checkout__layout {
    grid-template-columns: 1fr;
  }
}

.checkout__section {
  margin-bottom: 3rem;
}

.checkout__section-title {
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-weight: 500;
  margin: 0 0 1.25rem;
  padding-bottom: 0.75rem;
  border-bottom: 3px solid var(--ink);
}

.checkout__error {
  border: 3px solid #a33224;
  background-color: #a33224;
  color: var(--paper);
  font-family: var(--font-terminal);
  font-size: 0.75rem;
  padding: 0.75rem 0.875rem;
  margin: 0 0 2rem;
}

.checkout__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.25rem;
  margin-bottom: 1.25rem;
}

@media (max-width: 34rem) {
  .checkout__grid {
    grid-template-columns: 1fr;
  }
}

.checkout__stack {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

/* --- Saved addresses ------------------------------------------------------- */
.checkout__addresses {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
  gap: 0.875rem;
}

.addr {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  border: 3px solid var(--ink);
  background-color: var(--paper);
  color: var(--ink);
  padding: 0.875rem;
  text-align: start;
  cursor: pointer;
}

.addr--on {
  background-color: var(--accent);
  color: var(--paper);
}

.addr:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: 3px;
}

.addr__name {
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  font-weight: 500;
}

.addr__text {
  font-family: var(--font-editorial);
  font-size: 0.875rem;
  line-height: 1.5;
}

/* --- Shipping -------------------------------------------------------------- */
.ship {
  display: flex;
  flex-direction: column;
  gap: 0.875rem;
}

.ship__option {
  display: flex;
  align-items: center;
  gap: 1rem;
  border: 3px solid var(--ink);
  background-color: var(--paper);
  color: var(--ink);
  padding: 1rem;
  text-align: start;
  cursor: pointer;
}

.ship__option--on {
  box-shadow: 5px 5px 0 var(--shadow);
}

.ship__option:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: 3px;
}

/* A square mark, filled with accent when chosen — never a round radio. */
.ship__mark {
  width: 1rem;
  height: 1rem;
  border: 3px solid var(--ink);
  flex: none;
}

.ship__option--on .ship__mark {
  background-color: var(--accent);
}

.ship__body {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  flex: 1;
}

.ship__label {
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  font-weight: 500;
}

.ship__desc {
  font-family: var(--font-editorial);
  font-size: 0.875rem;
  color: var(--ink-muted);
  line-height: 1.5;
}

.ship__days {
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.08em;
  color: var(--ink-muted);
}

.ship__cost {
  font-family: var(--font-editorial);
  font-size: 1rem;
  font-weight: 600;
  flex: none;
}

/* --- Summary --------------------------------------------------------------- */
.checkout__summary {
  border: 3px solid var(--ink);
  box-shadow: 8px 8px 0 var(--shadow);
  padding: 1.5rem;
  position: sticky;
  top: 2rem;
}

.mini {
  list-style: none;
  padding: 0;
  margin: 0;
}

.mini__row {
  display: flex;
  align-items: flex-start;
  gap: 0.625rem;
  padding: 0.625rem 0;
  border-bottom: 1px solid var(--rule);
}

.mini__qty {
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  color: var(--ink-muted);
  flex: none;
}

.mini__body {
  display: flex;
  flex-direction: column;
  gap: 0.1875rem;
  flex: 1;
  min-width: 0;
}

.mini__name {
  font-family: var(--font-editorial);
  font-size: 0.9375rem;
  line-height: 1.35;
}

.mini__meta {
  font-family: var(--font-terminal);
  font-size: 0.5625rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--ink-muted);
}

.mini__price {
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  flex: none;
}

.checkout__rule {
  height: 3px;
  background-color: var(--ink);
  margin: 1.25rem 0;
}

.totals {
  margin: 0;
}

.totals__row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.375rem 0;
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
}

.totals__row dt {
  color: var(--ink-muted);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.totals__row dd {
  margin: 0;
}

.totals__grand {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.totals__grand span {
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
}

.totals__grand strong {
  font-family: var(--font-editorial);
  font-size: 1.375rem;
  font-weight: 600;
}

/* --- Gateway picker -------------------------------------------------------- */
.gw {
  border: 3px solid var(--ink);
  padding: 0.875rem 1rem 1rem;
  margin-block-end: 1rem;
}

.gw__legend {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  padding-inline: 0.375rem;
}

.gw__opt {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  padding-block: 0.4375rem;
  cursor: pointer;
}

/* The native radio is replaced by a square: round controls have no place in
   this system. It stays in the DOM for keyboard and assistive tech. */
.gw__opt input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

.gw__box {
  flex: none;
  width: 1.125rem;
  height: 1.125rem;
  border: 3px solid var(--ink);
  background-color: var(--paper);
}

.gw__opt input:checked + .gw__box {
  background-color: var(--accent);
}

.gw__opt input:focus-visible + .gw__box {
  outline: 3px solid var(--accent);
  outline-offset: 3px;
}

.gw__label {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 1rem;
}

/* --- Keep-this-address ----------------------------------------------------- */
.keep {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  margin-block-start: 1rem;
  cursor: pointer;
}

.keep input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

.keep__box {
  flex: none;
  width: 1.125rem;
  height: 1.125rem;
  border: 3px solid var(--ink);
  background-color: var(--paper);
}

.keep input:checked + .keep__box {
  background-color: var(--accent);
}

.keep input:focus-visible + .keep__box {
  outline: 3px solid var(--accent);
  outline-offset: 3px;
}

.keep__label {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 0.9375rem;
}

.checkout__manage {
  display: inline-block;
  margin-block-start: 0.875rem;
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--accent);
  text-decoration: none;
  border-block-end: 2px solid var(--accent);
}

.checkout__gateway-note {
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.06em;
  line-height: 1.6;
  color: var(--ink-muted);
  margin: 1rem 0 0;
  text-align: center;
}

.checkout__back {
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
.checkout__back:hover {
  color: var(--ink);
}
</style>
