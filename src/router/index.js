import { createRouter, createWebHistory } from 'vue-router'

import { panelPath } from '@/constants/panel'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/HomeView.vue'),
  },
  {
    path: '/about',
    name: 'about',
    component: () => import('@/views/AboutView.vue'),
  },
  {
    path: '/products',
    name: 'products',
    component: () => import('@/views/ProductListView.vue'),
  },
  {
    path: '/products/:slug',
    name: 'product-detail',
    component: () => import('@/views/ProductDetailView.vue'),
  },
  // --- Admin: the Terminal register ---------------------------------------
  // Under PANEL_BASE, not /admin — Nginx proxies /admin/ to Django's own admin,
  // so a panel route there would never reach the SPA.
  {
    path: panelPath(),
    name: 'admin-dashboard',
    component: () => import('@/views/admin/AdminDashboardView.vue'),
    meta: { requiresAuth: true, requiresStaff: true, chrome: false },
  },
  {
    path: panelPath('orders'),
    name: 'admin-orders',
    component: () => import('@/views/admin/AdminOrdersView.vue'),
    meta: { requiresAuth: true, requiresStaff: true, chrome: false },
  },
  {
    path: panelPath('products'),
    name: 'admin-products',
    component: () => import('@/views/admin/AdminProductsView.vue'),
    meta: { requiresAuth: true, requiresStaff: true, chrome: false },
  },
  {
    path: panelPath('batches'),
    name: 'admin-batches',
    component: () => import('@/views/admin/AdminBatchesView.vue'),
    meta: { requiresAuth: true, requiresStaff: true, chrome: false },
  },
  {
    path: panelPath('inventory'),
    name: 'admin-inventory',
    component: () => import('@/views/admin/AdminInventoryView.vue'),
    meta: { requiresAuth: true, requiresStaff: true, chrome: false },
  },
  {
    path: panelPath('users'),
    name: 'admin-users',
    component: () => import('@/views/admin/AdminUsersView.vue'),
    meta: { requiresAuth: true, requiresStaff: true, chrome: false },
  },
  {
    path: panelPath('settings'),
    name: 'admin-settings',
    component: () => import('@/views/admin/AdminSettingsView.vue'),
    meta: { requiresAuth: true, requiresStaff: true, chrome: false },
  },
  {
    path: panelPath('support'),
    name: 'admin-support',
    component: () => import('@/views/admin/AdminSupportView.vue'),
    meta: { requiresAuth: true, requiresStaff: true, chrome: false },
  },
  // --- Support: the customer's side ---------------------------------------
  {
    path: '/support',
    name: 'support',
    component: () => import('@/views/TicketListView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/support/:reference',
    name: 'ticket-detail',
    component: () => import('@/views/TicketDetailView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/account',
    name: 'account',
    component: () => import('@/views/AccountView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/orders',
    name: 'orders',
    component: () => import('@/views/OrderListView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/orders/:number',
    name: 'order-detail',
    component: () => import('@/views/OrderDetailView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/cart',
    name: 'cart',
    component: () => import('@/views/CartView.vue'),
  },
  {
    path: '/checkout',
    name: 'checkout',
    component: () => import('@/views/CheckoutView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/checkout/callback',
    name: 'checkout-callback',
    component: () => import('@/views/CheckoutCallbackView.vue'),
  },
  {
    // Mock gateway's stand-in pay page. Inert unless the backend runs the mock.
    path: '/checkout/mock-gateway/:authority',
    name: 'mock-gateway',
    component: () => import('@/views/MockGatewayView.vue'),
    meta: { chrome: false },
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { guestOnly: true, chrome: false },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/views/RegisterView.vue'),
    meta: { guestOnly: true, chrome: false },
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach((to) => {
  const auth = useAuthStore()

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  // The admin panel is staff-only. The API enforces this too — this guard just
  // avoids showing a customer a panel that would only return 403s.
  if (to.meta.requiresStaff && !auth.isStaff) {
    return { name: 'home' }
  }

  // A signed-in user has no business on the login or register page.
  if (to.meta.guestOnly && auth.isAuthenticated) {
    return { name: 'home' }
  }

  return true
})

/*
 * Report the page view for the shop's own traffic digest.
 *
 * `afterEach`, so a navigation that was redirected or cancelled is not
 * counted. Admin pages are skipped — the roaster browsing their own panel is
 * not traffic. Failures are swallowed entirely: this is a counter, and a
 * customer must never see a page break because of it.
 */
router.afterEach((to) => {
  if (to.meta.requiresStaff) return

  import('@/api/visits')
    .then(({ recordVisit }) => recordVisit(to.fullPath))
    .catch(() => {})
})

export default router
