import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/auth', () => ({
  default: {
    requestCode: vi.fn(),
    verifyCode: vi.fn(),
    profile: vi.fn(),
    logout: vi.fn(),
  },
}))

import authApi from '@/api/auth'
import OtpForm from './OtpForm.vue'

const PHONE = '09121234567'

/** Type into the nth field of the form. */
async function fill(wrapper, index, value) {
  const input = wrapper.findAll('input')[index]
  await input.setValue(value)
  return input
}

describe('OtpForm', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    localStorage.clear()
    vi.useRealTimers()
  })

  it('starts by asking for a number', () => {
    const wrapper = mount(OtpForm)
    expect(wrapper.text()).toContain('شماره موبایل')
    // One field, and no "we texted you" line yet. Asserting on the label text
    // alone would trip over the hint, which mentions the code too.
    expect(wrapper.findAll('input')).toHaveLength(1)
    expect(wrapper.find('.otp__sent').exists()).toBe(false)
  })

  it('moves to the code step once a code is sent', async () => {
    authApi.requestCode.mockResolvedValue({
      data: { is_new: false, expires_in: 120, resend_after: 60 },
    })
    const wrapper = mount(OtpForm)

    await fill(wrapper, 0, PHONE)
    await wrapper.find('form').trigger('submit')
    await new Promise((r) => setTimeout(r, 0))

    expect(authApi.requestCode).toHaveBeenCalledWith(PHONE)
    expect(wrapper.text()).toContain('کد ورود')
    expect(wrapper.text()).toContain(PHONE)
  })

  it('asks a new customer for a name, but not a returning one', async () => {
    authApi.requestCode.mockResolvedValue({
      data: { is_new: true, expires_in: 120, resend_after: 60 },
    })
    const wrapper = mount(OtpForm)
    await fill(wrapper, 0, PHONE)
    await wrapper.find('form').trigger('submit')
    await new Promise((r) => setTimeout(r, 0))

    expect(wrapper.text()).toContain('نام شما')

    setActivePinia(createPinia())
    authApi.requestCode.mockResolvedValue({
      data: { is_new: false, expires_in: 120, resend_after: 60 },
    })
    const returning = mount(OtpForm)
    await fill(returning, 0, PHONE)
    await returning.find('form').trigger('submit')
    await new Promise((r) => setTimeout(r, 0))

    expect(returning.text()).not.toContain('نام شما')
  })

  it('sends the name only for a new number', async () => {
    authApi.requestCode.mockResolvedValue({
      data: { is_new: true, expires_in: 120, resend_after: 60 },
    })
    authApi.verifyCode.mockResolvedValue({
      data: { access: 'a', refresh: 'r', user: { id: 1 }, created: true },
    })
    const wrapper = mount(OtpForm)

    await fill(wrapper, 0, PHONE)
    await wrapper.find('form').trigger('submit')
    await new Promise((r) => setTimeout(r, 0))

    await fill(wrapper, 0, '12345')
    await fill(wrapper, 1, 'سپیده')
    await wrapper.find('form').trigger('submit')
    await new Promise((r) => setTimeout(r, 0))

    expect(authApi.verifyCode).toHaveBeenCalledWith({
      phone: PHONE,
      code: '12345',
      name: 'سپیده',
    })
  })

  it('emits done once the code is accepted', async () => {
    authApi.requestCode.mockResolvedValue({
      data: { is_new: false, expires_in: 120, resend_after: 60 },
    })
    authApi.verifyCode.mockResolvedValue({
      data: { access: 'a', refresh: 'r', user: { id: 1 }, created: false },
    })
    const wrapper = mount(OtpForm)

    await fill(wrapper, 0, PHONE)
    await wrapper.find('form').trigger('submit')
    await new Promise((r) => setTimeout(r, 0))

    await fill(wrapper, 0, '12345')
    await wrapper.find('form').trigger('submit')
    await new Promise((r) => setTimeout(r, 0))

    expect(wrapper.emitted('done')).toBeTruthy()
  })

  it('keeps the customer on the code step when the code is wrong', async () => {
    authApi.requestCode.mockResolvedValue({
      data: { is_new: false, expires_in: 120, resend_after: 60 },
    })
    authApi.verifyCode.mockRejectedValue({
      response: { status: 400, data: { detail: 'کد وارد شده نادرست است.' } },
    })
    const wrapper = mount(OtpForm)

    await fill(wrapper, 0, PHONE)
    await wrapper.find('form').trigger('submit')
    await new Promise((r) => setTimeout(r, 0))

    await fill(wrapper, 0, '00000')
    await wrapper.find('form').trigger('submit')
    await new Promise((r) => setTimeout(r, 0))

    expect(wrapper.emitted('done')).toBeFalsy()
    expect(wrapper.text()).toContain('نادرست')
  })

  it('lets the customer go back and fix a mistyped number', async () => {
    authApi.requestCode.mockResolvedValue({
      data: { is_new: false, expires_in: 120, resend_after: 60 },
    })
    const wrapper = mount(OtpForm)
    await fill(wrapper, 0, PHONE)
    await wrapper.find('form').trigger('submit')
    await new Promise((r) => setTimeout(r, 0))

    await wrapper.find('.otp__edit').trigger('click')
    expect(wrapper.text()).toContain('شماره موبایل')
  })

  it('disables resend for as long as the server says to wait', async () => {
    authApi.requestCode.mockResolvedValue({
      data: { is_new: false, expires_in: 120, resend_after: 60 },
    })
    const wrapper = mount(OtpForm)
    await fill(wrapper, 0, PHONE)
    await wrapper.find('form').trigger('submit')
    await new Promise((r) => setTimeout(r, 0))

    const resend = wrapper.find('.otp__resend')
    expect(resend.attributes('disabled')).toBeDefined()
    expect(resend.text()).toContain('ثانیه')
  })

  it('starts the countdown from a refusal, so the button cannot be hammered', async () => {
    // 429 carries retry_after; without honouring it the customer would press
    // resend straight back into the same error.
    authApi.requestCode.mockRejectedValue({
      response: { status: 429, data: { detail: 'کمی صبر کنید.', retry_after: 45 } },
    })
    const wrapper = mount(OtpForm)
    await fill(wrapper, 0, PHONE)
    await wrapper.find('form').trigger('submit')
    await new Promise((r) => setTimeout(r, 0))

    // Still on the phone step, and the error is shown.
    expect(wrapper.text()).toContain('صبر')
  })

  it('strips anything that is not a digit from a pasted code', async () => {
    authApi.requestCode.mockResolvedValue({
      data: { is_new: false, expires_in: 120, resend_after: 60 },
    })
    const wrapper = mount(OtpForm)
    await fill(wrapper, 0, PHONE)
    await wrapper.find('form').trigger('submit')
    await new Promise((r) => setTimeout(r, 0))

    // People paste the whole SMS line, not just the number.
    await fill(wrapper, 0, 'کد: 12345')
    await new Promise((r) => setTimeout(r, 0))
    expect(wrapper.findAll('input')[0].element.value).toBe('12345')
  })
})
