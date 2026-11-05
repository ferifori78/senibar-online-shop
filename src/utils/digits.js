/** Persian and Arabic-Indic digits, in value order 0-9.
 *
 *  A Persian keyboard types ۰۱۲۳; some Arabic layouts and older Android IMEs
 *  type ٠١٢٣ instead. Both look like numbers to the person entering them and
 *  neither matches \d, so a phone number typed in Persian reached the server as
 *  an empty-looking string and the form said the field was blank. */
const PERSIAN = '۰۱۲۳۴۵۶۷۸۹'
const ARABIC = '٠١٢٣٤٥٦٧٨٩'

/** Rewrite any Persian or Arabic-Indic digits as ASCII, leaving the rest of
 *  the string alone. */
export function toEnglishDigits(value) {
  if (value === null || value === undefined) return ''
  return String(value).replace(/[۰-۹٠-٩]/g, (char) => {
    const index = PERSIAN.indexOf(char)
    return String(index === -1 ? ARABIC.indexOf(char) : index)
  })
}

/** ASCII digits only — for fields that hold nothing but a number, such as a
 *  postal code or a phone number.
 *
 *  Separators are dropped rather than rejected: people paste "0912 345 6789"
 *  and "۱۲۳۴۵-۶۷۸۹۰", and silently accepting both is kinder than an error
 *  that only says the format is wrong. */
export function digitsOnly(value) {
  return toEnglishDigits(value).replace(/\D/g, '')
}
