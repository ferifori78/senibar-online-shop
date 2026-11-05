<script setup>
/**
 * One labelled block of checkboxes in the catalog filter rail.
 *
 * Every group behaves the same way — multi-select, union within the group —
 * so the rail is one repeated component rather than five near-copies that
 * drift apart. The parent owns the selection and the request; this only
 * announces which value was clicked.
 */
import { formatNumber } from '@/utils/format'

defineProps({
  label: { type: String, required: true },
  /** `{ value, label, count? }`. `count` is printed when the server sent one. */
  options: { type: Array, required: true },
  selected: { type: Array, default: () => [] },
})

defineEmits(['toggle'])
</script>

<template>
  <fieldset class="group">
    <legend class="group__label">{{ label }}</legend>

    <ul class="group__list">
      <li v-for="option in options" :key="option.value">
        <label class="opt">
          <input
            type="checkbox"
            class="opt__input"
            :checked="selected.includes(option.value)"
            @change="$emit('toggle', option.value)"
          />
          <!-- A drawn box rather than the native control: the native one
               cannot be given a 3px square border across browsers. -->
          <span class="opt__box" aria-hidden="true"></span>
          <span class="opt__text">{{ option.label }}</span>
          <!-- Persian digits, like every other number on the storefront. -->
          <span v-if="option.count != null" class="opt__count">
            {{ formatNumber(option.count) }}
          </span>
        </label>
      </li>
    </ul>
  </fieldset>
</template>

<style scoped>
.group {
  border: 0;
  padding: 0;
  margin: 0 0 1.75rem;
}

.group__label {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-weight: 500;
  color: var(--ink-muted);
  padding: 0;
  margin-bottom: 0.75rem;
}

.group__list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.opt {
  display: flex;
  /* Not centred: a two-line origin should keep its box beside the first
     line, not floating in the middle of the row. */
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.3125rem 0;
  cursor: pointer;
  font-family: var(--font-editorial, "Morabba", sans-serif);
  font-size: 0.9375rem;
  line-height: 1.4;
}

/* Visually hidden, but still the real control: it keeps keyboard focus,
   the checked state, and the label association. */
.opt__input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

.opt__box {
  flex: none;
  width: 1rem;
  height: 1rem;
  border: 3px solid var(--ink);
  border-radius: 0;
  background-color: var(--paper);
  /* Nudged down so the box lines up with the first line's text, now that the
     row aligns to the top. */
  margin-top: 0.1875rem;
}

.opt__input:checked + .opt__box {
  background-color: var(--accent);
}

.opt__input:focus-visible + .opt__box {
  outline: 3px solid var(--accent);
  outline-offset: 2px;
}

.opt__text {
  flex: 1;
}

.opt__count {
  flex: none;
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.08em;
  color: var(--ink-muted);
  /* Sits on the first line even when the label wraps to two. */
  margin-top: 0.25rem;
}
</style>
