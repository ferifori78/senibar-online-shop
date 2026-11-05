<script setup>
import { ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import BrandMark from '@/components/base/BrandMark.vue'
import VowelledText from '@/components/base/VowelledText.vue'
import { panelPath } from '@/constants/panel'
import { useAuthStore } from '@/stores/auth'
import { useCartStore } from '@/stores/cart'

const auth = useAuthStore()
const cart = useCartStore()
const route = useRoute()

const open = ref(false)

// Navigating with the drawer open would leave it covering the new page.
watch(() => route.fullPath, () => { open.value = false })
</script>

<template>
  <header class="head">
    <div class="head__bar">
      <!-- The name beside the mark is set in Persian, vowelled, rather than
           the latin SENOBAR. `aria-label` carries the announced name, since
           the artwork itself is decorative. -->
      <RouterLink to="/" class="head__mark" aria-label="صنوبر — صفحه اصلی">
        <BrandMark :size="56" />
        <VowelledText class="head__mark-name" text="صِنوبَر" :scale="1.5" face="display" />
      </RouterLink>

      <!-- Below 52rem this collapses into the drawer under the bar. -->
      <nav class="head__nav" aria-label="ناوبری اصلی">
        <RouterLink to="/products" class="head__link">قهوه‌ها</RouterLink>
        <RouterLink to="/about" class="head__link">داستان ما</RouterLink>
        <!-- Orders and support live inside the account panel; repeating them
             here made the bar long enough to collapse on ordinary laptops. -->
        <RouterLink v-if="auth.isAuthenticated" to="/account" class="head__link">حساب من</RouterLink>
        <RouterLink v-if="auth.isStaff" :to="panelPath()" class="head__link">پنل</RouterLink>
      </nav>

      <div class="head__end">
        <RouterLink to="/cart" class="head__cart">
          <span>سبد</span>
          <span v-if="cart.count" class="head__count">{{ cart.count }}</span>
        </RouterLink>

        <RouterLink v-if="!auth.isAuthenticated" to="/login" class="head__link">ورود</RouterLink>
        <button v-else type="button" class="head__link head__link--button" @click="auth.logout()">
          خروج
        </button>

        <button
          type="button"
          class="head__toggle"
          :aria-expanded="open"
          aria-controls="site-drawer"
          aria-label="منو"
          @click="open = !open"
        >
          <!-- Three rules, not a glyph. -->
          <span aria-hidden="true" />
          <span aria-hidden="true" />
          <span aria-hidden="true" />
        </button>
      </div>
    </div>

    <nav v-if="open" id="site-drawer" class="head__drawer" aria-label="ناوبری">
      <RouterLink to="/products" class="head__drawer-link">قهوه‌ها</RouterLink>
      <RouterLink to="/about" class="head__drawer-link">داستان ما</RouterLink>
      <RouterLink v-if="auth.isAuthenticated" to="/account" class="head__drawer-link">حساب من</RouterLink>
      <RouterLink v-if="auth.isStaff" :to="panelPath()" class="head__drawer-link">پنل مدیریت</RouterLink>
    </nav>
  </header>
</template>

<style scoped>
/* ==========================================================================
   SiteHeader — Editorial register
   A ruled bar, not a floating pill. Sticks so the cart stays reachable.
   ========================================================================== */

.head {
  position: sticky;
  inset-block-start: 0;
  z-index: 20;
  background-color: var(--paper);
  border-block-end: 3px solid var(--divider);
}

.head__bar {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  /* Tightened from 0.875rem: the mark is taller than the old glyph, and the
     bar would otherwise eat noticeably more of the viewport. */
  padding: 0.5rem clamp(1.25rem, 5vw, 4rem);
}

/* --- Mark ------------------------------------------------------------------ */
.head__mark {
  display: flex;
  /* Centre, not baseline: the leaf has no baseline to sit on. */
  align-items: center;
  gap: 0.625rem;
  color: inherit;
  text-decoration: none;
  margin-inline-end: auto;
}

.head__mark-name {
  /* The wordmark: the one place the name is set on every page. */
  font-family: var(--font-display, "Morabba", sans-serif);
  font-size: 1.375rem;
  font-weight: 900;
  line-height: 1;
  color: var(--ink);
}

/* --- Links ----------------------------------------------------------------- */
.head__nav,
.head__end {
  display: flex;
  align-items: center;
  gap: 1.25rem;
}

.head__link {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink);
  text-decoration: none;
  padding-block-end: 2px;
  border-block-end: 2px solid transparent;
}

.head__link--button {
  border-inline: 0;
  border-block-start: 0;
  background: none;
  cursor: pointer;
  font: inherit;
  letter-spacing: 0.14em;
  padding-inline: 0;
}

.head__link:hover,
.head__link.router-link-active {
  border-block-end-color: var(--accent);
}

.head__link:focus-visible,
.head__cart:focus-visible,
.head__toggle:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: 3px;
}

/* --- Cart ------------------------------------------------------------------ */
.head__cart {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  border: 3px solid var(--ink);
  padding: 0.3125rem 0.625rem;
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink);
  text-decoration: none;
}

.head__count {
  background-color: var(--accent);
  color: var(--paper);
  min-width: 1.125rem;
  text-align: center;
  padding: 0 0.25rem;
  font-size: 0.625rem;
}

/* --- Drawer toggle --------------------------------------------------------- */
.head__toggle {
  display: none;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
  width: 2.25rem;
  height: 2.25rem;
  border: 3px solid var(--ink);
  border-radius: 0;
  background-color: var(--paper);
  padding: 0 0.375rem;
  cursor: pointer;
}

.head__toggle span {
  display: block;
  height: 3px;
  background-color: var(--ink);
}

.head__drawer {
  display: none;
  flex-direction: column;
  border-block-start: 3px solid var(--divider);
}

.head__drawer-link {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.75rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink);
  text-decoration: none;
  padding: 0.875rem clamp(1.25rem, 5vw, 4rem);
  border-block-end: 2px solid var(--rule);
}

.head__drawer-link.router-link-active {
  color: var(--accent);
}

@media (max-width: 52rem) {
  .head__nav {
    display: none;
  }
  .head__toggle {
    display: flex;
  }
  .head__drawer {
    display: flex;
  }
}
</style>
