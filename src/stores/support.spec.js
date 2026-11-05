import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/support', () => ({
  default: {
    list: vi.fn(),
    detail: vi.fn(),
    create: vi.fn(),
    reply: vi.fn(),
    close: vi.fn(),
    reopen: vi.fn(),
    inboxSummary: vi.fn(),
  },
}))

import supportApi from '@/api/support'
import { useSupportStore } from './support'

function apiError(status, data) {
  return Object.assign(new Error('failed'), { response: { status, data } })
}

const TICKET = {
  reference: 'TK-1',
  subject: 'قهوه دیر رسید',
  status: 'open',
  status_display: 'باز',
  messages: [
    { id: 1, body: 'سلام', author_role: 'customer', is_internal: false },
  ],
}

describe('support store', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    supportApi.list.mockResolvedValue({ data: { results: [], count: 0 } })
    setActivePinia(createPinia())
  })

  it('sends the active state filter when listing', async () => {
    const support = useSupportStore()

    await support.setState('needs_reply')

    expect(supportApi.list).toHaveBeenCalledWith({ state: 'needs_reply' })
  })

  it('omits the state param when showing everything', async () => {
    const support = useSupportStore()

    await support.setState('all')

    expect(supportApi.list).toHaveBeenCalledWith({})
  })

  it('clears the local unread badge when a thread is opened', async () => {
    supportApi.list.mockResolvedValue({
      data: { results: [{ reference: 'TK-1', unread: 3 }], count: 1 },
    })
    supportApi.detail.mockResolvedValue({ data: TICKET })
    const support = useSupportStore()
    await support.fetchTickets()

    await support.fetchTicket('TK-1')

    expect(support.tickets[0].unread).toBe(0)
    expect(support.ticket.reference).toBe('TK-1')
  })

  it('adopts the refreshed thread the reply response carries', async () => {
    supportApi.detail.mockResolvedValue({ data: TICKET })
    supportApi.reply.mockResolvedValue({
      data: {
        message: { id: 2, body: 'بررسی شد', author_role: 'staff' },
        ticket: { ...TICKET, status: 'pending', messages: [...TICKET.messages, { id: 2 }] },
      },
    })
    const support = useSupportStore()
    await support.fetchTicket('TK-1')

    const result = await support.reply('TK-1', 'بررسی شد')

    expect(result.ok).toBe(true)
    expect(support.ticket.status).toBe('pending')
    expect(support.messages).toHaveLength(2)
    expect(support.sending).toBe(false)
  })

  it('passes the internal flag through to the API', async () => {
    supportApi.reply.mockResolvedValue({ data: { message: {}, ticket: TICKET } })
    const support = useSupportStore()

    await support.reply('TK-1', 'یادداشت', { isInternal: true })

    expect(supportApi.reply).toHaveBeenCalledWith('TK-1', {
      body: 'یادداشت',
      is_internal: true,
    })
  })

  it('keeps the inbox row in step with a status change', async () => {
    supportApi.list.mockResolvedValue({
      data: {
        results: [
          { reference: 'TK-1', status: 'open', unread: 2 },
          { reference: 'TK-2', status: 'open', unread: 0 },
        ],
        count: 2,
      },
    })
    supportApi.close.mockResolvedValue({
      data: { ...TICKET, status: 'closed', status_display: 'بسته' },
    })
    const support = useSupportStore()
    await support.fetchTickets()

    await support.closeTicket('TK-1')

    expect(support.tickets[0].status).toBe('closed')
    expect(support.tickets[0].unread).toBe(0)
    expect(support.tickets[1].status).toBe('open')
  })

  it('reports validation errors when a ticket cannot be created', async () => {
    supportApi.create.mockRejectedValue(
      apiError(400, { subject: ['موضوع نمی‌تواند خالی باشد.'] }),
    )
    const support = useSupportStore()

    const result = await support.createTicket({ subject: '', body: 'x' })

    expect(result.ok).toBe(false)
    expect(support.fieldErrors.subject).toBeTruthy()
    expect(support.tickets).toHaveLength(0)
  })

  it('prepends a newly created ticket to the list', async () => {
    supportApi.create.mockResolvedValue({ data: TICKET })
    const support = useSupportStore()

    const result = await support.createTicket({ subject: 'x', body: 'y' })

    expect(result.ok).toBe(true)
    expect(support.tickets[0].reference).toBe('TK-1')
    expect(support.ticket.reference).toBe('TK-1')
  })

  it('reports isClosed from the loaded thread', async () => {
    supportApi.detail.mockResolvedValue({ data: { ...TICKET, status: 'closed' } })
    const support = useSupportStore()

    await support.fetchTicket('TK-1')

    expect(support.isClosed).toBe(true)
  })

  it('falls back to a readable message when the server sends nothing useful', async () => {
    supportApi.reply.mockRejectedValue(apiError(500, {}))
    const support = useSupportStore()

    const result = await support.reply('TK-1', 'x')

    expect(result.ok).toBe(false)
    expect(support.error).toBe('ارسال پیام ناموفق بود.')
  })

  it('swallows a failed summary rather than blocking the inbox', async () => {
    supportApi.inboxSummary.mockRejectedValue(apiError(500, {}))
    const support = useSupportStore()

    await support.fetchSummary()

    expect(support.summary).toBeNull()
    expect(support.error).toBe('')
  })
})
