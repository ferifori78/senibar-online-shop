import client from './client'

export const supportApi = {
  list: (params) => client.get('/tickets/', { params }),
  detail: (reference) => client.get(`/tickets/${reference}/`),
  create: (payload) => client.post('/tickets/', payload),
  reply: (reference, payload) => client.post(`/tickets/${reference}/reply/`, payload),
  close: (reference, note) => client.post(`/tickets/${reference}/close/`, { note }),
  reopen: (reference) => client.post(`/tickets/${reference}/reopen/`),
  assign: (reference, payload) => client.post(`/tickets/${reference}/assign/`, payload),
  inboxSummary: () => client.get('/support/inbox-summary/'),
}

export default supportApi
