import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('@/api/catalog', () => ({
  catalogApi: { quiz: vi.fn(), recommend: vi.fn() },
  default: { quiz: vi.fn(), recommend: vi.fn() },
}))

import { catalogApi } from '@/api/catalog'
import PlateQuiz from './PlateQuiz.vue'

const QUESTIONS = [
  {
    key: 'flavor',
    title: 'کدام توصیف؟',
    options: [
      { value: 'fruity', label: 'میوه‌ای و روشن' },
      { value: 'chocolate', label: 'شکلاتی و پُرمایه' },
    ],
  },
  {
    key: 'acidity',
    title: 'ترشی؟',
    options: [
      { value: 'love', label: 'بله، هرچه بیشتر بهتر' },
      { value: 'avoid', label: 'ترجیح می‌دهم نباشد' },
    ],
  },
]

function result(score, { against = [], inStock = true } = {}) {
  return {
    data: {
      answered: 2,
      results: [
        {
          product: {
            slug: 'yirga',
            name: 'یرگاچف',
            origin_country: 'اتیوپی',
            price_per_250g: '500000',
            is_in_stock: inStock,
          },
          score,
          reasons: ['نت‌های میوه‌ای دارد'],
          against,
        },
      ],
    },
  }
}

const stubs = {
  RouterLink: { props: ['to'], template: '<a :to="to"><slot /></a>' },
}

async function settle(wrapper, times = 3) {
  for (let i = 0; i < times; i += 1) {
    await Promise.resolve()
    await wrapper.vm.$nextTick()
  }
}

async function start(wrapper) {
  await settle(wrapper)
  await wrapper.find('.plate__start').trigger('click')
  await settle(wrapper)
}

/** Click an option by its wording — the cell it landed in is random. */
async function pick(wrapper, text) {
  const cell = wrapper
    .findAll('.cell--option')
    .find((c) => c.text().includes(text))
  if (!cell) throw new Error(`no option matching "${text}"`)
  await cell.trigger('click')
  await settle(wrapper)
}

describe('PlateQuiz', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    catalogApi.quiz.mockResolvedValue({ data: { questions: QUESTIONS } })
  })

  it('is the specimen plate until it is started', async () => {
    const wrapper = mount(PlateQuiz, { global: { stubs } })
    await settle(wrapper)

    // Nine cells, the name in the centre, glyphs around it — the plate as it
    // always was.
    expect(wrapper.findAll('.cell')).toHaveLength(9)
    expect(wrapper.find('.cell__name').exists()).toBe(true)
    expect(wrapper.findAll('.cell__glyph')).toHaveLength(6)
    expect(wrapper.find('.cell--option').exists()).toBe(false)
    expect(wrapper.text()).toContain('SMALL BATCH')
  })

  it('puts the invitation inside the plate, not under it', async () => {
    const wrapper = mount(PlateQuiz, { global: { stubs } })
    await settle(wrapper)

    // The prompt is one of the nine cells — the empty one below the name —
    // so what you click sits in the plate it is about.
    const start = wrapper.find('.plate__start')
    expect(start.classes()).toContain('cell')
    expect(wrapper.findAll('.cell')[7].text()).toContain('کدام قهوه')
    expect(wrapper.find('.plate__label').text()).not.toContain('کدام قهوه')
  })

  it('gives the invitation cell back to the plate once started', async () => {
    const wrapper = mount(PlateQuiz, { global: { stubs } })
    await start(wrapper)

    // It is an option cell or an empty one now — never a second way in.
    expect(wrapper.find('.plate__start').exists()).toBe(false)
    expect(wrapper.findAll('.cell')).toHaveLength(9)
  })

  it('turns the grid into the question once started', async () => {
    const wrapper = mount(PlateQuiz, { global: { stubs } })
    await start(wrapper)

    expect(wrapper.find('.cell__question').text()).toBe('کدام توصیف؟')
    expect(wrapper.findAll('.cell--option')).toHaveLength(2)
    // The name and the glyphs give way to the questionnaire.
    expect(wrapper.find('.cell__name').exists()).toBe(false)
    expect(wrapper.find('.cell__glyph').exists()).toBe(false)
  })

  it('keeps the plate at nine cells whatever the question', async () => {
    // The grid is the plate; a question with fewer options leaves cells
    // empty rather than changing the shape of the sheet.
    const wrapper = mount(PlateQuiz, { global: { stubs } })
    await start(wrapper)
    expect(wrapper.findAll('.cell')).toHaveLength(9)
  })

  it('scatters the options rather than filling in a fixed order', async () => {
    // Options are dealt into cells at random, so the sheet looks different
    // each run. What must hold is that they land next to the question: the
    // ring around the centre, never a far corner.
    const RING = [5, 2, 1, 0, 3, 6, 7, 8]
    const seen = new Set()

    for (let run = 0; run < 24; run += 1) {
      const wrapper = mount(PlateQuiz, { global: { stubs } })
      await start(wrapper)

      // Which option landed in which cell — not merely which cells are
      // occupied, which two options over two slots never changes.
      const deal = wrapper
        .findAll('.cell')
        .map((cell, i) =>
          cell.classes().includes('cell--option')
            ? `${i}:${cell.find('.cell__full').text()}`
            : null,
        )
        .filter(Boolean)

      expect(deal).toHaveLength(2)
      deal.forEach((d) =>
        expect(RING.slice(0, 2)).toContain(Number(d.split(':')[0])),
      )
      seen.add(deal.join('|'))
    }

    // Two options over two ring cells: both deals should turn up across 24
    // runs. Seeing only one means the shuffle is not shuffling.
    expect(seen.size).toBeGreaterThan(1)
  })

  it('re-deals when the quiz is run again on the same page', async () => {
    // Restarting in place is not the same as a fresh mount: dealing from
    // inside the `cells` computed made a real browser serve the cached
    // arrangement, so every restart after the first repeated the same one.
    //
    // Note this test does NOT catch that bug — checked by reintroducing it,
    // and jsdom re-evaluates the computed where the browser does not. It is
    // kept for the behaviour it does pin (a restart re-deals at all); the
    // caching regression itself is only visible in a browser.
    catalogApi.recommend.mockResolvedValue(result(90))
    const wrapper = mount(PlateQuiz, { global: { stubs } })
    const seen = new Set()

    for (let run = 0; run < 20; run += 1) {
      await start(wrapper)
      seen.add(
        wrapper
          .findAll('.cell')
          .map((c, i) =>
            c.classes().includes('cell--option')
              ? `${i}:${c.find('.cell__full').text()}`
              : null,
          )
          .filter(Boolean)
          .join('|'),
      )
      // Finish the run so the plate offers its way back to the start.
      await wrapper.findAll('.cell--option')[0].trigger('click')
      await wrapper.findAll('.cell--option')[0].trigger('click')
      await settle(wrapper)
      await wrapper.find('.plate__again').trigger('click')
      await settle(wrapper)
    }

    expect(seen.size).toBeGreaterThan(1)
  })

  it('holds a question’s arrangement while the run lasts', async () => {
    // Re-rendering must not re-deal: an option that moves under the reader's
    // cursor as they click it is worse than a fixed layout.
    const wrapper = mount(PlateQuiz, { global: { stubs } })
    await start(wrapper)

    const before = wrapper.findAll('.cell').map((c) => c.text())
    await wrapper.find('.plate__label').trigger('click')
    await settle(wrapper)
    expect(wrapper.findAll('.cell').map((c) => c.text())).toEqual(before)
  })

  it('shows a question exactly as it was when stepped back to', async () => {
    const wrapper = mount(PlateQuiz, { global: { stubs } })
    await start(wrapper)

    const first = wrapper.findAll('.cell').map((c) => c.text())
    await wrapper.findAll('.cell--option')[0].trigger('click')
    await settle(wrapper)
    await wrapper.find('.plate__back').trigger('click')
    await settle(wrapper)

    // Same question, same cells — otherwise going back looks like a new one.
    expect(wrapper.findAll('.cell').map((c) => c.text())).toEqual(first)
  })

  it('walks the questions and submits every answer', async () => {
    catalogApi.recommend.mockResolvedValue(result(90))
    const wrapper = mount(PlateQuiz, { global: { stubs } })
    await start(wrapper)

    // Addressed by option, not by cell: which cell holds it is now random.
    await pick(wrapper, 'میوه‌ای')
    expect(wrapper.find('.cell__question').text()).toBe('ترشی؟')

    await pick(wrapper, 'بله، هرچه بیشتر بهتر')

    expect(catalogApi.recommend).toHaveBeenCalledWith({
      flavor: 'fruity',
      acidity: 'love',
    })
  })

  it('counts the steps in its own caption', async () => {
    const wrapper = mount(PlateQuiz, { global: { stubs } })
    await start(wrapper)
    expect(wrapper.text()).toContain('QUESTION 1 OF 2')

    await wrapper.findAll('.cell--option')[0].trigger('click')
    await settle(wrapper)
    expect(wrapper.text()).toContain('QUESTION 2 OF 2')
  })

  it('lets the customer step back and change an answer', async () => {
    const wrapper = mount(PlateQuiz, { global: { stubs } })
    await start(wrapper)
    await wrapper.findAll('.cell--option')[0].trigger('click')
    await settle(wrapper)

    await wrapper.find('.plate__back').trigger('click')
    await settle(wrapper)
    expect(wrapper.find('.cell__question').text()).toBe('کدام توصیف؟')
  })

  it('shows the recommendations with a way to buy them', async () => {
    catalogApi.recommend.mockResolvedValue(result(92))
    const wrapper = mount(PlateQuiz, { global: { stubs } })
    await start(wrapper)
    await wrapper.findAll('.cell--option')[0].trigger('click')
    await settle(wrapper)
    await wrapper.findAll('.cell--option')[0].trigger('click')
    await settle(wrapper)

    expect(wrapper.find('.picks').exists()).toBe(true)
    expect(wrapper.text()).toContain('یرگاچف')
    const cta = wrapper.find('.pick__cta')
    expect(cta.attributes('to')).toBe('/products/yirga')
    expect(cta.text()).toContain('خرید')
  })

  it('admits when nothing is a close match', async () => {
    catalogApi.recommend.mockResolvedValue(
      result(38, { against: ['اسیدیته‌اش بالاست'] }),
    )
    const wrapper = mount(PlateQuiz, { global: { stubs } })
    await start(wrapper)
    await wrapper.findAll('.cell--option')[0].trigger('click')
    await settle(wrapper)
    await wrapper.findAll('.cell--option')[0].trigger('click')
    await settle(wrapper)

    expect(wrapper.text()).toContain('نزدیک‌ترین')
    expect(wrapper.find('.pick__score--weak').exists()).toBe(true)
    expect(wrapper.find('.pick__against').text()).toContain('اسیدیته')
  })

  it('does not invite a purchase for something out of stock', async () => {
    catalogApi.recommend.mockResolvedValue(result(92, { inStock: false }))
    const wrapper = mount(PlateQuiz, { global: { stubs } })
    await start(wrapper)
    await wrapper.findAll('.cell--option')[0].trigger('click')
    await settle(wrapper)
    await wrapper.findAll('.cell--option')[0].trigger('click')
    await settle(wrapper)

    expect(wrapper.find('.pick__cta').text()).not.toContain('خرید')
  })

  it('returns to the plate when restarted', async () => {
    catalogApi.recommend.mockResolvedValue(result(90))
    const wrapper = mount(PlateQuiz, { global: { stubs } })
    await start(wrapper)
    await wrapper.findAll('.cell--option')[0].trigger('click')
    await settle(wrapper)
    await wrapper.findAll('.cell--option')[0].trigger('click')
    await settle(wrapper)

    await wrapper.find('.plate__again').trigger('click')
    await settle(wrapper)
    expect(wrapper.find('.cell__name').exists()).toBe(true)
    expect(wrapper.findAll('.cell__glyph')).toHaveLength(6)
  })

  it('reports a failed request instead of hanging', async () => {
    catalogApi.recommend.mockRejectedValue({
      response: { status: 500, data: { detail: 'خطای سرور' } },
    })
    const wrapper = mount(PlateQuiz, { global: { stubs } })
    await start(wrapper)
    await wrapper.findAll('.cell--option')[0].trigger('click')
    await settle(wrapper)
    await wrapper.findAll('.cell--option')[0].trigger('click')
    await settle(wrapper)

    expect(wrapper.find('.plate__error').exists()).toBe(true)
  })

  it('cannot be started before the questions arrive', async () => {
    catalogApi.quiz.mockResolvedValue({ data: { questions: [] } })
    const wrapper = mount(PlateQuiz, { global: { stubs } })
    await settle(wrapper)

    expect(wrapper.find('.plate__start').attributes('disabled')).toBeDefined()
    await wrapper.find('.plate__start').trigger('click')
    await settle(wrapper)
    // Still the plate: no question, no options.
    expect(wrapper.find('.cell__question').exists()).toBe(false)
  })

  it('carries the full wording even where the short form is shown', async () => {
    // The cell is small, so the label is shortened — but the whole phrase has
    // to remain available to a screen reader and to the column layout.
    const wrapper = mount(PlateQuiz, { global: { stubs } })
    await start(wrapper)

    // Found by its short form, since the cell it occupies is random.
    const option = wrapper
      .findAll('.cell--option')
      .find((c) => c.text().includes('میوه‌ای'))
    expect(option.find('.cell__full').text()).toBe('میوه‌ای و روشن')
    expect(option.attributes('title')).toBe('میوه‌ای و روشن')
  })
})
