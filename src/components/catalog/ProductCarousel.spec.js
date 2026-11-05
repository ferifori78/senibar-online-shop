import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import ProductCarousel from './ProductCarousel.vue'

const FOUR = [
  { id: 1, image: '/media/a.jpg', alt_text: '' },
  { id: 2, image: '/media/b.jpg', alt_text: 'دانه‌ها' },
  { id: 3, image: '/media/c.jpg', alt_text: '' },
  { id: 4, image: '/media/d.jpg', alt_text: '' },
]

const mountIt = (props) => mount(ProductCarousel, { props: { name: 'یرگاچف', ...props } })

/** The index of the one slide that is not hidden. */
function shown(wrapper) {
  return wrapper.findAll('.car__image').findIndex(
    (img) => img.attributes('hidden') === undefined,
  )
}

describe('ProductCarousel', () => {
  it('renders every uploaded photo, not just the cover', () => {
    expect(mountIt({ images: FOUR }).findAll('.car__image')).toHaveLength(4)
  })

  it('shows one at a time', () => {
    const wrapper = mountIt({ images: FOUR })
    const visible = wrapper.findAll('.car__image').filter((i) => i.attributes('hidden') === undefined)
    expect(visible).toHaveLength(1)
  })

  it('falls back to the cover when the gallery is empty', () => {
    // Products from before the gallery existed still have only `image`.
    const wrapper = mountIt({ images: [], fallback: '/media/cover.jpg' })
    const images = wrapper.findAll('.car__image')
    expect(images).toHaveLength(1)
    expect(images[0].attributes('src')).toBe('/media/cover.jpg')
  })

  it('shows the placeholder when there is no photo at all', () => {
    const wrapper = mountIt({ images: [], fallback: '' })
    expect(wrapper.findAll('.car__image')).toHaveLength(0)
    expect(wrapper.find('.car__placeholder').exists()).toBe(true)
  })

  it('grows no controls for a single photo', () => {
    // A product with one picture should look exactly as it did before.
    const wrapper = mountIt({ images: [FOUR[0]] })
    expect(wrapper.find('.car__arrow').exists()).toBe(false)
    expect(wrapper.find('.car__thumbs').exists()).toBe(false)
    expect(wrapper.find('.car__count').exists()).toBe(false)
  })

  it('offers a thumbnail per photo when there are several', () => {
    expect(mountIt({ images: FOUR }).findAll('.car__thumb')).toHaveLength(4)
  })

  it('advances and goes back', async () => {
    const wrapper = mountIt({ images: FOUR })
    expect(shown(wrapper)).toBe(0)

    await wrapper.find('.car__arrow--next').trigger('click')
    expect(shown(wrapper)).toBe(1)

    await wrapper.find('.car__arrow--prev').trigger('click')
    expect(shown(wrapper)).toBe(0)
  })

  it('wraps around rather than dead-ending', async () => {
    const wrapper = mountIt({ images: FOUR })

    // Back from the first photo lands on the last.
    await wrapper.find('.car__arrow--prev').trigger('click')
    expect(shown(wrapper)).toBe(3)

    // And forward from the last returns to the first.
    await wrapper.find('.car__arrow--next').trigger('click')
    expect(shown(wrapper)).toBe(0)
  })

  it('jumps to a photo from its thumbnail, and marks it current', async () => {
    const wrapper = mountIt({ images: FOUR })
    await wrapper.findAll('.car__thumb')[2].trigger('click')

    expect(shown(wrapper)).toBe(2)
    expect(wrapper.findAll('.car__thumb')[2].classes()).toContain('car__thumb--on')
    expect(wrapper.findAll('.car__thumb')[2].attributes('aria-current')).toBe('true')
  })

  it('maps the arrow keys to the reading direction, not the array', async () => {
    // The page is RTL: the visually-left arrow means "next".
    const wrapper = mountIt({ images: FOUR })

    await wrapper.find('.car__plate').trigger('keydown', { key: 'ArrowLeft' })
    expect(shown(wrapper)).toBe(1)

    await wrapper.find('.car__plate').trigger('keydown', { key: 'ArrowRight' })
    expect(shown(wrapper)).toBe(0)
  })

  it('uses the photo alt text when there is one, else the coffee name', () => {
    const images = mountIt({ images: FOUR }).findAll('.car__image')
    expect(images[0].attributes('alt')).toBe('یرگاچف')
    expect(images[1].attributes('alt')).toBe('دانه‌ها')
  })

  it('is reachable by keyboard only when there is somewhere to go', () => {
    expect(mountIt({ images: FOUR }).find('.car__plate').attributes('tabindex')).toBe('0')
    expect(mountIt({ images: [FOUR[0]] }).find('.car__plate').attributes('tabindex')).toBeUndefined()
  })

  it('resets when the gallery shrinks under it', async () => {
    // Navigating to another coffee reuses the component; a stale index would
    // otherwise point past the end of the new product's gallery.
    const wrapper = mountIt({ images: FOUR })
    await wrapper.findAll('.car__thumb')[3].trigger('click')
    expect(shown(wrapper)).toBe(3)

    await wrapper.setProps({ images: FOUR.slice(0, 2) })
    expect(shown(wrapper)).toBe(0)
  })
})
