<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'

import BaseButton from '@/components/base/BaseButton.vue'
import { paymentsApi } from '@/api/orders'
import { formatPrice } from '@/utils/format'

/**
 * Stands in for the gateway's hosted pay page. Reachable only while the
 * backend runs PAYMENT_GATEWAY=mock — the mock-pay endpoint 404s otherwise, so
 * this page cannot settle anything real.
 */
const route = useRoute()
const authority = route.params.authority
const callback = route.query.callback
const amount = route.query.amount

const working = ref(false)

async function finish(outcome) {
  working.value = true
  try {
    await paymentsApi.mockPay(authority, outcome)
  } catch {
    // The backend refused; still return the customer so they see a result.
  }
  const status = outcome === 'success' ? 'OK' : 'NOK'
  const separator = callback.includes('?') ? '&' : '?'
  window.location.assign(`${callback}${separator}Status=${status}`)
}
</script>

<template>
  <main class="register-terminal gateway">
    <div class="gateway__panel">
      <header class="gateway__head">
        <span class="status-light" data-state="warn" />
        <span class="gateway__tag">MOCK GATEWAY</span>
      </header>

      <p class="gateway__warn">
        این یک درگاه شبیه‌سازی‌شده است. هیچ تراکنش واقعی انجام نمی‌شود.
      </p>

      <dl class="gateway__rows">
        <div class="gateway__row">
          <dt>شناسه تراکنش</dt>
          <dd class="gateway__mono">{{ authority }}</dd>
        </div>
        <div v-if="amount" class="gateway__row">
          <dt>مبلغ</dt>
          <dd>{{ formatPrice(amount) }}</dd>
        </div>
      </dl>

      <div class="gateway__actions">
        <BaseButton variant="primary" size="lg" block :loading="working" @click="finish('success')">
          پرداخت موفق
        </BaseButton>
        <BaseButton variant="secondary" inverse block :disabled="working" @click="finish('fail')">
          شبیه‌سازی خطا
        </BaseButton>
      </div>
    </div>
  </main>
</template>

<style scoped>
/* The one place the Terminal register faces a customer: a mock gateway should
   look like infrastructure, never like the shop. */
.gateway {
  min-height: 100vh;
  min-height: 100dvh;
  display: grid;
  place-items: center;
  padding: 2rem;
  background-color: var(--terminal);
}

.gateway__panel {
  width: 100%;
  max-width: 26rem;
  border: 3px solid var(--terminal-text);
  box-shadow: 8px 8px 0 var(--terminal-text);
  padding: 1.75rem;
}

.gateway__head {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  padding-bottom: 1rem;
  border-bottom: 3px solid var(--terminal-text);
}

.gateway__tag {
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--terminal-text);
}

.gateway__warn {
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  line-height: 1.7;
  color: var(--terminal-dim);
  margin: 1.25rem 0;
}

.gateway__rows {
  margin: 0 0 1.75rem;
}

.gateway__row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--terminal-rule);
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
}

.gateway__row dt {
  color: var(--terminal-dim);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.gateway__row dd {
  margin: 0;
  color: var(--terminal-text);
}

.gateway__mono {
  font-size: 0.5625rem;
  word-break: break-all;
  text-align: end;
}

.gateway__actions {
  display: flex;
  flex-direction: column;
  gap: 0.875rem;
}
</style>
