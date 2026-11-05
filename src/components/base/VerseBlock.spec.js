import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import VerseBlock from './VerseBlock.vue'

describe('VerseBlock', () => {
  it('carries the couplet exactly, both hemistichs', () => {
    // The point of the component: the text is asserted in one place, so a
    // stray edit to a classical verse cannot pass unnoticed.
    const text = mount(VerseBlock).text()
    expect(text).toContain('پیشِ بالایت، به بالایت فروریزم گهر')
    expect(text).toContain('زآنکه صد نوبر مرا زآن یک صِنوبَر، ساختند')
  })

  it('keeps the pun intact — نوبر against صنوبر', () => {
    // If either word were lost to a typo the verse would still scan but the
    // reason it is on this site would be gone.
    const second = mount(VerseBlock).findAll('.verse__line')[1].text()
    expect(second).toContain('نوبر')
    expect(second).toContain('صِنوبَر')
  })

  it('attributes the verse to Khaqani', () => {
    expect(mount(VerseBlock).find('.verse__by').text()).toBe('خاقانی')
  })

  it('sets each hemistich as its own line, never re-wrapped into prose', () => {
    expect(mount(VerseBlock).findAll('.verse__line')).toHaveLength(2)
  })

  it('marks it up as a quotation with an attribution', () => {
    const wrapper = mount(VerseBlock)
    expect(wrapper.find('figure blockquote').exists()).toBe(true)
    expect(wrapper.find('figure figcaption').exists()).toBe(true)
  })

  it('offers the sunk variant for a recessed panel', () => {
    expect(mount(VerseBlock).find('figure').classes()).toContain('verse--paper')
    expect(
      mount(VerseBlock, { props: { variant: 'sunk' } }).find('figure').classes(),
    ).toContain('verse--sunk')
  })

  it('rejects a variant it has no styling for', () => {
    const { validator } = VerseBlock.props.variant
    expect(validator('sunk')).toBe(true)
    expect(validator('terminal')).toBe(false)
  })
})
