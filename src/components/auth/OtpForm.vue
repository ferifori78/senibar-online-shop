<script setup>
import { computed, onUnmounted, ref, watch } from 'vue'

import BaseButton from '@/components/base/BaseButton.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import { useAuthStore } from '@/stores/auth'

const emit = defineEmits(['done'])

const auth = useAuthStore()

// 'phone' asks for the number; 'code' asks for what arrived by SMS.
const step = ref('phone')
const phone = ref('')
const code = ref('')
const name = ref('')
const isNew = ref(false)

/** Seconds until another code may be asked for. */
const wait = ref(0)
let timer = null

function startCountdown(seconds) {
  wait.value = Math.max(0, Math.ceil(seconds || 0))
  clearInterval(timer)
  if (!wait.value) return
  timer = setInterval(() => {
    wait.value -= 1
    if (wait.value <= 0) clearInterval(timer)
  }, 1000)
}

onUnmounted(() => {
  clearInterval(timer)
  auth.resetErrors()
})

const phoneError = computed(() => auth.fieldErrors.phone || '')
const codeError = computed(() => auth.fieldErrors.code || '')

async function sendCode() {
  const { ok, data, retryAfter } = await auth.requestCode(phone.value)
  if (ok) {
    isNew.value = Boolean(data.is_new)
    step.value = 'code'
    startCountdown(data.resend_after)
    return
  }
  // A refusal carries how long to wait, so the button can say so rather than
  // letting the customer press it again into the same error.
  if (retryAfter) startCountdown(retryAfter)
}

async function submitCode() {
  const payload = { phone: phone.value, code: code.value }
  // Only sent when the server said this number has no account yet.
  if (isNew.value && name.value.trim()) payload.name = name.value.trim()

  const { ok } = await auth.verifyCode(payload)
  if (ok) emit('done')
}

/** Back to the number, e.g. after a typo. */
function edit() {
  step.value = 'phone'
  code.value = ''
  auth.resetErrors()
}

// Codes are digits; strip anything else so a pasted "کد: 12345" still works.
watch(code, (value) => {
  const digits = value.replace(/\D/g, '')
  if (digits !== value) code.value = digits
})
</script>

<template>
  <form class="otp" novalidate @submit.prevent="step === 'phone' ? sendCode() : submitCode()">
    <p v-if="auth.error" class="otp__banner" role="alert">{{ auth.error }}</p>

    <!-- Step one: the number ------------------------------------------- -->
    <template v-if="step === 'phone'">
      <BaseInput
        v-model="phone"
        label="شماره موبایل"
        type="tel"
        inputmode="tel"
        digits="strict"
        placeholder="09xxxxxxxxx"
        autocomplete="tel"
        :error="phoneError"
        hint="کد ورود به این شماره پیامک می‌شود."
        required
      />

      <BaseButton type="submit" variant="primary" size="lg" block :loading="auth.loading">
        دریافت کد
      </BaseButton>
    </template>

    <!-- Step two: the code --------------------------------------------- -->
    <template v-else>
      <p class="otp__sent">
        کد به شماره
        <span class="otp__number">{{ phone }}</span>
        پیامک شد.
        <button type="button" class="otp__edit" @click="edit">ویرایش شماره</button>
      </p>

      <BaseInput
        v-model="code"
        label="کد ورود"
        inputmode="numeric"
        digits="strict"
        autocomplete="one-time-code"
        :error="codeError"
        required
      />

      <!-- Asked only from someone the server told us has no account. -->
      <BaseInput
        v-if="isNew"
        v-model="name"
        label="نام شما"
        hint="روی سفارش‌ها و پیامک‌ها به این نام صدایتان می‌زنیم."
        autocomplete="given-name"
      />

      <BaseButton type="submit" variant="primary" size="lg" block :loading="auth.loading">
        {{ isNew ? 'ساخت حساب و ورود' : 'ورود' }}
      </BaseButton>

      <button
        type="button"
        class="otp__resend"
        :disabled="wait > 0 || auth.loading"
        @click="sendCode"
      >
        {{ wait > 0 ? `ارسال دوباره تا ${wait} ثانیه دیگر` : 'ارسال دوباره کد' }}
      </button>
    </template>
  </form>
</template>

<style scoped>
.otp {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.otp__banner {
  border: 3px solid #a33224;
  color: #a33224;
  padding: 0.75rem 0.875rem;
  margin: 0;
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.75rem;
  line-height: 1.7;
}

.otp__sent {
  margin: 0;
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.75rem;
  line-height: 1.9;
  color: var(--ink-muted);
}

.otp__number {
  /* A bare run of digits in an RTL line is laid out right-to-left by the bidi
     algorithm, so the number would read backwards without this. */
  direction: ltr;
  display: inline-block;
  color: var(--ink);
}

.otp__edit,
.otp__resend {
  background: none;
  border: 0;
  border-radius: 0;
  padding: 0;
  cursor: pointer;
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.06em;
  color: var(--accent);
  border-block-end: 2px solid var(--accent);
}

.otp__resend {
  align-self: center;
}

.otp__edit:disabled,
.otp__resend:disabled {
  color: var(--ink-muted);
  border-block-end-color: transparent;
  cursor: not-allowed;
}
</style>
