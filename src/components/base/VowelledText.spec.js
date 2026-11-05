import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import VowelledText from './VowelledText.vue'

const SENOBAR = 'صِنوبَر'

describe('VowelledText', () => {
  it('keeps the text intact, marks included', () => {
    // The whole point is scaling the marks without losing them: the word must
    // still copy, search and read to a screen reader as one vowelled word.
    expect(mount(VowelledText, { props: { text: SENOBAR } }).text()).toBe(SENOBAR)
  })

  it('wraps each mark so it can be sized on its own', () => {
    // صِنوبَر carries a kasra under the ص and a fatha over the ب.
    const marks = mount(VowelledText, {
      props: { text: SENOBAR, face: 'editorial' },
    }).findAll('.vow__mark')
    expect(marks).toHaveLength(2)
    expect(marks.map((m) => m.text())).toEqual(['ِ', 'َ'])
  })

  it('applies the scale to the marks only', () => {
    const wrapper = mount(VowelledText, {
      props: { text: SENOBAR, scale: 1.4, face: 'editorial' },
    })
    expect(wrapper.find('.vow__mark').attributes('style')).toContain('1.4em')
  })

  it('caps the scale where the marks would leave their letters', () => {
    // Measured in a browser: past ~1.5x the font's proportional offset walks
    // the mark off its letter and it floats above the line. Asking for more
    // must clamp rather than render the broken form.
    const wrapper = mount(VowelledText, {
      props: { text: SENOBAR, scale: 3, face: 'editorial' },
    })
    expect(wrapper.find('.vow__mark').attributes('style')).toContain('1.5em')
  })

  it('does not split the text at all on the display face', () => {
    // THE bug this pins. A combining mark is positioned by the shaper relative
    // to the glyph it follows; wrapping it in its own element takes it out of
    // that run, and the browser can then only place it at the boundary between
    // two letters. In Morabba the fatha of صِنوبَر landed between the ب and the
    // ر instead of above the ب, and no vertical offset could fix it — raising
    // the mark just walked it up the wrong column and off the word.
    //
    // Morabba places its own harakat correctly, so the fix is to do nothing.
    const wrapper = mount(VowelledText, {
      props: { text: SENOBAR, scale: 1.5, face: 'display' },
    })
    expect(wrapper.findAll('.vow__mark')).toHaveLength(0)
    expect(wrapper.text()).toBe(SENOBAR)
  })

  it('keeps the word in one shaping run whatever scale is asked for', () => {
    // A caller passing a large scale must not be able to reintroduce the
    // split — the mark positions matter more than the mark size.
    const html = mount(VowelledText, {
      props: { text: SENOBAR, scale: 3, face: 'display' },
    }).html()
    expect(html).not.toContain('vow__mark')
    expect(html).toContain(SENOBAR)
  })

  it('defaults to the face the site is actually set in', () => {
    // Morabba sets the whole site, so a caller that names no face must get
    // its behaviour — untouched text, not Vazirmatn's splitting.
    const wrapper = mount(VowelledText, { props: { text: SENOBAR, scale: 1.5 } })
    expect(wrapper.findAll('.vow__mark')).toHaveLength(0)
    expect(wrapper.text()).toBe(SENOBAR)
  })

  it('falls back to the editorial face for an unknown one', () => {
    const wrapper = mount(VowelledText, {
      props: { text: SENOBAR, scale: 1.5, face: 'nonesuch' },
    })
    expect(wrapper.find('.vow__mark').attributes('style')).toContain('1.5em')
  })

  it('nudges each mark by its own side, not one value for both', () => {
    // The font sets a kasra much tighter to its letter than a fatha, so one
    // shared offset leaves the two at visibly different distances.
    const marks = mount(VowelledText, {
      props: { text: SENOBAR, scale: 1.5, face: 'editorial' },
    }).findAll('.vow__mark')
    const style = (m) => m.attributes('style')

    expect(style(marks[0])).toContain('vertical-align')
    expect(style(marks[1])).toContain('vertical-align')
    // The kasra (below, first in the word) and the fatha do not share a value.
    expect(style(marks[0])).not.toBe(style(marks[1]))
  })

  it('moves the nudge with the scale, since the drift does', () => {
    // A mark drifts further from its letter the larger it is drawn, so a
    // fixed offset can only be right at one scale. Measured on rendered
    // pixels: at 1.5 the correction above is ~-0.25em, at 1.0 about zero.
    const offset = (scale, i) =>
      mount(VowelledText, { props: { text: SENOBAR, scale, face: 'editorial' } })
        .findAll('.vow__mark')
        [i].attributes('style')
        .match(/vertical-align:\s*(-?[\d.]+)em/)[1]

    expect(Number(offset(1.5, 1))).toBeLessThan(Number(offset(1.0, 1)))
    // The mark below moves the other way: the font sets it too tight, so
    // enlarging it needs less pushing away, not more.
    expect(Number(offset(1.5, 0))).toBeGreaterThan(Number(offset(1.0, 0)))
  })

  it('leaves the letters in unbroken runs so the cursive joining survives', () => {
    // One span per letter would render Persian as disconnected isolated forms.
    // The letters between two marks must stay in a single text node.
    const html = mount(VowelledText, { props: { text: SENOBAR } }).html()
    expect(html).toContain('نوب')
  })

  it('renders text with no marks unchanged', () => {
    const wrapper = mount(VowelledText, { props: { text: 'قهوه' } })
    expect(wrapper.text()).toBe('قهوه')
    expect(wrapper.findAll('.vow__mark')).toHaveLength(0)
  })

  it('handles a mark at the very end of the string', () => {
    // The trailing-buffer branch: a mark last means no plain run follows it.
    const wrapper = mount(VowelledText, {
      props: { text: 'صِ', face: 'editorial' },
    })
    expect(wrapper.text()).toBe('صِ')
    expect(wrapper.findAll('.vow__mark')).toHaveLength(1)
  })

  it('covers the harakat a Persian text actually uses', () => {
    const all = 'اًٌٍَُِّْ'
    const wrapper = mount(VowelledText, { props: { text: all, face: 'editorial' } })
    expect(wrapper.findAll('.vow__mark')).toHaveLength(all.length - 1)
  })
})
