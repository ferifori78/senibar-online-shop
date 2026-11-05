import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import StatusLamp from './StatusLamp.vue'

describe('StatusLamp', () => {
  it('maps an order status to a lamp colour and Persian label', () => {
    const wrapper = mount(StatusLamp, { props: { status: 'roasting' } })

    expect(wrapper.find('.status-light').attributes('data-state')).toBe('active')
    expect(wrapper.text()).toBe('در حال رست')
  })

  it('shows pending as a warning lamp — it is a queue wanting attention', () => {
    const wrapper = mount(StatusLamp, { props: { status: 'pending' } })

    expect(wrapper.find('.status-light').attributes('data-state')).toBe('warn')
  })

  it('shows delivered as green and cancelled as red', () => {
    const done = mount(StatusLamp, { props: { status: 'delivered' } })
    const dead = mount(StatusLamp, { props: { status: 'cancelled' } })

    expect(done.find('.status-light').attributes('data-state')).toBe('ok')
    expect(dead.find('.status-light').attributes('data-state')).toBe('error')
  })

  it('accepts a direct state and label instead of a status', () => {
    const wrapper = mount(StatusLamp, { props: { state: 'error', label: 'رو به اتمام' } })

    expect(wrapper.find('.status-light').attributes('data-state')).toBe('error')
    expect(wrapper.text()).toBe('رو به اتمام')
  })

  it('falls back to an idle lamp for an unknown status', () => {
    const wrapper = mount(StatusLamp, { props: { status: 'nonsense' } })

    expect(wrapper.find('.status-light').attributes('data-state')).toBe('idle')
  })

  it('always pairs the lamp with text, never colour alone', () => {
    const wrapper = mount(StatusLamp, { props: { status: 'packed' } })

    expect(wrapper.find('.status-light').exists()).toBe(true)
    expect(wrapper.find('.lamp__text').text().length).toBeGreaterThan(0)
  })

  it('uses no emoji', () => {
    const wrapper = mount(StatusLamp, { props: { status: 'shipped' } })

    expect(wrapper.text()).not.toMatch(/\p{Extended_Pictographic}/u)
  })
})
