<script setup>
import { formatPrice, formatWeight } from '@/utils/format'

defineProps({
  modelValue: { type: Number, default: 250 },
  /** [{ weight_grams, price }] straight from the product's price_options. */
  options: { type: Array, required: true },
  label: { type: String, default: 'وزن' },
})

defineEmits(['update:modelValue'])
</script>

<template>
  <fieldset class="weight">
    <legend class="weight__legend">{{ label }}</legend>

    <div class="weight__row" role="radiogroup" :aria-label="label">
      <button
        v-for="option in options"
        :key="option.weight_grams"
        type="button"
        role="radio"
        class="weight__option"
        :class="{ 'weight__option--active': option.weight_grams === modelValue }"
        :aria-checked="option.weight_grams === modelValue"
        :tabindex="option.weight_grams === modelValue ? 0 : -1"
        @click="$emit('update:modelValue', option.weight_grams)"
      >
        <span class="weight__grams">{{ formatWeight(option.weight_grams) }}</span>
        <span class="weight__price">{{ formatPrice(option.price) }}</span>
      </button>
    </div>
  </fieldset>
</template>

<style scoped>
/* ==========================================================================
   WeightSelector — Editorial register
   Same physics as the grind tiles: selected fills with accent and sits flush.
   ========================================================================== */

.weight {
  border: 0;
  padding: 0;
  margin: 0;
  min-inline-size: 0;
}

.weight__legend {
  padding: 0;
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-weight: 500;
  margin-bottom: 0.875rem;
}

.weight__row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(6rem, 1fr));
  gap: 0.75rem;
}

.weight__option {
  display: flex;
  flex-direction: column;
  gap: 0.3125rem;

  border: 3px solid var(--ink);
  border-radius: 0;
  background-color: var(--paper);
  color: var(--ink);
  box-shadow: 4px 4px 0 var(--shadow);

  padding: 0.75rem 0.625rem;
  cursor: pointer;
  text-align: start;
  -webkit-tap-highlight-color: transparent;
  transition:
    transform 90ms cubic-bezier(0.2, 0, 0, 1),
    box-shadow 90ms cubic-bezier(0.2, 0, 0, 1);
}

.weight__grams {
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 1.0625rem;
  font-weight: 600;
}

.weight__price {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.625rem;
  letter-spacing: 0.08em;
  color: var(--ink-muted);
}

@media (hover: hover) {
  .weight__option:not(.weight__option--active):hover {
    transform: translate(-2px, -2px);
    box-shadow: 6px 6px 0 var(--shadow);
  }
}

.weight__option:active {
  transform: translate(4px, 4px);
  box-shadow: 0 0 0 var(--ink);
}

.weight__option--active {
  background-color: var(--accent);
  color: var(--paper);
  transform: translate(4px, 4px);
  box-shadow: 0 0 0 var(--ink);
}

.weight__option--active .weight__price {
  color: var(--paper);
  opacity: 0.85;
}

.weight__option:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: 3px;
}
.weight__option--active:focus-visible {
  outline-color: var(--ink);
}

@media (prefers-reduced-motion: reduce) {
  .weight__option {
    transition: none;
  }
}
</style>
