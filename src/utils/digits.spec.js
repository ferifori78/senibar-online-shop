import { describe, expect, it } from 'vitest'

import { digitsOnly, toEnglishDigits } from './digits'

describe('toEnglishDigits', () => {
  it('converts Persian digits', () => {
    expect(toEnglishDigits('۰۹۱۲۳۴۵۶۷۸۹')).toBe('09123456789')
  })

  it('converts Arabic-Indic digits, which some Android keyboards emit', () => {
    expect(toEnglishDigits('٠١٢٣٤٥٦٧٨٩')).toBe('0123456789')
  })

  it('handles the two sets mixed in one string', () => {
    expect(toEnglishDigits('۰۹١٢٣۴۵۶۷۸۹')).toBe('09123456789')
  })

  it('leaves Persian letters alone', () => {
    expect(toEnglishDigits('خیابان ولیعصر پلاک ۱۲')).toBe('خیابان ولیعصر پلاک 12')
  })

  it('is a no-op on text that is already ASCII', () => {
    expect(toEnglishDigits('09121234567')).toBe('09121234567')
  })

  it('returns an empty string for null and undefined rather than "null"', () => {
    expect(toEnglishDigits(null)).toBe('')
    expect(toEnglishDigits(undefined)).toBe('')
  })

  it('accepts a number as well as a string', () => {
    expect(toEnglishDigits(1234)).toBe('1234')
  })
})

describe('digitsOnly', () => {
  it('strips the separators people paste into a phone number', () => {
    expect(digitsOnly('0912 345 6789')).toBe('09123456789')
    expect(digitsOnly('۱۲۳۴۵-۶۷۸۹۰')).toBe('1234567890')
  })

  it('drops the Persian thousands separator', () => {
    expect(digitsOnly('۱۲۰٬۰۰۰')).toBe('120000')
  })

  it('keeps nothing from a field holding only letters', () => {
    expect(digitsOnly('تهران')).toBe('')
  })

  it('produces a postal code that passes the checkout validator', () => {
    // The regression: this validator is /^\d{10}$/ and Persian digits failed it.
    expect(/^\d{10}$/.test(digitsOnly('۱۲۳۴۵۶۷۸۹۰'))).toBe(true)
  })
})
