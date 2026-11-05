<script setup>
import { onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import BaseButton from '@/components/base/BaseButton.vue'
import { paymentsApi } from '@/api/orders'
import { parseApiError } from '@/api/client'
import { useCartStore } from '@/stores/cart'
import { formatPrice } from '@/utils/format'

/**
 * Where the gateway returns the customer. Verification happens here rather
 * than in the browser's imagination: the backend re-asks the gateway whether
 * the money actually moved, and only then is the order marked paid.
 */
const route = useRoute()
const cart = useCartStore()

const state = ref('verifying') // verifying | paid | cancelled | failed
const orderNumber = ref('')
const refId = ref('')
const amount = ref(null)
const message = ref('')

onMounted(async () => {
  // The two gateways name their return parameters differently:
  //   ZarinPal  ?Authority=A000…&Status=OK|NOK
  //   BitPay    ?id_get=1200&trans_id=555   (and no status at all)
  // Both are forwarded as-is; the server normalises and the driver reads what
  // it needs. Sending `Status: OK` for BitPay is correct — a customer who
  // abandons the bank page never reaches this route.
  const authority =
    route.query.Authority || route.query.authority || route.query.id_get
  const transId = route.query.trans_id || route.query.transId
  const gatewayStatus = route.query.Status || route.query.status || 'OK'

  if (!authority) {
    state.value = 'failed'
    message.value = 'اطلاعات بازگشت از درگاه ناقص است.'
    return
  }

  try {
    const { data } = await paymentsApi.verify({
      authority,
      status: gatewayStatus,
      ...(transId ? { trans_id: transId } : {}),
    })
    state.value = data.status === 'paid' ? 'paid' : data.status
    orderNumber.value = data.order || ''
    refId.value = data.ref_id || ''
    amount.value = data.payment?.amount ?? null

    if (state.value === 'paid') {
      // The money is settled and the order is recorded server-side; the local
      // cart has done its job.
      cart.clear()
      sessionStorage.removeItem('senobar.pending_order')
    }
  } catch (err) {
    const parsed = parseApiError(err)
    const data = err?.response?.data || {}
    state.value = data.status === 'cancelled' ? 'cancelled' : 'failed'
    orderNumber.value = data.order || sessionStorage.getItem('senobar.pending_order') || ''
    message.value = parsed.message || data.detail || 'تأیید پرداخت ناموفق بود.'
  }
})
</script>

<template>
  <main class="register-editorial callback">
    <div class="callback__panel">
      <!-- Verifying ---------------------------------------------------- -->
      <template v-if="state === 'verifying'">
        <p class="callback__eyebrow">SENOBAR / PAYMENT</p>
        <h1 class="callback__title">در حال بررسی پرداخت</h1>
        <p class="callback__text">
          لطفاً این صفحه را نبندید. نتیجه‌ی تراکنش در حال تأیید از درگاه است.
        </p>
        <div class="callback__bar" aria-hidden="true"><span /></div>
      </template>

      <!-- Paid --------------------------------------------------------- -->
      <template v-else-if="state === 'paid'">
        <p class="callback__eyebrow">SENOBAR / PAYMENT</p>
        <h1 class="callback__title">پرداخت انجام شد</h1>
        <p class="callback__text">
          سفارش شما ثبت شد و در صف رست قرار گرفت. قهوه پس از رست ارسال می‌شود.
        </p>

        <dl class="callback__rows">
          <div class="callback__row">
            <dt>شماره سفارش</dt>
            <dd>{{ orderNumber }}</dd>
          </div>
          <div v-if="refId" class="callback__row">
            <dt>کد پیگیری</dt>
            <dd>{{ refId }}</dd>
          </div>
          <div v-if="amount" class="callback__row">
            <dt>مبلغ</dt>
            <dd>{{ formatPrice(amount) }}</dd>
          </div>
        </dl>

        <div class="callback__actions">
          <RouterLink v-if="orderNumber" :to="`/orders/${orderNumber}`">
            <BaseButton variant="primary">پیگیری سفارش</BaseButton>
          </RouterLink>
          <RouterLink to="/products">
            <BaseButton variant="secondary">ادامه خرید</BaseButton>
          </RouterLink>
        </div>
      </template>

      <!-- Cancelled / failed ------------------------------------------- -->
      <template v-else>
        <p class="callback__eyebrow">SENOBAR / PAYMENT</p>
        <h1 class="callback__title">
          {{ state === 'cancelled' ? 'پرداخت لغو شد' : 'پرداخت ناموفق بود' }}
        </h1>
        <p class="callback__text">
          {{
            message ||
            (state === 'cancelled'
              ? 'شما پرداخت را در درگاه لغو کردید. سبد خرید شما دست‌نخورده باقی مانده است.'
              : 'تراکنش تأیید نشد. اگر مبلغی کسر شده باشد، طی ۷۲ ساعت بازگردانده می‌شود.')
          }}
        </p>

        <dl v-if="orderNumber" class="callback__rows">
          <div class="callback__row">
            <dt>شماره سفارش</dt>
            <dd>{{ orderNumber }}</dd>
          </div>
        </dl>

        <div class="callback__actions">
          <RouterLink to="/cart"><BaseButton variant="primary">بازگشت به سبد</BaseButton></RouterLink>
          <RouterLink to="/products"><BaseButton variant="ghost">قهوه‌ها</BaseButton></RouterLink>
        </div>
      </template>
    </div>
  </main>
</template>

<style scoped>
.callback {
  display: grid;
  place-items: center;
  padding: 2rem clamp(1.25rem, 5vw, 4rem);
}

.callback__panel {
  width: 100%;
  max-width: 32rem;
  border: 3px solid var(--ink);
  box-shadow: 10px 10px 0 var(--shadow);
  padding: clamp(1.75rem, 5vw, 2.75rem);
}

.callback__eyebrow {
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
  margin: 0;
}

.callback__title {
  font-family: var(--font-editorial);
  font-size: clamp(1.75rem, 5vw, 2.25rem);
  line-height: 1.2;
  font-weight: 600;
  margin: 0.75rem 0 0;
}

.callback__text {
  font-family: var(--font-editorial);
  font-size: 1rem;
  line-height: 1.75;
  color: var(--ink-muted);
  margin: 1rem 0 0;
}

/* A determinate-looking bar that simply sweeps — squares, no spinner arc. */
.callback__bar {
  height: 0.75rem;
  border: 3px solid var(--ink);
  margin-top: 2rem;
  overflow: hidden;
}

.callback__bar span {
  display: block;
  width: 35%;
  height: 100%;
  background-color: var(--accent);
  animation: sweep 1.1s steps(6, end) infinite;
}

@keyframes sweep {
  from {
    transform: translateX(-100%);
  }
  to {
    transform: translateX(300%);
  }
}

.callback__rows {
  margin: 2rem 0 0;
}

.callback__row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.625rem 0;
  border-bottom: 1px solid var(--rule);
  font-family: var(--font-terminal);
  font-size: 0.75rem;
}

.callback__row dt {
  color: var(--ink-muted);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.callback__row dd {
  margin: 0;
}

.callback__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  margin-top: 2rem;
}

@media (prefers-reduced-motion: reduce) {
  .callback__bar span {
    animation-duration: 3s;
  }
}
</style>
