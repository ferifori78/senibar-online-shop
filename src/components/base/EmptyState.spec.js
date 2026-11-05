import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import EmptyState from './EmptyState.vue'
import LoadingState from './LoadingState.vue'

describe('EmptyState', () => {
  it('renders the monospace code and the explanatory sentence', () => {
    const wrapper = mount(EmptyState, {
      props: { code: 'NO BEANS IN SIGHT', message: 'هنوز قهوه‌ای منتشر نشده است.' },
    })

    expect(wrapper.find('.empty__code').text()).toBe('NO BEANS IN SIGHT')
    expect(wrapper.find('.empty__message').text()).toBe('هنوز قهوه‌ای منتشر نشده است.')
  })

  it('draws a linear SVG mark, never an emoji', () => {
    const wrapper = mount(EmptyState, { props: { icon: 'bean' } })
    const svg = wrapper.find('svg')

    expect(svg.exists()).toBe(true)
    expect(svg.attributes('stroke')).toBe('currentColor')
    expect(svg.attributes('fill')).toBe('none')
    expect(wrapper.text()).not.toMatch(/\p{Extended_Pictographic}/u)
  })

  it('draws a different mark per icon', () => {
    const bean = mount(EmptyState, { props: { icon: 'bean' } }).html()
    const box = mount(EmptyState, { props: { icon: 'box' } }).html()
    const ticket = mount(EmptyState, { props: { icon: 'ticket' } }).html()

    expect(bean).not.toBe(box)
    expect(box).not.toBe(ticket)
    expect(bean).toContain('ellipse')
  })

  it('falls back to a visible mark for an unknown icon', () => {
    const wrapper = mount(EmptyState, { props: { icon: 'nonsense' } })

    expect(wrapper.find('svg path').exists()).toBe(true)
  })

  it('renders a call to action from the default slot', () => {
    const wrapper = mount(EmptyState, {
      props: { code: 'NO ORDERS YET' },
      slots: { default: '<button>دیدن قهوه‌ها</button>' },
    })

    expect(wrapper.find('.empty__action button').text()).toBe('دیدن قهوه‌ها')
  })

  it('omits the action wrapper when nothing is slotted', () => {
    const wrapper = mount(EmptyState, { props: { code: 'X' } })

    expect(wrapper.find('.empty__action').exists()).toBe(false)
  })

  it('switches registers and tone on request', () => {
    const terminal = mount(EmptyState, { props: { inverse: true, compact: true } })
    const error = mount(EmptyState, { props: { tone: 'error' } })

    expect(terminal.classes()).toContain('empty--inverse')
    expect(terminal.classes()).toContain('empty--compact')
    expect(error.classes()).toContain('empty--error')
  })

  it('announces itself to assistive technology', () => {
    const wrapper = mount(EmptyState, { props: { code: 'NO MATCH' } })

    expect(wrapper.attributes('role')).toBe('status')
    // The mark is decorative; the code and message carry the meaning.
    expect(wrapper.find('.empty__mark').attributes('aria-hidden')).toBe('true')
  })
})

describe('LoadingState', () => {
  it('shows a sweeping block in a framed track, not a spinner', () => {
    const wrapper = mount(LoadingState, { props: { variant: 'bar' } })

    expect(wrapper.find('.load__track').exists()).toBe(true)
    expect(wrapper.find('.load__block').exists()).toBe(true)
    // A spinner would be a circle or an arc; this system has neither.
    expect(wrapper.html()).not.toContain('circle')
  })

  it('prints a monospace status code', () => {
    const wrapper = mount(LoadingState, { props: { code: 'ROASTING THE LIST' } })

    expect(wrapper.find('.load__code').text()).toContain('ROASTING THE LIST')
  })

  it('draws the requested number of skeletons', () => {
    const wrapper = mount(LoadingState, { props: { variant: 'rows', count: 4 } })

    expect(wrapper.findAll('.skel')).toHaveLength(4)
  })

  it('lays cards out as a grid and rows as a stack', () => {
    const cards = mount(LoadingState, { props: { variant: 'cards', count: 2 } })
    const rows = mount(LoadingState, { props: { variant: 'rows', count: 2 } })

    expect(cards.find('.load__skeletons--cards').exists()).toBe(true)
    expect(rows.find('.load__skeletons--rows').exists()).toBe(true)
  })

  it('staggers the skeletons so the list reads as filling in', () => {
    const wrapper = mount(LoadingState, { props: { variant: 'rows', count: 3 } })
    const delays = wrapper.findAll('.skel').map((s) => s.attributes('style'))

    expect(new Set(delays).size).toBe(3)
  })

  it('renders inline without a track', () => {
    const wrapper = mount(LoadingState, { props: { variant: 'inline', code: 'LOADING' } })

    expect(wrapper.find('.load__track').exists()).toBe(false)
    expect(wrapper.find('.load__code--inline').exists()).toBe(true)
  })

  it('announces progress politely and uses no emoji', () => {
    const wrapper = mount(LoadingState, { props: { code: 'FETCHING ORDERS' } })

    expect(wrapper.attributes('role')).toBe('status')
    expect(wrapper.attributes('aria-live')).toBe('polite')
    expect(wrapper.text()).not.toMatch(/\p{Extended_Pictographic}/u)
  })
})
