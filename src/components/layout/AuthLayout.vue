<script setup>
import { RouterLink } from 'vue-router'

import BrandMark from '@/components/base/BrandMark.vue'

defineProps({
  /** Small mono label above the title, e.g. "ACCOUNT / 01". */
  eyebrow: { type: String, default: '' },
  title: { type: String, default: '' },
  subtitle: { type: String, default: '' },
})

const year = new Date().getFullYear()
</script>

<template>
  <div class="auth-shell register-editorial">
    <!-- Header: wordmark and one escape route. Nothing else. -->
    <header class="auth-shell__header">
      <!-- No text wordmark: the artwork carries «صنوبر» itself. -->
      <RouterLink to="/" class="auth-shell__brand" aria-label="صنوبر — صفحه اصلی">
        <BrandMark :size="52" />
      </RouterLink>

      <RouterLink to="/" class="auth-shell__back">بازگشت به فروشگاه</RouterLink>
    </header>

    <main class="auth-shell__main">
      <div class="auth-shell__panel">
        <p v-if="eyebrow" class="auth-shell__eyebrow">{{ eyebrow }}</p>
        <h1 v-if="title" class="auth-shell__title">{{ title }}</h1>
        <p v-if="subtitle" class="auth-shell__subtitle">{{ subtitle }}</p>

        <div class="auth-shell__rule" aria-hidden="true" />

        <slot />
      </div>

      <p v-if="$slots.aside" class="auth-shell__aside">
        <slot name="aside" />
      </p>
    </main>

    <footer class="auth-shell__footer">
      <span>صنوبر — قهوه تخصصی</span>
      <span>{{ year }}</span>
    </footer>
  </div>
</template>

<style scoped>
/* ==========================================================================
   AuthLayout — Editorial register
   Paper ground, serif headings, generous whitespace. The form panel sits on
   a hard shadow; everything else is rules and space.
   ========================================================================== */

.auth-shell {
  min-height: 100vh;
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
  background-color: var(--paper);
}

/* --- Header ---------------------------------------------------------------- */
.auth-shell__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1.5rem clamp(1.25rem, 5vw, 4rem);
  border-bottom: 3px solid var(--divider);
}

.auth-shell__brand {
  display: inline-flex;
  align-items: center;
  gap: 0.625rem;
  color: var(--ink);
  text-decoration: none;
}

.auth-shell__back {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
  text-decoration: none;
  border-bottom: 2px solid transparent;
  padding-bottom: 2px;
  transition: color 90ms cubic-bezier(0.2, 0, 0, 1);
}

.auth-shell__back:hover {
  color: var(--ink);
  border-bottom-color: var(--accent);
}

/* --- Main ------------------------------------------------------------------ */
.auth-shell__main {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1.75rem;
  padding: clamp(2.5rem, 8vw, 5rem) clamp(1.25rem, 5vw, 4rem);
}

.auth-shell__panel {
  width: 100%;
  max-width: 30rem;
  background-color: var(--paper);
  border: 3px solid var(--ink);
  box-shadow: 10px 10px 0 var(--shadow);
  padding: clamp(1.75rem, 5vw, 2.75rem);
}

.auth-shell__eyebrow {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
  margin: 0;
}

.auth-shell__title {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: clamp(1.875rem, 5vw, 2.5rem);
  line-height: 1.15;
  font-weight: 600;
  margin: 0.75rem 0 0;
}

.auth-shell__subtitle {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 1rem;
  line-height: 1.65;
  color: var(--ink-muted);
  margin: 0.75rem 0 0;
}

.auth-shell__rule {
  height: 3px;
  background-color: var(--ink);
  margin: 1.75rem 0;
}

.auth-shell__aside {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--ink-muted);
  text-align: center;
  margin: 0;
  max-width: 30rem;
}

/* --- Footer ---------------------------------------------------------------- */
.auth-shell__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1.25rem clamp(1.25rem, 5vw, 4rem);
  border-top: 3px solid var(--divider);
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
}

@media (prefers-reduced-motion: reduce) {
  .auth-shell__back {
    transition: none;
  }
}
</style>
