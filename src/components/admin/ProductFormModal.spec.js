import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import ProductFormModal from './ProductFormModal.vue'

/*
 * The form has two shapes behind one component: a roasted lot, and a pantry
 * item with no roast, grind or cup profile. These tests pin the boundary —
 * which fields exist for which kind, and which validation applies — because
 * getting it wrong is invisible until a roaster cannot save a product.
 */

const saveProduct = vi.fn()
const fetchProduct = vi.fn()

vi.mock('@/stores/admin', () => ({
  useAdminStore: () => ({
    fieldErrors: {},
    saveProduct,
    fetchProduct,
    resetErrors: vi.fn(),
  }),
}))

// The gallery talks to the API and is irrelevant here.
const stubs = {
  ProductGallery: true,
  BaseButton: { template: '<button><slot /></button>' },
}

function makeForm(props = {}) {
  return mount(ProductFormModal, {
    props: { product: null, ...props },
    global: { stubs, directives: { digits: {} } },
  })
}

/** Switch the form to the pantry shape the way a roaster would. */
async function choosePantry(wrapper) {
  const pantry = wrapper
    .findAll('.kind__btn')
    .find((b) => b.text().includes('محصول انبار'))
  await pantry.trigger('click')
  return wrapper
}

describe('ProductFormModal — product kinds', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    saveProduct.mockResolvedValue({ ok: true, data: {} })
  })

  it('offers both kinds and starts on a coffee lot', () => {
    const wrapper = makeForm()
    expect(wrapper.findAll('.kind__btn')).toHaveLength(2)
    // A new product is a coffee until told otherwise: that is what this shop
    // mostly sells, and it keeps the existing workflow unchanged.
    expect(wrapper.find('.kind__btn--on').text()).toContain('قهوه تک‌مبدأ')
  })

  it('hides the cup profile for a pantry item', async () => {
    // Asserted on the legends, not on the whole text: the phrase "پروفایل
    // فنجان" also appears in the kind toggle's own hint, so a substring
    // search over the form would pass while the fieldset was still rendered.
    const legends = (w) => w.findAll('.set__legend').map((l) => l.text())

    const wrapper = makeForm()
    expect(legends(wrapper)).toContain('پروفایل فنجان')

    await choosePantry(wrapper)
    // Masala has no acidity or body; showing the axes would invite someone to
    // record a measurement that does not exist, and the quiz would score it.
    expect(legends(wrapper)).not.toContain('پروفایل فنجان')
    expect(legends(wrapper)).toContain('موجودی و قیمت')
  })

  it('swaps farm and varietal for brand and production year', async () => {
    const wrapper = makeForm()
    expect(wrapper.text()).toContain('مزرعه')
    expect(wrapper.text()).toContain('واریته')

    await choosePantry(wrapper)
    expect(wrapper.text()).not.toContain('مزرعه')
    expect(wrapper.text()).not.toContain('واریته')
    expect(wrapper.text()).toContain('برند')
    expect(wrapper.text()).toContain('سال تولید')
  })

  it('asks for package fields when sold as a package', async () => {
    const wrapper = await choosePantry(makeForm())
    expect(wrapper.text()).toContain('وزن هر بسته')
    expect(wrapper.text()).toContain('قیمت هر بسته')
    expect(wrapper.text()).toContain('تعداد موجود در انبار')
    // A package is counted in packs, not grams.
    expect(wrapper.text()).not.toContain('موجودی انبار (گرم)')
  })

  it('asks for grams when sold by weight', async () => {
    const wrapper = await choosePantry(makeForm())
    await wrapper.find('select').setValue('weight')

    expect(wrapper.text()).toContain('موجودی انبار (گرم)')
    expect(wrapper.text()).not.toContain('وزن هر بسته')
  })

  it('does not demand a 250g price for a package item', async () => {
    // The bug this pins: `validate()` required price_per_250g for everything,
    // which made every package item impossible to save — the field is not
    // even on screen for one.
    const wrapper = await choosePantry(makeForm())
    await wrapper.find('input').setValue('چای ماسالا')

    const inputs = wrapper.findAll('input')
    const byLabel = (text) =>
      wrapper.findAll('label').find((l) => l.text().includes(text))?.find('input')

    await byLabel('کشور').setValue('هند')
    await byLabel('وزن هر بسته').setValue(200)
    await byLabel('قیمت هر بسته').setValue(185000)

    await wrapper.find('form').trigger('submit')
    expect(saveProduct).toHaveBeenCalled()
    const payload = saveProduct.mock.calls[0][0]
    expect(payload.kind).toBe('pantry')
    expect(payload.package_price).toBe(185000)
    // Sent as 0 rather than null: the column is not nullable, and it is
    // genuinely unused for a package.
    expect(payload.price_per_250g).toBe(0)
    expect(inputs.length).toBeGreaterThan(0)
  })

  it('still demands a price from a coffee lot', async () => {
    const wrapper = makeForm()
    const byLabel = (text) =>
      wrapper.findAll('label').find((l) => l.text().includes(text))?.find('input')

    await byLabel('نام').setValue('یرگاچف')
    await byLabel('کشور').setValue('اتیوپی')

    await wrapper.find('form').trigger('submit')
    expect(saveProduct).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('قیمت باید بزرگ‌تر از صفر باشد.')
  })
})

describe('ProductFormModal — origin type', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    saveProduct.mockResolvedValue({ ok: true, data: {} })
  })

  it('offers single and multi origin for a coffee lot', () => {
    const wrapper = makeForm()
    const label = wrapper.findAll('label').find((l) => l.text().includes('خاستگاه'))
    expect(label).toBeTruthy()
    const options = label.findAll('option').map((o) => o.text())
    expect(options).toEqual(['تک‌خاستگاه', 'چندخاستگاه'])
  })

  it('sends the chosen origin type', async () => {
    const wrapper = makeForm()
    const byLabel = (text) =>
      wrapper.findAll('label').find((l) => l.text().includes(text))

    await byLabel('نام').find('input').setValue('ترکیب صبحگاهی')
    await byLabel('کشور').find('input').setValue('اتیوپی')
    await byLabel('قیمت').find('input').setValue(250000)
    await byLabel('خاستگاه').find('select').setValue('multi')

    await wrapper.find('form').trigger('submit')
    // A select bound to a key missing from `form` silently saves the default,
    // so this asserts the value actually reaches the payload.
    expect(saveProduct).toHaveBeenCalled()
    expect(saveProduct.mock.calls[0][0].origin_type).toBe('multi')
  })

  it('shows the saved origin type when editing', async () => {
    fetchProduct.mockResolvedValue({
      ok: true,
      data: { slug: 'blend', name: 'ترکیب', origin_type: 'multi', kind: 'lot' },
    })
    const wrapper = makeForm({ product: { slug: 'blend', name: 'ترکیب' } })
    await new Promise((r) => setTimeout(r, 0))
    await wrapper.vm.$nextTick()

    const select = wrapper
      .findAll('label')
      .find((l) => l.text().includes('خاستگاه'))
      .find('select')
    // `fill()` copies by key over `Object.keys(form)`. A key missing from the
    // form's initial shape is skipped, so editing a multi-origin blend would
    // show «تک‌خاستگاه» and save that back over it.
    expect(select.element.value).toBe('multi')
  })

  it('hides the origin type for a pantry item', async () => {
    const wrapper = await choosePantry(makeForm())
    // It lives in the cup-profile fieldset: masala has no origin to blend.
    expect(wrapper.findAll('label').find((l) => l.text().includes('خاستگاه'))).toBeFalsy()
  })
})

describe('ProductFormModal — home page shelf', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    saveProduct.mockResolvedValue({ ok: true, data: {} })
  })

  const shelfToggle = (wrapper) =>
    wrapper.findAll('.check').find((b) => b.text().includes('پیشنهادی صنوبر'))

  it('offers the shelf toggle, off by default', () => {
    const wrapper = makeForm()
    const toggle = shelfToggle(wrapper)
    expect(toggle).toBeTruthy()
    expect(toggle.attributes('aria-pressed')).toBe('false')
  })

  it('sends is_featured once turned on', async () => {
    const wrapper = makeForm()
    const byLabel = (text) =>
      wrapper.findAll('label').find((l) => l.text().includes(text))

    await byLabel('نام').find('input').setValue('یرگاچف')
    await byLabel('کشور').find('input').setValue('اتیوپی')
    await byLabel('قیمت').find('input').setValue(250000)
    await shelfToggle(wrapper).trigger('click')

    await wrapper.find('form').trigger('submit')
    expect(saveProduct).toHaveBeenCalled()
    expect(saveProduct.mock.calls[0][0].is_featured).toBe(true)
  })

  it('shows the saved state when editing', async () => {
    fetchProduct.mockResolvedValue({
      ok: true,
      data: { slug: 'y', name: 'یرگاچف', kind: 'lot', is_featured: true },
    })
    const wrapper = makeForm({ product: { slug: 'y', name: 'یرگاچف' } })
    await new Promise((r) => setTimeout(r, 0))
    await wrapper.vm.$nextTick()

    // `fill()` copies by key over the form's initial shape. A key missing
    // there is skipped, so editing a featured product would quietly clear it.
    expect(shelfToggle(wrapper).attributes('aria-pressed')).toBe('true')
  })

  it('offers it for a pantry item too', async () => {
    const wrapper = await choosePantry(makeForm())
    // Masala belongs on the home shelf as readily as a coffee does.
    expect(shelfToggle(wrapper)).toBeTruthy()
  })
})
