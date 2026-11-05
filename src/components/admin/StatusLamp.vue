<script setup>
import { computed } from 'vue'

import { orderStatusLabel, orderStatusState } from '@/utils/format'

/**
 * A small circular lamp plus its label — the Terminal register's way of
 * showing state. Never a filled badge: the lamp carries the colour and the
 * text carries the meaning, so colour is never the only signal.
 */
const props = defineProps({
  /** An order status key, e.g. "roasting". */
  status: { type: String, default: '' },
  /** Or drive it directly: ok | warn | error | active | idle. */
  state: { type: String, default: '' },
  /** Override the text. */
  label: { type: String, default: '' },
  uppercase: { type: Boolean, default: true },
})

const lampState = computed(() => props.state || orderStatusState(props.status))
const text = computed(() => props.label || orderStatusLabel(props.status))
</script>

<template>
  <span class="lamp" :class="{ 'lamp--upper': uppercase }">
    <span class="status-light" :data-state="lampState" />
    <span class="lamp__text">{{ text }}</span>
  </span>
</template>

<style scoped>
.lamp {
  display: inline-flex;
  align-items: center;
  gap: 0.4375rem;
  font-family: var(--font-terminal);
  font-size: 0.625rem;
  letter-spacing: 0.1em;
  white-space: nowrap;
}

.lamp--upper .lamp__text {
  text-transform: uppercase;
}

/* The pending lamp is the only one that pulses — it is a queue that wants
   attention, not a state that simply is. */
.lamp .status-light[data-state='warn'] {
  animation: lamp-blink 2.4s steps(2, end) infinite;
}

@keyframes lamp-blink {
  50% {
    opacity: 0.35;
  }
}

@media (prefers-reduced-motion: reduce) {
  .lamp .status-light[data-state='warn'] {
    animation: none;
  }
}
</style>
