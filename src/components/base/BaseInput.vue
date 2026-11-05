<script setup>
import { computed, useId } from 'vue'

import { digitsOnly, toEnglishDigits } from '@/utils/digits'

const props = defineProps({
  label: { type: String, default: '' },
  type: { type: String, default: 'text' },
  modelValue: { type: [String, Number], default: '' },
  placeholder: { type: String, default: '' },
  hint: { type: String, default: '' },
  error: { type: String, default: '' },
  required: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  autocomplete: { type: String, default: null },
  /** Hints the phone/number keypad on mobile. */
  inputmode: { type: String, default: null },
  /** How to treat non-ASCII digits typed into this field.
   *
   *  `'strict'` keeps digits and nothing else — postal codes, phone numbers.
   *  `'loose'` converts Persian digits but keeps the rest, for fields where a
   *  number sits inside text, such as a street address with a plate number.
   *  The default leaves the value untouched. */
  digits: {
    type: String,
    default: '',
    validator: (v) => ['', 'strict', 'loose'].includes(v),
  },
  /** Renders for the Terminal register. */
  inverse: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

/** Normalize before the value leaves the field, so the model, the validators
 *  and the request all see ASCII — and the person typing sees the correction
 *  happen under the cursor rather than at submit. */
function onInput(event) {
  const raw = event.target.value
  let value = raw
  if (props.digits === 'strict') value = digitsOnly(raw)
  else if (props.digits === 'loose') value = toEnglishDigits(raw)

  // Vue will not re-render an unchanged model value, so a rejected character
  // would otherwise stay visible in the DOM.
  if (value !== raw) event.target.value = value
  emit('update:modelValue', value)
}

const id = useId()
const describedBy = computed(() => {
  const ids = []
  if (props.error) ids.push(`${id}-error`)
  else if (props.hint) ids.push(`${id}-hint`)
  return ids.join(' ') || undefined
})
</script>

<template>
  <div class="sb-field" :class="{ 'sb-field--inverse': inverse }">
    <label v-if="label" class="sb-field__label" :for="id">
      {{ label }}<span v-if="required" class="sb-field__required" aria-hidden="true">*</span>
    </label>

    <input
      :id="id"
      class="sb-field__input"
      :class="{ 'sb-field__input--error': error, 'sb-field__input--digits': digits === 'strict' }"
      :type="type"
      :value="modelValue"
      :placeholder="placeholder"
      :required="required"
      :disabled="disabled"
      :autocomplete="autocomplete"
      :inputmode="inputmode"
      :aria-invalid="error ? 'true' : undefined"
      :aria-describedby="describedBy"
      @input="onInput"
    />

    <p v-if="error" :id="`${id}-error`" class="sb-field__error" role="alert">{{ error }}</p>
    <p v-else-if="hint" :id="`${id}-hint`" class="sb-field__hint">{{ hint }}</p>
  </div>
</template>

<style scoped>
/* ==========================================================================
   BaseInput — Senobar
   3px ink rule, square, mono uppercase label. The field sinks into its own
   shadow on focus, the inverse of the button's press.
   ========================================================================== */

.sb-field {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.sb-field__label {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-weight: 500;
  color: var(--ink);
}

.sb-field__required {
  color: var(--accent);
  margin-inline-start: 0.25rem;
}

.sb-field__input {
  border: 3px solid var(--ink);
  border-radius: 0;
  background-color: var(--paper);
  color: var(--ink);
  padding: 0.75rem 0.875rem;
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.875rem;
  width: 100%;
  transition: box-shadow 90ms cubic-bezier(0.2, 0, 0, 1);
}

/* A bare run of digits in an RTL field is laid out right-to-left by the bidi
   algorithm, so 09121234567 reads back to front. Force the direction, and keep
   the text against the same edge as every other field in the form. */
.sb-field__input--digits {
  direction: ltr;
  text-align: right;
}

.sb-field__input::placeholder {
  color: var(--ink-muted);
  opacity: 1;
}

/* Focus lands the field on a hard shadow — no glow, no ring blur. */
.sb-field__input:focus {
  outline: none;
  box-shadow: 4px 4px 0 var(--accent);
}

.sb-field__input--error {
  border-color: #a33224;
}
.sb-field__input--error:focus {
  box-shadow: 4px 4px 0 #a33224;
}

.sb-field__input:disabled {
  background-color: var(--paper-sunk);
  color: var(--ink-muted);
  cursor: not-allowed;
}

.sb-field__hint,
.sb-field__error {
  font-family: var(--font-terminal, "Morabba", sans-serif);
  font-size: 0.6875rem;
  letter-spacing: 0.06em;
  margin: 0;
}

.sb-field__hint {
  color: var(--ink-muted);
}
.sb-field__error {
  color: #a33224;
  font-weight: 500;
}

/* --- Terminal register ----------------------------------------------------- */
.sb-field--inverse .sb-field__label {
  color: var(--terminal-text);
}
.sb-field--inverse .sb-field__input {
  border-color: var(--terminal-text);
  background-color: var(--terminal);
  color: var(--terminal-text);
}
.sb-field--inverse .sb-field__input::placeholder {
  color: var(--terminal-dim);
}
.sb-field--inverse .sb-field__hint {
  color: var(--terminal-dim);
}

@media (prefers-reduced-motion: reduce) {
  .sb-field__input {
    transition: none;
  }
}
</style>
