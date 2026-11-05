import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import GrindSelector from './GrindSelector.vue'
import { GRIND_METHODS } from '@/utils/format'

function mountSelector(props = {}) {
  return mount(GrindSelector, { props: { modelValue: 'whole', ...props } })
}

describe('GrindSelector', () => {
  it('renders one tile per grind method with an SVG icon and no emoji', () => {
    const wrapper = mountSelector()
    const tiles = wrapper.findAll('[role="radio"]')

    expect(tiles).toHaveLength(GRIND_METHODS.length)
    expect(wrapper.findAll('svg')).toHaveLength(GRIND_METHODS.length)
    // Design rule 2: nothing outside the Basic Multilingual plane, and no
    // pictographs. Persian text and ASCII only.
    expect(wrapper.text()).not.toMatch(/\p{Extended_Pictographic}/u)
  })

  it('marks exactly one option as checked', () => {
    const wrapper = mountSelector({ modelValue: 'v60' })
    const checked = wrapper.findAll('[aria-checked="true"]')

    expect(checked).toHaveLength(1)
    expect(checked[0].text()).toContain('وی۶۰')
  })

  it('emits the chosen method on click', async () => {
    const wrapper = mountSelector()
    const espresso = wrapper.findAll('[role="radio"]')[6]

    await espresso.trigger('click')

    expect(wrapper.emitted('update:modelValue')[0]).toEqual(['espresso'])
  })

  it('disables unavailable methods and refuses to select them', async () => {
    const wrapper = mountSelector({ unavailable: ['espresso', 'turkish'] })
    const tiles = wrapper.findAll('[role="radio"]')
    const espresso = tiles[6]

    expect(espresso.attributes('disabled')).toBeDefined()
    await espresso.trigger('click')
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })

  it('walks the grid with arrow keys', async () => {
    const wrapper = mountSelector({ modelValue: 'whole' })
    const first = wrapper.findAll('[role="radio"]')[0]

    // ArrowLeft advances in RTL reading order.
    await first.trigger('keydown', { key: 'ArrowLeft' })
    expect(wrapper.emitted('update:modelValue')[0]).toEqual(['french_press'])

    // ArrowDown jumps a row of four.
    await first.trigger('keydown', { key: 'ArrowDown' })
    expect(wrapper.emitted('update:modelValue')[1]).toEqual(['aeropress'])
  })

  it('skips disabled options when navigating by keyboard', async () => {
    // moka_pot is index 5; espresso (6) is disabled, so ArrowLeft must land on
    // turkish (7) rather than stopping on a disabled tile.
    const wrapper = mountSelector({ modelValue: 'moka_pot', unavailable: ['espresso'] })
    const moka = wrapper.findAll('[role="radio"]')[5]

    await moka.trigger('keydown', { key: 'ArrowLeft' })

    expect(wrapper.emitted('update:modelValue')[0]).toEqual(['turkish'])
  })

  it('keeps only the selected tile in the tab order', () => {
    const wrapper = mountSelector({ modelValue: 'v60' })
    const tabbable = wrapper
      .findAll('[role="radio"]')
      .filter((tile) => tile.attributes('tabindex') === '0')

    expect(tabbable).toHaveLength(1)
    expect(tabbable[0].attributes('aria-checked')).toBe('true')
  })
})
