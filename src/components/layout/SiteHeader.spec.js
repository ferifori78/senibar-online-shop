import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'

import SiteHeader from './SiteHeader.vue'
import { PANEL_BASE } from '@/constants/panel'
import { useAuthStore } from '@/stores/auth'
import { useCartStore } from '@/stores/cart'

const Blank = { template: '<div />' }

function makeRouter() {
  return createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/', name: 'home', component: Blank },
      { path: '/about', name: 'about', component: Blank },
      { path: '/products', name: 'products', component: Blank },
      { path: '/cart', name: 'cart', component: Blank },
      { path: '/account', name: 'account', component: Blank },
      { path: '/orders', name: 'orders', component: Blank },
      { path: '/support', name: 'support', component: Blank },
      { path: PANEL_BASE, name: 'admin-dashboard', component: Blank },
      { path: '/login', name: 'login', component: Blank },
    ],
  })
}

async function mountHeader() {
  const router = makeRouter()
  router.push('/')
  await router.isReady()
  const wrapper = mount(SiteHeader, { global: { plugins: [router] } })
  return { wrapper, router }
}

function hrefs(wrapper) {
  return wrapper.findAll('.head__nav a').map((a) => a.attributes('href'))
}

describe('SiteHeader', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('shows only the public links to a signed-out visitor', async () => {
    const { wrapper } = await mountHeader()

    expect(hrefs(wrapper)).toEqual(['/products', '/about'])
    expect(wrapper.text()).toContain('ورود')
    expect(wrapper.text()).not.toContain('خروج')
  })

  it('adds the account link once signed in, but not the admin panel', async () => {
    const auth = useAuthStore()
    auth.access = 'token'
    auth.user = { display_name: 'سپیده', role: 'customer' }

    const { wrapper } = await mountHeader()

    // Orders and support hang off the account panel, not the header.
    expect(hrefs(wrapper)).toEqual(['/products', '/about', '/account'])
    expect(hrefs(wrapper)).not.toContain('/orders')
    expect(hrefs(wrapper)).not.toContain('/support')
    expect(hrefs(wrapper)).not.toContain(PANEL_BASE)
  })

  it('offers the admin panel to a roaster', async () => {
    const auth = useAuthStore()
    auth.access = 'token'
    auth.user = { display_name: 'رستر', role: 'roaster' }

    const { wrapper } = await mountHeader()

    expect(hrefs(wrapper)).toContain(PANEL_BASE)
  })

  it('hides the cart badge when empty and counts units, not lines', async () => {
    const cart = useCartStore()
    const { wrapper } = await mountHeader()

    expect(wrapper.find('.head__count').exists()).toBe(false)

    // Two lines, four bags in total: the badge reports bags.
    cart.items = [
      { slug: 'a', weight_grams: 250, grind_type: 'whole', quantity: 3, unit_price: '100' },
      { slug: 'b', weight_grams: 250, grind_type: 'v60', quantity: 1, unit_price: '100' },
    ]
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.head__count').text()).toBe('4')
  })

  it('closes the drawer after navigating, so it cannot cover the new page', async () => {
    const { wrapper, router } = await mountHeader()

    await wrapper.find('.head__toggle').trigger('click')
    expect(wrapper.find('#site-drawer').exists()).toBe(true)

    await router.push('/products')
    await wrapper.vm.$nextTick()

    expect(wrapper.find('#site-drawer').exists()).toBe(false)
  })

  it('reports the drawer toggle state for assistive tech', async () => {
    const { wrapper } = await mountHeader()
    const toggle = wrapper.find('.head__toggle')

    expect(toggle.attributes('aria-expanded')).toBe('false')
    await toggle.trigger('click')
    expect(toggle.attributes('aria-expanded')).toBe('true')
  })
})
