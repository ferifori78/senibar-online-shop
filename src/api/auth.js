import client from './client'

export const authApi = {
  register: (payload) => client.post('/auth/register/', payload, { skipAuth: true }),
  login: (credentials) => client.post('/auth/login/', credentials, { skipAuth: true }),

  // Login or registration by one-time code. `skipAuth` because a signed-out
  // visitor is the whole point — sending a stale token would only 401.
  requestCode: (phone) =>
    client.post('/auth/otp/request/', { phone }, { skipAuth: true }),
  verifyCode: (payload) =>
    client.post('/auth/otp/verify/', payload, { skipAuth: true }),
  logout: (refresh) => client.post('/auth/logout/', { refresh }),
  profile: () => client.get('/me/'),
  updateProfile: (payload) => client.patch('/me/', payload),
  changePassword: (payload) => client.post('/auth/password/', payload),

  // Saved shipping addresses. Scoped to the caller server-side, so no user id
  // is ever sent from here.
  addresses: () => client.get('/addresses/'),
  createAddress: (payload) => client.post('/addresses/', payload),
  updateAddress: (id, payload) => client.patch(`/addresses/${id}/`, payload),
  deleteAddress: (id) => client.delete(`/addresses/${id}/`),
}

export default authApi
