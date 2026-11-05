import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import OrderTimeline from './OrderTimeline.vue'

const PIPELINE = ['pending', 'roasting', 'ground', 'packed', 'shipped', 'delivered']

/** Build a timeline payload shaped like the API's, with `current` at `index`. */
function stagesAt(index) {
  return PIPELINE.map((status, i) => ({
    status,
    label: status,
    state: i < index ? 'done' : i === index ? 'current' : 'upcoming',
  }))
}

const cancelledStages = PIPELINE.map((status) => ({ status, label: status, state: 'cancelled' }))

function fillWidth(wrapper) {
  return wrapper.find('.rail__fill').attributes('style') || ''
}

describe('OrderTimeline', () => {
  it('renders one node per pipeline stage', () => {
    const wrapper = mount(OrderTimeline, { props: { stages: stagesAt(0) } })

    expect(wrapper.findAll('[role="listitem"]')).toHaveLength(6)
    expect(wrapper.findAll('.rail__node')).toHaveLength(6)
  })

  it('labels the stages in Persian, not the API English', () => {
    const wrapper = mount(OrderTimeline, { props: { stages: stagesAt(1) } })
    const text = wrapper.text()

    expect(text).toContain('ثبت سفارش')
    expect(text).toContain('در حال رست')
    expect(text).toContain('آسیاب شده')
    expect(text).toContain('بسته‌بندی')
    expect(text).toContain('ارسال شده')
    expect(text).not.toContain('roasting')
  })

  it('leaves the rail empty on a brand new order', () => {
    const wrapper = mount(OrderTimeline, { props: { stages: stagesAt(0) } })

    expect(fillWidth(wrapper)).toContain('height: 0%')
  })

  it('fills the rail proportionally to the current stage', () => {
    // packed is index 3 of 6 stages, so 3/5 of the way along the rail.
    const wrapper = mount(OrderTimeline, { props: { stages: stagesAt(3) } })

    expect(fillWidth(wrapper)).toContain('height: 60%')
  })

  it('fills the rail completely once delivered', () => {
    const wrapper = mount(OrderTimeline, { props: { stages: stagesAt(5) } })

    expect(fillWidth(wrapper)).toContain('height: 100%')
  })

  it('marks exactly one stage as current and the earlier ones as done', () => {
    const wrapper = mount(OrderTimeline, { props: { stages: stagesAt(2) } })

    expect(wrapper.findAll('.rail__stage--current')).toHaveLength(1)
    expect(wrapper.findAll('.rail__stage--done')).toHaveLength(2)
    expect(wrapper.findAll('.rail__stage--upcoming')).toHaveLength(3)
  })

  it('shows a "now" badge only on the current stage', () => {
    const wrapper = mount(OrderTimeline, { props: { stages: stagesAt(2) } })

    expect(wrapper.findAll('.rail__badge')).toHaveLength(1)
    expect(wrapper.find('.rail__stage--current .rail__badge').text()).toBe('اکنون')
  })

  it('drains the rail entirely for a cancelled order', () => {
    const wrapper = mount(OrderTimeline, { props: { stages: cancelledStages } })

    expect(fillWidth(wrapper)).toContain('height: 0%')
    expect(wrapper.classes()).toContain('rail--cancelled')
    expect(wrapper.findAll('.rail__stage--current')).toHaveLength(0)
  })

  it('prints the real timestamp for a stage that has one', () => {
    const wrapper = mount(OrderTimeline, {
      props: {
        stages: stagesAt(1),
        order: { placed_at: '2026-08-30T09:15:00Z', roasted_at: null },
      },
    })
    const first = wrapper.findAll('[role="listitem"]')[0]

    // Persian calendar rendering; assert it produced digits, not the raw ISO.
    expect(first.find('.rail__time').exists()).toBe(true)
    expect(first.text()).not.toContain('2026-08-30T')
  })

  it('falls back to a description when a stage has no timestamp', () => {
    const wrapper = mount(OrderTimeline, {
      props: { stages: stagesAt(1), order: { placed_at: null } },
    })
    const roasting = wrapper.findAll('[role="listitem"]')[1]

    expect(roasting.find('.rail__note').text()).toContain('در حال رست')
  })

  it('says nothing under stages that have not happened yet', () => {
    const wrapper = mount(OrderTimeline, { props: { stages: stagesAt(1), order: {} } })
    const upcoming = wrapper.findAll('[role="listitem"]')[4]

    expect(upcoming.find('.rail__note').exists()).toBe(false)
    expect(upcoming.find('.rail__time').exists()).toBe(false)
  })

  it('switches to the Terminal register when inverse', () => {
    const wrapper = mount(OrderTimeline, { props: { stages: stagesAt(1), inverse: true } })

    expect(wrapper.classes()).toContain('rail--inverse')
  })

  it('uses no emoji anywhere', () => {
    const wrapper = mount(OrderTimeline, {
      props: { stages: stagesAt(3), order: { placed_at: '2026-08-30T09:15:00Z' } },
    })

    expect(wrapper.text()).not.toMatch(/\p{Extended_Pictographic}/u)
  })
})
