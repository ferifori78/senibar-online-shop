<script setup>
import { computed, onUnmounted, reactive, ref } from 'vue'
import { useRouter, RouterLink } from 'vue-router'

import AuthLayout from '@/components/layout/AuthLayout.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const form = reactive({
  first_name: '',
  last_name: '',
  email: '',
  phone: '',
  password: '',
  password_confirm: '',
})

// Checked client-side too, so the user isn't sent to the server to be told
// something the browser already knows.
const localErrors = ref({})

function validate() {
  const errors = {}
  if (form.password.length < 8) {
    errors.password = 'رمز عبور باید حداقل ۸ کاراکتر باشد.'
  }
  if (form.password !== form.password_confirm) {
    errors.password_confirm = 'تکرار رمز عبور مطابقت ندارد.'
  }
  localErrors.value = errors
  return Object.keys(errors).length === 0
}

/** Server errors win once they arrive; local ones cover the gap before that. */
function errorFor(field) {
  return auth.fieldErrors[field] || localErrors.value[field] || ''
}

const passwordHint = computed(() =>
  errorFor('password') ? '' : 'حداقل ۸ کاراکتر، غیر از اطلاعات شخصی شما.',
)

async function submit() {
  localErrors.value = {}
  if (!validate()) return

  const { ok } = await auth.register({ ...form })
  if (ok) {
    router.push('/')
  }
}

onUnmounted(() => auth.resetErrors())
</script>

<template>
  <AuthLayout
    eyebrow="SENOBAR / ACCOUNT"
    title="ساخت حساب"
    subtitle="یک حساب بسازید تا سفارش‌هایتان را دنبال کنید و قهوه را تازه رست‌شده تحویل بگیرید."
  >
    <form class="auth-form" novalidate @submit.prevent="submit">
      <p v-if="auth.error" class="auth-form__banner" role="alert">
        {{ auth.error }}
      </p>

      <div class="auth-form__row">
        <BaseInput
          v-model="form.first_name"
          label="نام"
          autocomplete="given-name"
          :error="errorFor('first_name')"
        />
        <BaseInput
          v-model="form.last_name"
          label="نام خانوادگی"
          autocomplete="family-name"
          :error="errorFor('last_name')"
        />
      </div>

      <BaseInput
        v-model="form.email"
        label="ایمیل"
        type="email"
        autocomplete="email"
        placeholder="name@example.com"
        :error="errorFor('email')"
        required
      />

      <BaseInput
        v-model="form.phone"
        label="شماره تماس"
        type="tel"
        inputmode="tel"
        digits="strict"
        autocomplete="tel"
        placeholder="09xxxxxxxxx"
        :error="errorFor('phone')"
      />

      <BaseInput
        v-model="form.password"
        label="رمز عبور"
        type="password"
        autocomplete="new-password"
        :hint="passwordHint"
        :error="errorFor('password')"
        required
      />

      <BaseInput
        v-model="form.password_confirm"
        label="تکرار رمز عبور"
        type="password"
        autocomplete="new-password"
        :error="errorFor('password_confirm')"
        required
      />

      <BaseButton type="submit" variant="primary" size="lg" block :loading="auth.loading">
        {{ auth.loading ? 'در حال ثبت' : 'ساخت حساب' }}
      </BaseButton>
    </form>

    <template #aside>
      حساب دارید؟
      <RouterLink to="/login" class="auth-form__link">وارد شوید</RouterLink>
    </template>
  </AuthLayout>
</template>

<style scoped>
.auth-form {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.auth-form__row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

@media (max-width: 30rem) {
  .auth-form__row {
    grid-template-columns: 1fr;
  }
}

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
