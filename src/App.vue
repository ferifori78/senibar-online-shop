<script setup>
import { computed } from 'vue'
import { RouterView, useRoute } from 'vue-router'

import SiteFooter from '@/components/layout/SiteFooter.vue'
import SiteHeader from '@/components/layout/SiteHeader.vue'

const route = useRoute()

// The admin panel is the Terminal register with its own chrome, and the auth
// pages carry AuthLayout. Everything else is the storefront and gets these.
const showChrome = computed(() => route.meta.chrome !== false)
</script>

<template>
  <div class="shell" :class="{ 'shell--chrome': showChrome }">
    <SiteHeader v-if="showChrome" />
    <RouterView />
    <SiteFooter v-if="showChrome" />
  </div>
</template>

<style scoped>
/* Footer pinned to the bottom on short pages, without min-height on each view. */
.shell--chrome {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  min-height: 100dvh;
  background-color: var(--paper);
}

.shell--chrome :deep(> main) {
  flex: 1;
}
</style>
