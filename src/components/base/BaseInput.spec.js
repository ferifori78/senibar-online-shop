import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import BaseInput from './BaseInput.vue'

/** Type into the field the way a Persian keyboard does. */
async function type(wrapper, value) {
  const input = wrapper.find('input')
  input.element.value = value
  await input.trigger('input')
  return input
}

/** The last value the field emitted upward. */
function emitted(wrapper) {
  const events = wrapper.emitted('update:modelValue')
  return events?.[events.length - 1]?.[0]
}

describe('BaseInput digit handling', () => {
  it('passes the value through untouched by default', async () => {
    const wrapper = mount(BaseInput)
    await type(wrapper, '۱۲۳')
    expect(emitted(wrapper)).toBe('۱۲۳')
  })

  it('converts a Persian phone number to ASCII', async () => {
    const wrapper = mount(BaseInput, { props: { digits: 'strict' } })
    await type(wrapper, '۰۹۱۲۳۴۵۶۷۸۹')
    expect(emitted(wrapper)).toBe('09123456789')
  })

  it('rewrites the visible field, not only the model', async () => {
    // Vue skips the re-render when the model is unchanged, so without this the
    // Persian text stays on screen while ASCII is sent.
    const wrapper = mount(BaseInput, { props: { digits: 'strict' } })
    const input = await type(wrapper, '۱۲۳۴')
    expect(input.element.value).toBe('1234')
  })

  it('strips separators from a strict field', async () => {
    const wrapper = mount(BaseInput, { props: { digits: 'strict' } })
    await type(wrapper, '0912 345 6789')
    expect(emitted(wrapper)).toBe('09123456789')
  })

  it('keeps the surrounding text in a loose field', async () => {
    const wrapper = mount(BaseInput, { props: { digits: 'loose' } })
    await type(wrapper, 'خیابان ولیعصر، پلاک ۱۲')
    expect(emitted(wrapper)).toBe('خیابان ولیعصر، پلاک 12')
  })

  it('lays a strict field out left to right, so a phone number reads forward', () => {
    const wrapper = mount(BaseInput, { props: { digits: 'strict' } })
    expect(wrapper.find('input').classes()).toContain('sb-field__input--digits')
  })

  it('forwards inputmode, so the numeric keypad opens on a phone', () => {
    const wrapper = mount(BaseInput, { props: { inputmode: 'tel' } })
    expect(wrapper.find('input').attributes('inputmode')).toBe('tel')
  })
})
