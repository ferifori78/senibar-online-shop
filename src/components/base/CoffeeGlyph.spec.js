import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import CoffeeGlyph from './CoffeeGlyph.vue'

const NAMES = ['bean', 'cherry', 'dripper', 'moka', 'cup', 'portafilter', 'grinder', 'scale']

describe('CoffeeGlyph', () => {
  it('renders a distinct drawing for every name', () => {
    // The v-if/v-else chain is easy to break with a typo, which would silently
    // fall through to the final `v-else` and draw a scale for everything.
    const drawings = NAMES.map((name) => mount(CoffeeGlyph, { props: { name } }).html())
    expect(new Set(drawings).size).toBe(NAMES.length)
  })

  it('draws in line only, so the plate stays line work', () => {
    for (const name of NAMES) {
      const svg = mount(CoffeeGlyph, { props: { name } }).find('svg')
      expect(svg.attributes('fill')).toBe('none')
      expect(svg.attributes('stroke')).toBe('currentColor')
    }
  })

  it('shares one frame across the set, so the glyphs sit at one scale', () => {
    for (const name of NAMES) {
      expect(mount(CoffeeGlyph, { props: { name } }).find('svg').attributes('viewBox')).toBe(
        '0 0 32 32',
      )
    }
  })

  it('is hidden from screen readers — the label beside it carries the meaning', () => {
    expect(mount(CoffeeGlyph, { props: { name: 'bean' } }).find('svg').attributes('aria-hidden')).toBe(
      'true',
    )
  })

  it('rejects a name it has no drawing for', () => {
    const { validator } = CoffeeGlyph.props.name
    expect(validator('bean')).toBe(true)
    expect(validator('teapot')).toBe(false)
  })
})
