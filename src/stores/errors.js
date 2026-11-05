import { parseApiError } from '@/api/client'

/** What parseApiError yields when the server sent nothing usable. A caller's
 *  own fallback is always more actionable than this, so it wins. */
const GENERIC = 'خطای ناشناخته.'

/** Build the error pair every admin store keeps: a sentence and a field map.
 *
 *  Shared rather than copied so a fix to the fallback rule lands everywhere
 *  at once.
 */
/**
 * @param error         ref holding the sentence shown at the top of a screen
 * @param fieldErrors   ref holding the per-field map, for forms that render
 *                      each message under its own input
 * @param options.foldFieldErrors
 *   When the caller has no per-field UI, set this so a DRF validation error —
 *   which arrives under its field name with an empty `message` — is promoted
 *   into the banner instead of being replaced by a generic fallback. Those
 *   sentences ("400g is reserved; stock cannot go below that") are the only
 *   text that tells the user what to do. Leave it off where the form already
 *   shows field errors inline, or the same words appear twice.
 */
export function useApiErrors(error, fieldErrors, { foldFieldErrors = false } = {}) {
  function capture(err, fallback) {
    const parsed = parseApiError(err)

    if (parsed.message && parsed.message !== GENERIC) {
      error.value = parsed.message
    } else if (foldFieldErrors) {
      const specific = Object.values(parsed.fields).filter(Boolean)
      error.value = specific.length ? specific.join(' ') : fallback || parsed.message
    } else {
      error.value = fallback || parsed.message
    }

    fieldErrors.value = parsed.fields
    return parsed
  }

  function reset() {
    error.value = ''
    fieldErrors.value = {}
  }

  return { capture, reset }
}
