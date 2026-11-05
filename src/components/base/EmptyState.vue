<script setup>
import { computed } from 'vue'

/**
 * The Senobar empty state.
 *
 * A framed slab with a linear SVG mark, a monospace headline, and a sentence
 * in the register's own voice. No emoji, no illustration — the icon is drawn
 * in strokes like every other icon in the system.
 */
const props = defineProps({
  /** Which mark to draw. */
  icon: {
    type: String,
    default: 'bean',
    validator: (v) => ['bean', 'box', 'ticket', 'search', 'inbox', 'error'].includes(v),
  },
  /** Monospace headline, uppercase. Kept short. */
  code: { type: String, default: 'NOTHING HERE' },
  /** A sentence explaining what happened, in Persian. */
  message: { type: String, default: '' },
  /** Terminal register. */
  inverse: { type: Boolean, default: false },
  /** Reduces padding, for use inside a panel. */
  compact: { type: Boolean, default: false },
  /** Draws the frame in the error colour. */
  tone: {
    type: String,
    default: 'neutral',
    validator: (v) => ['neutral', 'error'].includes(v),
  },
})

const classes = computed(() => [
  { 'empty--inverse': props.inverse, 'empty--compact': props.compact },
  `empty--${props.tone}`,
])
</script>

<template>
  <div class="empty" :class="classes" role="status">
    <span class="empty__mark" aria-hidden="true">
      <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.5"
           stroke-linecap="square">
        <!-- A coffee bean: the outline and its centre crease. -->
        <template v-if="icon === 'bean'">
          <ellipse cx="24" cy="24" rx="13" ry="18" transform="rotate(-35 24 24)" />
          <path d="M15 33C20 28 28 20 33 15" />
        </template>

        <!-- An open, empty carton. -->
        <template v-else-if="icon === 'box'">
          <path d="M8 18h32v22H8z" />
          <path d="M8 18l5-8h22l5 8" />
          <path d="M20 18v6h8v-6" />
        </template>

        <!-- A ticket stub, notched on both edges. -->
        <template v-else-if="icon === 'ticket'">
          <path d="M6 14h36v7a3 3 0 0 0 0 6v7H6v-7a3 3 0 0 0 0-6v-7Z" />
          <path d="M17 18v12" stroke-dasharray="3 3" />
        </template>

        <!-- A magnifier over nothing. -->
        <template v-else-if="icon === 'search'">
          <circle cx="21" cy="21" r="12" />
          <path d="M30 30l10 10" />
          <path d="M15 21h12" />
        </template>

        <!-- An empty tray. -->
        <template v-else-if="icon === 'inbox'">
          <path d="M7 26h10l3 6h8l3-6h10" />
          <path d="M7 26l6-16h22l6 16v12H7V26Z" />
        </template>

        <!-- A broken frame: something went wrong. -->
        <template v-else>
          <path d="M10 10h28v28H10z" />
          <path d="M18 18l12 12M30 18L18 30" />
        </template>
      </svg>
    </span>

    <p class="empty__code">{{ code }}</p>
    <p v-if="message" class="empty__message">{{ message }}</p>

    <div v-if="$slots.default" class="empty__action">
      <slot />
    </div>
  </div>
</template>

<style scoped>
/* ==========================================================================
   EmptyState — both registers
   ========================================================================== */

.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 0.875rem;

  border: 3px dashed var(--rule);
  padding: clamp(2.5rem, 7vw, 4rem) 1.5rem;
}

.empty--compact {
  padding: 2rem 1.25rem;
  gap: 0.625rem;
}

.empty--error {
  border-style: solid;
  border-color: #a33224;
}

/* The mark is drawn in the rule colour — present, but not competing with the
   action beneath it. */
.empty__mark {
  display: inline-flex;
  color: var(--rule);
}

.empty__mark svg {
  width: clamp(2.75rem, 7vw, 3.5rem);
  height: clamp(2.75rem, 7vw, 3.5rem);
}

.empty--error .empty__mark {
  color: #a33224;
}

.empty__code {
  font-family: var(--font-terminal);
  font-size: 0.75rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  font-weight: 500;
  color: var(--ink);
  margin: 0;
}

.empty--error .empty__code {
  color: #a33224;
}

.empty__message {
  font-family: var(--font-editorial);
  font-size: 1rem;
  line-height: 1.7;
  color: var(--ink-muted);
  max-width: 26rem;
  margin: 0;
}

.empty__action {
  margin-top: 0.625rem;
}

/* --- Terminal register ----------------------------------------------------- */
.empty--inverse {
  border-color: var(--terminal-rule);
}

.empty--inverse .empty__mark {
  color: var(--terminal-rule);
}

.empty--inverse .empty__code {
  color: var(--terminal-text);
}

.empty--inverse .empty__message {
  font-family: var(--font-terminal);
  font-size: 0.6875rem;
  color: var(--terminal-dim);
}
</style>
