import { digitsOnly, toEnglishDigits } from '@/utils/digits'

/** `v-digits` — normalize Persian and Arabic-Indic digits inside a raw input.
 *
 *  BaseInput has a `digits` prop for the storefront forms; this covers the
 *  back-office forms, which use bare <input> elements inside their own layout
 *  and would otherwise each need rewriting.
 *
 *  `v-digits` keeps digits only; `v-digits.loose` converts them but leaves the
 *  surrounding text, for a field where a number sits inside a sentence.
 *
 *  The listener is capturing, so it runs before v-model reads the value and
 *  the model never sees the Persian form.
 */
export const vDigits = {
  mounted(el, binding) {
    // The directive may sit on a wrapper, and <input type="number"> discards a
    // value it cannot parse before any handler sees it — so find the field and
    // take it off number, keeping the numeric keypad via inputmode.
    const input = el.tagName === 'INPUT' ? el : el.querySelector('input')
    if (!input) return

    if (input.type === 'number') {
      input.type = 'text'
      if (!input.getAttribute('inputmode')) input.setAttribute('inputmode', 'decimal')
    }

    const loose = Boolean(binding.modifiers.loose)
    // A price or a weight is written with a decimal point, so `digitsOnly`
    // would eat the separator; keep it, and let the field's own validation
    // judge the rest.
    const decimal = !loose && input.getAttribute('inputmode') === 'decimal'

    // The re-dispatch below re-enters this handler; the guard below would end
    // it on the second pass anyway, but a flag says so outright rather than
    // leaving it to be re-derived.
    let rewriting = false

    const normalize = (event) => {
      if (rewriting) return
      const raw = event.target.value
      let value
      if (loose) value = toEnglishDigits(raw)
      else if (decimal) value = toEnglishDigits(raw).replace(/[^\d.-]/g, '')
      else value = digitsOnly(raw)

      if (value === raw) return
      event.target.value = value
      // v-model listens for `input`; re-dispatching after rewriting the value
      // is what makes the model see the ASCII form.
      rewriting = true
      try {
        event.target.dispatchEvent(new Event('input', { bubbles: true }))
      } finally {
        rewriting = false
      }
    }

    input.addEventListener('input', normalize)
    el._digitsCleanup = () => input.removeEventListener('input', normalize)
  },

  unmounted(el) {
    el._digitsCleanup?.()
  },
}
