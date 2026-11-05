import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'

import { vDigits } from './digits'

/** Mount a bare input carrying the directive, as the admin forms do. */
function mountField(template, initial = null) {
  const model = ref(initial)
  const wrapper = mount(
    { template, setup: () => ({ form: ref({ value: initial }), model }) },
    { global: { directives: { digits: vDigits } } },
  )
  return { wrapper, model }
}

async function type(wrapper, value) {
  const input = wrapper.find('input')
  input.element.value = value
  await input.trigger('input')
  return input
}

describe('v-digits', () => {
  it('takes a number input off type=number, which would discard Persian input', () => {
    // <input type="number"> reports an empty value for anything it cannot
    // parse, so the roaster typing ۱۲۰۰۰۰ saw the field clear itself.
    const { wrapper } = mountField(
      '<input v-digits v-model.number="model" type="number" />',
    )
    const input = wrapper.find('input')
    expect(input.attributes('type')).toBe('text')
    expect(input.attributes('inputmode')).toBe('decimal')
  })

  it('feeds the ASCII value to v-model.number as a number', async () => {
    const { wrapper, model } = mountField(
      '<input v-digits v-model.number="model" type="number" />',
    )
    await type(wrapper, '۱۲۰۰۰۰')
    expect(model.value).toBe(120000)
  })

  it('keeps the decimal point in a price', async () => {
    const { wrapper, model } = mountField(
      '<input v-digits v-model.number="model" type="number" />',
    )
    await type(wrapper, '۸۶.۵')
    expect(model.value).toBe(86.5)
  })

  it('keeps a leading minus, for an adjustment that removes stock', async () => {
    const { wrapper, model } = mountField(
      '<input v-digits v-model.number="model" type="number" />',
    )
    await type(wrapper, '-۲۵۰')
    expect(model.value).toBe(-250)
  })

  it('strips digits only on a text field', async () => {
    const { wrapper, model } = mountField('<input v-digits v-model="model" type="text" />')
    await type(wrapper, '۱۲۳ الف')
    expect(model.value).toBe('123')
  })

  it('keeps surrounding text with the loose modifier', async () => {
    const { wrapper, model } = mountField('<input v-digits.loose v-model="model" />')
    await type(wrapper, 'پلاک ۱۲')
    expect(model.value).toBe('پلاک 12')
  })

  it('rewrites the visible field as well as the model', async () => {
    const { wrapper } = mountField('<input v-digits v-model="model" type="text" />')
    const input = await type(wrapper, '۹۹')
    expect(input.element.value).toBe('99')
  })

  it('leaves an already-ASCII value alone without re-dispatching', async () => {
    const { wrapper, model } = mountField('<input v-digits v-model="model" type="text" />')
    await type(wrapper, '4040')
    expect(model.value).toBe('4040')
  })

  it('finds the input when the directive sits on a wrapping label', async () => {
    const { wrapper, model } = mountField(
      '<label v-digits><span>وزن</span><input v-model="model" /></label>',
    )
    await type(wrapper, '۲۵۰')
    expect(model.value).toBe('250')
  })
})
