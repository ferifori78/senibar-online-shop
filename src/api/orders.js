import client from './client'

export const ordersApi = {
  quoteCart: (payload) => client.post('/cart/quote/', payload),
  shippingMethods: (subtotal) => client.get('/shipping/methods/', { params: { subtotal } }),

  create: (payload) => client.post('/orders/', payload),
  list: (params) => client.get('/orders/', { params }),
  detail: (number) => client.get(`/orders/${number}/`),
  cancel: (number, reason) => client.post(`/orders/${number}/cancel/`, { reason }),
}

export const paymentsApi = {
  // Public: the checkout page needs the list before anyone signs in.
  gateways: () => client.get('/payments/gateways/', { skipAuth: true }),
  request: (payload) => client.post('/payments/request/', payload),
  // The gateway sends the customer back unauthenticated; the authority is the
  // credential, so this call must not carry a stale token.
  verify: (params) => client.post('/payments/verify/', params, { skipAuth: true }),
  status: (orderNumber) => client.get(`/payments/status/${orderNumber}/`),
  // Mock gateway only — stands in for the hosted pay page.
  mockPay: (authority, outcome = 'success') =>
    client.post(`/payments/mock/${authority}/`, { outcome }, { skipAuth: true }),
}

export default ordersApi
