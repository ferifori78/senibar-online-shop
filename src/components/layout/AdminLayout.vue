<script setup>
import { computed } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import BrandMark from '@/components/base/BrandMark.vue'
import { panelPath } from '@/constants/panel'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const NAV = [
  { to: panelPath(), label: 'DASHBOARD', exact: true },
  { to: panelPath('orders'), label: 'ORDERS' },
  { to: panelPath('products'), label: 'PRODUCTS' },
  { to: panelPath('batches'), label: 'BATCHES' },
  { to: panelPath('inventory'), label: 'INVENTORY' },
  { to: panelPath('users'), label: 'USERS' },
  { to: panelPath('support'), label: 'SUPPORT' },
  { to: panelPath('settings'), label: 'SETTINGS' },
]

function isActive(item) {
  return item.exact ? route.path === item.to : route.path.startsWith(item.to)
}

const stamp = computed(() =>
  new Date().toLocaleDateString('fa-IR', { year: 'numeric', month: 'long', day: 'numeric' }),
)

async function signOut() {
  await auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="admin register-terminal">
    <!-- Header: one dense bar, everything on it. -->
    <header class="admin__bar">
      <RouterLink :to="panelPath()" class="admin__brand">
        <!-- Terminal register: the stock green is near-invisible on this ground. -->
        <BrandMark :size="30" light />
        <span class="admin__wordmark">SENOBAR</span>
        <span class="admin__env">TERMINAL</span>
      </RouterLink>

      <nav class="admin__nav" aria-label="پنل مدیریت">
        <RouterLink
          v-for="item in NAV"
          :key="item.to"
          :to="item.to"
          class="admin__link"
          :class="{ 'admin__link--on': isActive(item) }"
        >
          {{ item.label }}
        </RouterLink>
      </nav>

      <div class="admin__session">
        <span class="admin__date">{{ stamp }}</span>
        <span class="admin__user">
          <span class="status-light" data-state="ok" />
          {{ auth.displayName }}
        </span>
        <RouterLink to="/" class="admin__exit">SHOP</RouterLink>
        <button type="button" class="admin__exit" @click="signOut">EXIT</button>
      </div>
    </header>

    <main class="admin__main">
      <slot />
    </main>
  </div>
</template>

<style scoped>
/* ==========================================================================
   AdminLayout — Terminal register
   Dark ground, monospace, high density. Rules in light, not ink.
   ========================================================================== */

.admin {
  min-height: 100vh;
  min-height: 100dvh;
  background-color: var(--terminal);
  color: var(--terminal-text);
  display: flex;
  flex-direction: column;
}

/* --- Bar ------------------------------------------------------------------- */
.admin__bar {
  display: flex;
  align-items: center;
  gap: 2rem;
  flex-wrap: wrap;
  padding: 0.75rem 1.25rem;
  border-bottom: 3px solid var(--terminal-text);
  background-color: var(--terminal);
  position: sticky;
  top: 0;
  z-index: 10;
}

.admin__brand {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--terminal-text);
  text-decoration: none;
}

.admin__wordmark {
  font-family: var(--font-terminal);
  font-size: 0.8125rem;
  letter-spacing: 0.18em;
  font-weight: 600;
}

.admin__env {
  border: 2px solid var(--accent);
  color: var(--accent);
  font-family: var(--font-terminal);
  font-size: 0.5rem;
  letter-spacing: 0.14em;
  padding: 0.125rem 0.3125rem;
}

/* --- Nav ------------------------------------------------------------------- */
.admin__nav {
  display: flex;
  gap: 0;
  margin-inline-end: auto;
}

.admin__link {
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  color: var(--terminal-dim);
  text-decoration: none;
  padding: 0.4375rem 0.75rem;
  border: 2px solid transparent;
}

.admin__link:hover {
  color: var(--terminal-text);
  background-color: var(--terminal-raised);
}

/* Active nav is the one place accent appears in the chrome. */
.admin__link--on {
  color: var(--paper);
  background-color: var(--accent);
}

.admin__link:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

/* --- Session --------------------------------------------------------------- */
.admin__session {
  display: flex;
  align-items: center;
  gap: 1rem;
  font-family: var(--font-terminal);
  font-size: 0.5625rem;
  letter-spacing: 0.12em;
}

.admin__date {
  color: var(--terminal-dim);
}

.admin__user {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  color: var(--terminal-text);
}

.admin__exit {
  border: 2px solid var(--terminal-rule);
  background: none;
  color: var(--terminal-dim);
  font: inherit;
  letter-spacing: 0.14em;
  padding: 0.25rem 0.5rem;
  cursor: pointer;
  text-decoration: none;
}

.admin__exit:hover {
  border-color: var(--terminal-text);
  color: var(--terminal-text);
}

.admin__exit:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

/* --- Main ------------------------------------------------------------------ */
.admin__main {
  flex: 1;
  padding: 1.5rem 1.25rem 4rem;
}

@media (max-width: 60rem) {
  .admin__bar {
    gap: 1rem;
  }
  .admin__session {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
