<script setup>
import { computed } from 'vue'

const props = defineProps({
  /** primary = accent fill. secondary = paper fill. ghost = no shadow, rule only. danger = error fill. */
  variant: {
    type: String,
    default: 'primary',
    validator: (v) => ['primary', 'secondary', 'ghost', 'danger'].includes(v),
  },
  size: {
    type: String,
    default: 'md',
    validator: (v) => ['sm', 'md', 'lg'].includes(v),
  },
  /** Renders for the Terminal register: shadows and borders cast in light. */
  inverse: { type: Boolean, default: false },
  block: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  /** Renders as <a> when set. */
  href: { type: String, default: null },
  type: { type: String, default: 'button' },
})

const isDisabled = computed(() => props.disabled || props.loading)

const tag = computed(() => (props.href ? 'a' : 'button'))

const attrs = computed(() =>
  props.href
    ? { href: isDisabled.value ? undefined : props.href, role: 'button', 'aria-disabled': isDisabled.value || undefined }
    : { type: props.type, disabled: isDisabled.value },
)
</script>

<template>
  <component
    :is="tag"
    v-bind="attrs"
    class="sb-btn"
    :class="[
      `sb-btn--${variant}`,
      `sb-btn--${size}`,
      { 'sb-btn--inverse': inverse, 'sb-btn--block': block, 'sb-btn--disabled': isDisabled },
    ]"
  >
    <span v-if="loading" class="sb-btn__spinner" aria-hidden="true" />
    <slot name="icon" />
    <span class="sb-btn__label"><slot /></span>
  </component>
</template>

<style scoped>
/* ==========================================================================
   BaseButton — Senobar
   Physics: 3px ink border, hard 6px offset shadow, square corners.
   On :active the button travels the full shadow offset and the shadow is
   removed, so it lands flush on the surface. No blur, ever.
   ========================================================================== */

.sb-btn {
  --sb-offset: 6px;
  /* Ink, not the green the panels now cast: the primary button is already a
     green fill, and a green shadow under it would merge with the button and
     lose the edge that makes the press read. */
  --sb-shadow-color: var(--ink);
  --sb-border-color: var(--ink);

  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;

  border: 3px solid var(--sb-border-color);
  border-radius: 0;
  box-shadow: var(--sb-offset) var(--sb-offset) 0 var(--sb-shadow-color);

  font-family: var(--font-terminal, "Morabba", sans-serif);
  text-transform: uppercase;
  letter-spacing: 0.14em;
  font-weight: 500;
  text-decoration: none;
  white-space: nowrap;

  cursor: pointer;
  user-select: none;
  -webkit-tap-highlight-color: transparent;
  transition:
    transform 90ms cubic-bezier(0.2, 0, 0, 1),
    box-shadow 90ms cubic-bezier(0.2, 0, 0, 1);
}

/* --- Sizes. Offset scales with the button so the physics stay proportional. */
.sb-btn--sm {
  --sb-offset: 3px;
  padding: 0.375rem 0.75rem;
  font-size: 0.625rem;
}
.sb-btn--md {
  --sb-offset: 6px;
  padding: 0.625rem 1.25rem;
  font-size: 0.6875rem;
}
.sb-btn--lg {
  --sb-offset: 6px;
  padding: 0.9375rem 2rem;
  font-size: 0.8125rem;
}

.sb-btn--block {
  display: flex;
  width: 100%;
}

/* --- Variants. Flat fills only. -------------------------------------------- */
.sb-btn--primary {
  background-color: var(--accent);
  color: var(--paper);
}

.sb-btn--secondary {
  background-color: var(--paper);
  color: var(--ink);
}

.sb-btn--danger {
  background-color: #a33224;
  color: var(--paper);
}

/* Ghost carries no shadow, so it must not travel on press either. */
.sb-btn--ghost {
  background-color: transparent;
  color: var(--ink);
  box-shadow: none;
}

/* --- Terminal register ----------------------------------------------------- */
.sb-btn--inverse {
  --sb-shadow-color: var(--terminal-text);
  --sb-border-color: var(--terminal-text);
}
.sb-btn--inverse.sb-btn--secondary {
  background-color: var(--terminal);
  color: var(--terminal-text);
}
.sb-btn--inverse.sb-btn--ghost {
  color: var(--terminal-text);
}

/* --- Hover: lift away from the surface, shadow grows. ---------------------- */
@media (hover: hover) {
  .sb-btn:not(.sb-btn--disabled):not(.sb-btn--ghost):hover {
    transform: translate(-2px, -2px);
    box-shadow: calc(var(--sb-offset) + 2px) calc(var(--sb-offset) + 2px) 0 var(--sb-shadow-color);
  }
  .sb-btn--ghost:not(.sb-btn--disabled):hover {
    background-color: var(--paper-sunk);
  }
  .sb-btn--inverse.sb-btn--ghost:not(.sb-btn--disabled):hover {
    background-color: var(--terminal-raised);
  }
}

/* --- Active: travel the full offset, shadow removed. ----------------------- */
.sb-btn:not(.sb-btn--disabled):not(.sb-btn--ghost):active {
  transform: translate(var(--sb-offset), var(--sb-offset));
  box-shadow: 0 0 0 var(--sb-shadow-color);
}
.sb-btn--ghost:not(.sb-btn--disabled):active {
  transform: translate(1px, 1px);
}

.sb-btn:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: 3px;
}
.sb-btn--primary:focus-visible {
  outline-color: var(--ink);
}
.sb-btn--inverse.sb-btn--primary:focus-visible {
  outline-color: var(--terminal-text);
}

/* --- Disabled: flattened, no shadow, no travel. ---------------------------- */
.sb-btn--disabled {
  box-shadow: none;
  opacity: 0.45;
  cursor: not-allowed;
  pointer-events: none;
}

.sb-btn__label {
  display: inline-block;
}

/* Square spinner — a rotating outline, no arcs, no blur. */
.sb-btn__spinner {
  width: 0.6875em;
  height: 0.6875em;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-bottom-color: transparent;
  animation: sb-spin 700ms steps(8, end) infinite;
  flex: none;
}

@keyframes sb-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .sb-btn {
    transition: none;
  }
  .sb-btn__spinner {
    animation-duration: 2s;
  }
}
</style>
