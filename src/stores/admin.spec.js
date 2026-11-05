import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/admin', () => ({
  default: {
    dashboard: vi.fn(),
    board: vi.fn(),
    orders: vi.fn(),
    order: vi.fn(),
    setStatus: vi.fn(),
    products: vi.fn(),
    createProduct: vi.fn(),
    updateProduct: vi.fn(),
    deleteProduct: vi.fn(),
    archiveProduct: vi.fn(),
    productImages: vi.fn(),
    uploadProductImage: vi.fn(),
    deleteProductImage: vi.fn(),
    setProductCover: vi.fn(),
    reorderProductImages: vi.fn(),
    batches: vi.fn(),
    createBatch: vi.fn(),
    updateBatch: vi.fn(),
  },
}))

import adminApi from '@/api/admin'
import { useAdminStore } from './admin'

function apiError(status, data) {
  return Object.assign(new Error('failed'), { response: { status, data } })
}

describe('admin store', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
  })

  it('exposes the headline figures from the dashboard', async () => {
    adminApi.dashboard.mockResolvedValue({
      data: { sales: { today: '7080000' }, queue: { awaiting_roast: 4 } },
    })
    const admin = useAdminStore()

    await admin.fetchStats()

    expect(admin.todaySales).toBe(7080000)
    expect(admin.awaitingRoast).toBe(4)
    expect(admin.loading).toBe(false)
  })

  it('sends the active filter and search to the board endpoint', async () => {
    adminApi.board.mockResolvedValue({ data: { results: [] } })
    const admin = useAdminStore()
    admin.boardSearch = 'Cerrado'

    await admin.setBoardFilter('roasting')

    expect(adminApi.board).toHaveBeenCalledWith({ state: 'roasting', search: 'Cerrado' })
  })

  it('omits the state param when the filter is "all"', async () => {
    adminApi.board.mockResolvedValue({ data: { results: [] } })
    const admin = useAdminStore()

    await admin.setBoardFilter('all')

    expect(adminApi.board).toHaveBeenCalledWith({})
  })

  it('folds a status change back into the board rows', async () => {
    adminApi.board.mockResolvedValue({
      data: {
        results: [
          { order_number: 'SB-1', order_status: 'pending', product_name: 'A' },
          { order_number: 'SB-1', order_status: 'pending', product_name: 'B' },
          { order_number: 'SB-2', order_status: 'pending', product_name: 'C' },
        ],
      },
    })
    adminApi.setStatus.mockResolvedValue({ data: { number: 'SB-1', status: 'roasting' } })
    const admin = useAdminStore()
    await admin.fetchBoard()

    await admin.setStatus('SB-1', 'roasting', 'batch 1')

    // Both lines of SB-1 update; SB-2 is untouched.
    expect(admin.board[0].order_status).toBe('roasting')
    expect(admin.board[1].order_status).toBe('roasting')
    expect(admin.board[2].order_status).toBe('pending')
    expect(adminApi.setStatus).toHaveBeenCalledWith('SB-1', {
      status: 'roasting',
      note: 'batch 1',
    })
  })

  it('surfaces a rejected transition without changing local state', async () => {
    adminApi.board.mockResolvedValue({
      data: { results: [{ order_number: 'SB-1', order_status: 'pending' }] },
    })
    adminApi.setStatus.mockRejectedValue(
      apiError(400, { status: ['Cannot move from Pending to Delivered.'] }),
    )
    const admin = useAdminStore()
    await admin.fetchBoard()

    const result = await admin.setStatus('SB-1', 'delivered')

    expect(result.ok).toBe(false)
    expect(admin.board[0].order_status).toBe('pending')
    expect(admin.fieldErrors.status).toContain('Cannot move')
    expect(admin.acting).toBe(false)
  })

  it('prepends a newly created product to the list', async () => {
    adminApi.products.mockResolvedValue({ data: { results: [{ slug: 'old', name: 'Old' }] } })
    adminApi.createProduct.mockResolvedValue({ data: { slug: 'new', name: 'New' } })
    const admin = useAdminStore()
    await admin.fetchProducts()

    const result = await admin.saveProduct({ name: 'New' })

    expect(result.ok).toBe(true)
    expect(admin.products[0].slug).toBe('new')
    expect(admin.products).toHaveLength(2)
    expect(adminApi.createProduct).toHaveBeenCalled()
    expect(adminApi.updateProduct).not.toHaveBeenCalled()
  })

  it('replaces the row in place when editing an existing product', async () => {
    adminApi.products.mockResolvedValue({
      data: { results: [{ slug: 'eth', name: 'Old name', status: 'draft' }] },
    })
    adminApi.updateProduct.mockResolvedValue({
      data: { slug: 'eth', name: 'New name', status: 'published' },
    })
    const admin = useAdminStore()
    await admin.fetchProducts()

    await admin.saveProduct({ name: 'New name' }, 'eth')

    expect(admin.products).toHaveLength(1)
    expect(admin.products[0].name).toBe('New name')
    expect(admin.products[0].status).toBe('published')
  })

  it('reports field errors when a product fails validation', async () => {
    adminApi.createProduct.mockRejectedValue(
      apiError(400, { name: ['This field is required.'], price_per_250g: ['Required.'] }),
    )
    const admin = useAdminStore()

    const result = await admin.saveProduct({})

    expect(result.ok).toBe(false)
    expect(admin.fieldErrors.name).toContain('required')
    expect(admin.fieldErrors.price_per_250g).toBeTruthy()
    expect(admin.products).toHaveLength(0)
  })

  it('keeps a product that was archived instead of erased, and marks it so', async () => {
    // The server answers 200 with a body when orders or batches point at the
    // coffee. Dropping the row here would hide a product that still exists.
    adminApi.products.mockResolvedValue({
      data: { results: [{ slug: 'eth', name: 'Eth', status: 'published' }] },
    })
    adminApi.deleteProduct.mockResolvedValue({
      status: 200,
      data: { archived: true, blockers: { orders: 2, batches: 0 }, detail: 'بایگانی شد.' },
    })
    const admin = useAdminStore()
    await admin.fetchProducts()

    const result = await admin.deleteProduct('eth')

    expect(result.ok).toBe(true)
    expect(result.erased).toBe(false)
    expect(result.detail).toContain('بایگانی')
    expect(admin.products).toHaveLength(1)
    expect(admin.products[0].status).toBe('archived')
  })

  it('drops a product the server actually erased', async () => {
    adminApi.products.mockResolvedValue({
      data: { results: [{ slug: 'a' }, { slug: 'b' }] },
    })
    adminApi.deleteProduct.mockResolvedValue({ status: 204, data: null })
    const admin = useAdminStore()
    await admin.fetchProducts()

    const result = await admin.deleteProduct('a')

    expect(result.erased).toBe(true)
    expect(admin.products.map((p) => p.slug)).toEqual(['b'])
  })

  it('keeps the list intact when the delete itself fails', async () => {
    adminApi.products.mockResolvedValue({ data: { results: [{ slug: 'a' }] } })
    adminApi.deleteProduct.mockRejectedValue(apiError(500, {}))
    const admin = useAdminStore()
    await admin.fetchProducts()

    const result = await admin.deleteProduct('a')

    expect(result.ok).toBe(false)
    expect(admin.products).toHaveLength(1)
    expect(admin.error).toBeTruthy()
  })

  it('marks a product archived when archiving it directly', async () => {
    adminApi.products.mockResolvedValue({
      data: { results: [{ slug: 'eth', status: 'published' }] },
    })
    adminApi.archiveProduct.mockResolvedValue({
      data: { slug: 'eth', status: 'archived', changed: true },
    })
    const admin = useAdminStore()
    await admin.fetchProducts()

    await admin.archiveProduct('eth')

    expect(admin.products[0].status).toBe('archived')
  })

  it('returns the gallery without writing it into the product list', async () => {
    // The form modal owns the photo list while open; the product list only
    // needs the cover, which the product payload already carries.
    adminApi.productImages.mockResolvedValue({ data: [{ id: 1, is_cover: true }] })
    const admin = useAdminStore()

    const result = await admin.fetchProductImages('eth')

    expect(result.ok).toBe(true)
    expect(result.images).toHaveLength(1)
    expect(admin.products).toHaveLength(0)
  })

  it('surfaces an upload rejection rather than swallowing it', async () => {
    // Pillow refuses anything that is not a real image; the roaster needs to
    // be told, not left looking at a gallery that silently did not grow.
    adminApi.uploadProductImage.mockRejectedValue(
      apiError(400, { image: ['فایل معتبر تصویری نیست.'] }),
    )
    const admin = useAdminStore()

    const result = await admin.uploadProductImage('eth', new Blob())

    expect(result.ok).toBe(false)
    expect(admin.fieldErrors.image).toBeTruthy()
  })

  it('returns the reordered gallery from the server, not the optimistic guess', async () => {
    adminApi.reorderProductImages.mockResolvedValue({
      data: [{ id: 3 }, { id: 1 }, { id: 2 }],
    })
    const admin = useAdminStore()

    const result = await admin.reorderProductImages('eth', [3, 1, 2])

    expect(result.images.map((i) => i.id)).toEqual([3, 1, 2])
  })

  it('updates a batch in place when releasing it', async () => {
    adminApi.batches.mockResolvedValue({
      data: { results: [{ id: 7, batch_code: 'ETH-01', status: 'resting' }] },
    })
    adminApi.updateBatch.mockResolvedValue({
      data: { id: 7, batch_code: 'ETH-01', status: 'available' },
    })
    const admin = useAdminStore()
    await admin.fetchBatches()

    await admin.saveBatch({ status: 'available' }, 7)

    expect(admin.batches).toHaveLength(1)
    expect(admin.batches[0].status).toBe('available')
  })
})
