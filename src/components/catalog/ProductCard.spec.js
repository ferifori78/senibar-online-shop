import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import ProductCard from './ProductCard.vue'

const LOT = {
  id: 1,
  slug: 'yirgacheffe',
  name: 'یرگاچف',
  kind: 'lot',
  origin_country: 'اتیوپی',
  process_display: 'شسته',
  roast_level_display: 'متوسط',
  price_per_250g: 250000,
  is_in_stock: true,
  flavor_notes: [],
}

const MASALA = {
  id: 2,
  slug: 'masala',
  name: 'چای ماسالا',
  kind: 'pantry',
  origin_country: 'هند',
  brand: 'واگ باکری',
  // Not nullable on the model, so a pantry row carries these whether or not
  // they mean anything. The card must not print them.
  process_display: 'شسته',
  roast_level_display: 'متوسط',
  sale_mode: 'package',
  package_grams: 200,
  package_price: 185000,
  price_per_250g: 0,
  is_in_stock: true,
  flavor_notes: [],
}

function mountCard(product) {
  return mount(ProductCard, {
    props: { product },
    global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
  })
}

describe('ProductCard — coffee and pantry', () => {
  it('prints process and roast for a coffee lot', () => {
    const text = mountCard(LOT).text()
    expect(text).toContain('شسته')
    expect(text).toContain('متوسط')
    expect(text).toContain('۲۵۰ گرم')
  })

  it('never prints a roast profile for a pantry item', () => {
    const text = mountCard(MASALA).text()
    // The bug this pins: `process` and `roast_level` are non-nullable, so
    // masala carried the column defaults and the card read «شسته · متوسط» —
    // a roast profile invented for something that was never roasted.
    expect(text).not.toContain('شسته')
    expect(text).not.toContain('متوسط')
    expect(text).toContain('واگ باکری')
  })

  it('prices a package per pack, at the pack size', () => {
    const text = mountCard(MASALA).text()
    // Not «۲۵۰ گرم»: that would state the wrong weight for the price beside
    // it, since this pack is 200g.
    expect(text).toContain('۲۰۰ گرم')
    expect(text).not.toContain('۲۵۰ گرم')
    // `formatPrice` converts rial to toman, so 185,000 prints as ۱۸٬۵۰۰ —
    // the package price, not the unused 250g one.
    expect(text).toContain('۱۸٬۵۰۰')
  })

  it('falls back to "هر بسته" when no pack size was recorded', () => {
    const text = mountCard({ ...MASALA, package_grams: null }).text()
    expect(text).toContain('هر بسته')
  })

  it('drops the meta row entirely for a pantry item with no brand', () => {
    const wrapper = mountCard({ ...MASALA, brand: '' })
    // An empty bordered row reads as a missing value rather than an absent one.
    expect(wrapper.find('.card__meta').exists()).toBe(false)
  })

  it('carries no emoji', () => {
    expect(mountCard(MASALA).text()).not.toMatch(/\p{Extended_Pictographic}/u)
  })
})

describe('ProductCard — origin tab', () => {
  it('shows the country when there is one', () => {
    expect(mountCard(LOT).find('.card__origin').text()).toBe('اتیوپی')
  })

  it('says ترکیبی for a blend with no single country', () => {
    // The cleanup migration clears `origin_country` for a blend, because the
    // column is singular and «Brazil / Colombia / Ethiopia» is not a country.
    const wrapper = mountCard({ ...LOT, origin_country: '', origin_type: 'multi' })
    expect(wrapper.find('.card__origin').text()).toBe('ترکیبی')
  })

  it('drops the tab entirely when the origin is unknown', () => {
    // An empty tab renders as a black rectangle with nothing in it.
    const wrapper = mountCard({ ...LOT, origin_country: '', origin_type: 'single' })
    expect(wrapper.find('.card__origin').exists()).toBe(false)
  })
})
