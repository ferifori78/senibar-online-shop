import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import BrandMark from './BrandMark.vue'

describe('BrandMark', () => {
  it('renders the artwork, not a redrawn vector', () => {
    const img = mount(BrandMark).find('img')
    expect(img.attributes('src')).toBe('/logo.png')
  })

  it('offers a 2x file so the mark stays sharp on retina', () => {
    expect(mount(BrandMark).find('img').attributes('srcset')).toContain('/logo@2x.png 2x')
  })

  it('switches to the lightened artwork for the Terminal register', () => {
    // The stock green measures 2.6:1 on the panel ground and fails AA; the
    // light variant is the same mark at 6.4:1.
    const img = mount(BrandMark, { props: { light: true } }).find('img')
    expect(img.attributes('src')).toBe('/logo-light.png')
    expect(img.attributes('srcset')).toContain('/logo-light@2x.png 2x')
  })

  it('sets both dimensions so the header does not jump as the file loads', () => {
    const img = mount(BrandMark, { props: { size: 56 } }).find('img')
    expect(img.attributes('height')).toBe('56')
    expect(Number(img.attributes('width'))).toBeGreaterThan(0)
  })

  it('keeps the artwork proportions rather than squashing it to a square', () => {
    const img = mount(BrandMark, { props: { size: 100 } }).find('img')
    const ratio = Number(img.attributes('width')) / Number(img.attributes('height'))
    expect(ratio).toBeCloseTo(701 / 1084, 2)
  })

  it('is decorative: the name is announced by the link, not the image', () => {
    // The artwork spells «صنوبر», so a non-empty alt would have a screen
    // reader say the shop's name twice.
    expect(mount(BrandMark).find('img').attributes('alt')).toBe('')
  })
})
