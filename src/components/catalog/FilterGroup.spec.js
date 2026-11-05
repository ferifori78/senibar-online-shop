import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import FilterGroup from './FilterGroup.vue'

const SPECIES = [
  { value: 'arabica', label: 'عربیکا', count: 12 },
  { value: 'robusta', label: 'روبوستا', count: 3 },
  { value: 'blend', label: 'ترکیبی', count: 5 },
]

function mountGroup(props = {}) {
  return mount(FilterGroup, {
    props: { label: 'گونه', options: SPECIES, selected: [], ...props },
  })
}

describe('FilterGroup', () => {
  it('renders one checkbox per option, with the label', () => {
    const wrapper = mountGroup()
    expect(wrapper.findAll('input[type="checkbox"]')).toHaveLength(3)
    expect(wrapper.find('legend').text()).toBe('گونه')
    expect(wrapper.text()).toContain('عربیکا')
  })

  it('shows counts in Persian digits', () => {
    const wrapper = mountGroup()
    // Design rule: every number on the storefront is Persian. A raw `12` here
    // would be the one Latin numeral on the page.
    expect(wrapper.text()).toContain('۱۲')
    expect(wrapper.text()).not.toMatch(/\d/)
  })

  it('omits the count when the server did not send one', () => {
    const wrapper = mountGroup({
      options: [{ value: 'اتیوپی', label: 'اتیوپی' }],
    })
    // Origins come back as a plain list, not counted. A `0` printed beside
    // each one would read as "none in stock".
    expect(wrapper.find('.opt__count').exists()).toBe(false)
  })

  it('checks exactly the selected options', () => {
    const wrapper = mountGroup({ selected: ['arabica', 'blend'] })
    const checked = wrapper
      .findAll('input[type="checkbox"]')
      .filter((i) => i.element.checked)
    expect(checked).toHaveLength(2)
  })

  it('emits the value that was clicked, not the new list', async () => {
    const wrapper = mountGroup({ selected: ['arabica'] })
    await wrapper.findAll('input[type="checkbox"]')[1].trigger('change')
    // The parent owns the selection: it holds the store filter and decides
    // what a toggle means. This only reports which one was hit.
    expect(wrapper.emitted('toggle')[0]).toEqual(['robusta'])
  })

  it('carries no emoji', () => {
    expect(mountGroup().text()).not.toMatch(/\p{Extended_Pictographic}/u)
  })
})
