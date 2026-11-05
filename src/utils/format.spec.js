import { describe, expect, it } from 'vitest'

import { RIAL_PER_TOMAN, formatPrice, formatRial } from './format'

/** Persian digits back to ASCII, so assertions read plainly. */
function ascii(text) {
  return text.replace(/[۰-۹]/g, (d) => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d)).replace(/٬/g, ',')
}

describe('formatPrice', () => {
  it('converts rial to toman for display', () => {
    // The shop stores and charges rial; customers read toman.
    expect(ascii(formatPrice(1200000))).toBe('120,000 تومان')
  })

  it('does not show a rial figure under a toman label', () => {
    // The bug this guards: 1,200,000 rial rendered as "1,200,000 تومان",
    // which read like a tenfold overcharge on a correctly-charged order.
    expect(ascii(formatPrice(1200000))).not.toBe('1,200,000 تومان')
  })

  it('keeps the shipping table honest', () => {
    // 150,000 rial is 15,000 toman — a plausible postage charge. Read as
    // toman it would be 150,000, which is not.
    expect(ascii(formatPrice(150000))).toBe('15,000 تومان')
  })

  it('rounds away stray rial rather than showing a fraction', () => {
    expect(ascii(formatPrice(1200005))).toBe('120,001 تومان')
  })

  it('handles zero and free shipping', () => {
    expect(ascii(formatPrice(0))).toBe('0 تومان')
  })

  it('renders a dash for a missing amount', () => {
    expect(formatPrice(null)).toBe('—')
    expect(formatPrice(undefined)).toBe('—')
    expect(formatPrice('')).toBe('—')
  })

  it('accepts the string decimals DRF serialises', () => {
    expect(ascii(formatPrice('1200000'))).toBe('120,000 تومان')
  })
})

describe('formatRial', () => {
  it('shows the figure the gateway will actually charge, unconverted', () => {
    expect(ascii(formatRial(1200000))).toBe('1,200,000 ریال')
  })
})

describe('RIAL_PER_TOMAN', () => {
  it('is ten', () => {
    // Stated once so a future change has a single place to happen.
    expect(RIAL_PER_TOMAN).toBe(10)
  })
})
