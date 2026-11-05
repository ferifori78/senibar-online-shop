<script setup>
import { computed } from 'vue'

import GrindIcon from '@/components/icons/GrindIcon.vue'
import { GRIND_METHODS } from '@/utils/format'

const props = defineProps({
  modelValue: { type: String, default: 'whole' },
  /** Methods to hide, e.g. espresso on a coffee we don't roast for it. */
  unavailable: { type: Array, default: () => [] },
  label: { type: String, default: 'روش آسیاب' },
})

const emit = defineEmits(['update:modelValue'])

const methods = computed(() =>
  GRIND_METHODS.map((m) => ({ ...m, disabled: props.unavailable.includes(m.value) })),
)

const selected = computed(() => GRIND_METHODS.find((m) => m.value === props.modelValue))

function select(method) {
  if (!method.disabled) emit('update:modelValue', method.value)
}

/** Arrow keys walk the grid; the grid is a radiogroup, not a list of buttons. */
function onKeydown(event, index) {
  const keys = { ArrowRight: -1, ArrowLeft: 1, ArrowDown: 4, ArrowUp: -4 }
  const step = keys[event.key]
  if (step === undefined) return

  event.preventDefault()
  const enabled = methods.value.filter((m) => !m.disabled)
  if (!enabled.length) return

  // Walk from the current position until we land on an enabled option.
  let next = index
  for (let i = 0; i < methods.value.length; i += 1) {
    next = (next + step + methods.value.length) % methods.value.length
    if (!methods.value[next].disabled) break
  }
  emit('update:modelValue', methods.value[next].value)
}
</script>

<template>
  <fieldset class="grind">
    <legend class="grind__legend">
      {{ label }}
      <span v-if="selected" class="grind__current">{{ selected.hint }}</span>
    </legend>

    <div class="grind__grid" role="radiogroup" :aria-label="label">
      <button
        v-for="(method, index) in methods"
        :key="method.value"
        type="button"
        role="radio"
        class="grind__option"
        :class="{ 'grind__option--active': method.value === modelValue }"
        :aria-checked="method.value === modelValue"
        :disabled="method.disabled"
        :tabindex="method.value === modelValue ? 0 : -1"
        @click="select(method)"
        @keydown="onKeydown($event, index)"
      >
        <GrindIcon :method="method.value" :size="28" class="grind__icon" />
        <span class="grind__name">{{ method.label }}</span>
        <span class="grind__hint">{{ method.hint }}</span>
      </button>
    </div>

    <p class="grind__note">
      دانه کامل تازگی را بیشتر نگه می‌دارد. آسیاب فقط هنگام ارسال انجام می‌شود.
    </p>
  </fieldset>
</template>

<style scoped>
/* ==========================================================================
   GrindSelector — the Grind Configurator
   A grid of square tiles. The selected tile fills with accent and lands on
   its shadow, exactly like a pressed button that stays pressed.
   ========================================================================== */

.grind {
  border: 0;
  padding: 0;
  margin: 0;
  min-inline-size: 0; /* fieldset defaults would break the grid */
}

.grind__legend {
  display: flex;
  align-items: baseline;
  gap: 0.625rem;
  padding: 0;
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-weight: 500;
  color: var(--ink);
  margin-bottom: 0.875rem;
}

.grind__current {
  color: var(--accent);
}

.grind__grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.75rem;
}

@media (max-width: 30rem) {
  .grind__grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

/* --- Tile ------------------------------------------------------------------ */
.grind__option {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  gap: 0.4375rem;

  border: 3px solid var(--ink);
  border-radius: 0;
  background-color: var(--paper);
  color: var(--ink);
  box-shadow: 4px 4px 0 var(--shadow);

  padding: 0.875rem 0.5rem;
  cursor: pointer;
  text-align: center;
  -webkit-tap-highlight-color: transparent;
  transition:
    transform 90ms cubic-bezier(0.2, 0, 0, 1),
    box-shadow 90ms cubic-bezier(0.2, 0, 0, 1);
}

.grind__icon {
  flex: none;
}

.grind__name {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  font-weight: 500;
  line-height: 1.3;
}

.grind__hint {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.5625rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ink-muted);
}

@media (hover: hover) {
  .grind__option:not(:disabled):not(.grind__option--active):hover {
    transform: translate(-2px, -2px);
    box-shadow: 6px 6px 0 var(--shadow);
  }
}

.grind__option:not(:disabled):active {
  transform: translate(4px, 4px);
  box-shadow: 0 0 0 var(--ink);
}

/* Selected: filled with accent, sitting flush on the surface — a button that
   stayed pressed. This is the only place accent appears on this page besides
   the primary action. */
.grind__option--active {
  background-color: var(--accent);
  color: var(--paper);
  transform: translate(4px, 4px);
  box-shadow: 0 0 0 var(--ink);
}

.grind__option--active .grind__hint {
  color: var(--paper);
  opacity: 0.85;
}

.grind__option:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: 3px;
}
.grind__option--active:focus-visible {
  outline-color: var(--ink);
}

.grind__option:disabled {
  opacity: 0.35;
  cursor: not-allowed;
  box-shadow: none;
}

.grind__note {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.06em;
  line-height: 1.6;
  color: var(--ink-muted);
  margin: 0.875rem 0 0;
}

@media (prefers-reduced-motion: reduce) {
  .grind__option {
    transition: none;
  }
}
</style>
