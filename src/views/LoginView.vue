<script setup>
import { computed, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'

import AuthLayout from '@/components/layout/AuthLayout.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import OtpForm from '@/components/auth/OtpForm.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const form = reactive({ email: '', password: '' })

// Phone first: it is the shorter path for a customer, and it doubles as
// registration. The password form stays for accounts that have one — and for
// staff, who need it to reach the panel.
const method = ref('otp')

// Errors belong to whichever form raised them; switching must not carry a
// password complaint over to the phone form.
watch(method, () => auth.resetErrors())

function done() {
  router.push(route.query.redirect || '/')
}

// SimpleJWT reports a bad login under the credential field name, which is
// `email` here. Surface it on the field rather than as a banner.
const emailError = computed(() => auth.fieldErrors.email || '')
const passwordError = computed(() => auth.fieldErrors.password || '')

async function submit() {
  const { ok } = await auth.login({ email: form.email, password: form.password })
  if (ok) done()
}

onUnmounted(() => auth.resetErrors())
</script>

<template>
  <AuthLayout
    eyebrow="SENOBAR / ACCOUNT"
    title="ورود به حساب"
    subtitle="برای پیگیری سفارش‌ها و ثبت سفارش تازه وارد شوید."
  >
    <div class="switch" role="tablist" aria-label="روش ورود">
      <button
        type="button"
        class="switch__tab"
        :class="{ 'switch__tab--on': method === 'otp' }"
        role="tab"
        :aria-selected="method === 'otp'"
        @click="method = 'otp'"
      >
        ورود با پیامک
      </button>
      <button
        type="button"
        class="switch__tab"
        :class="{ 'switch__tab--on': method === 'password' }"
        role="tab"
        :aria-selected="method === 'password'"
        @click="method = 'password'"
      >
        ایمیل و رمز
      </button>
    </div>

    <OtpForm v-if="method === 'otp'" @done="done" />

    <form v-else class="auth-form" novalidate @submit.prevent="submit">
      <p v-if="auth.error" class="auth-form__banner" role="alert">
        {{ auth.error }}
      </p>

      <BaseInput
        v-model="form.email"
        label="ایمیل"
        type="email"
        autocomplete="email"
        placeholder="name@example.com"
        :error="emailError"
        required
      />

      <BaseInput
        v-model="form.password"
        label="رمز عبور"
        type="password"
        autocomplete="current-password"
        :error="passwordError"
        required
      />

      <BaseButton type="submit" variant="primary" size="lg" block :loading="auth.loading">
        {{ auth.loading ? 'در حال ورود' : 'ورود' }}
      </BaseButton>
    </form>

    <template #aside>
      <template v-if="method === 'otp'">
        با شماره موبایل هم وارد می‌شوید و هم حساب می‌سازید.
      </template>
      <template v-else>
        حساب ندارید؟
        <RouterLink to="/register" class="auth-form__link">ثبت‌نام کنید</RouterLink>
      </template>
    </template>
  </AuthLayout>
</template>

<style scoped>
/* Two square tabs sharing one rule, not a pill toggle. */
.switch {
  display: flex;
  border: 3px solid var(--ink);
  margin-block-end: 1.5rem;
}

.switch__tab {
  flex: 1;
  background: none;
  border: 0;
  border-radius: 0;
  padding: 0.6875rem 0.5rem;
  cursor: pointer;
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.1em;
  color: var(--ink-muted);
}

.switch__tab + .switch__tab {
  border-inline-start: 3px solid var(--ink);
}

.switch__tab--on {
  background-color: var(--accent);
  color: var(--paper);
}

.switch__tab:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: -6px;
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

/* Error banner: a filled slab, not a tinted pastel box. */
.auth-form__banner {
  border: 3px solid #a33224;
  background-color: #a33224;
  color: var(--paper);
  padding: 0.75rem 0.875rem;
  margin: 0;
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.75rem;
  line-height: 1.5;
}

.auth-form__link {
  color: var(--accent);
  text-decoration: none;
  border-bottom: 2px solid var(--accent);
  padding-bottom: 1px;
}

.auth-form__link:hover {
  color: var(--ink);
  border-bottom-color: var(--ink);
}
</style>
