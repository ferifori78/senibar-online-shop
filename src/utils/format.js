/** Rial per toman. Every price in the database is rial — that is what both
 *  payment gateways bill in — but Iranians shop in toman, so the storefront
 *  divides for display and nothing else. Doing this at the boundary means the
 *  figure sent to a gateway is never the converted one. */
export const RIAL_PER_TOMAN = 10

/** A rial amount, shown in toman.
 *
 *  Prices are stored and charged in rial. Showing that number with a "تومان"
 *  label is how a 1,200,000-rial order read as 120,000 toman and looked like a
 *  tenfold undercharge — the charge was right, the label was not.
 */
export function formatPrice(value) {
  if (value === null || value === undefined || value === '') return '—'
  const toman = Number(value) / RIAL_PER_TOMAN
  // Iranian prices are whole toman in practice; a stray rial would otherwise
  // render as 120,000.5 and read like a bug.
  return `${toman.toLocaleString('fa-IR', { maximumFractionDigits: 0 })} تومان`
}

/** The same amount labelled in rial — for the payment step, where the figure
 *  the gateway will actually charge should be unambiguous. */
export function formatRial(value) {
  if (value === null || value === undefined || value === '') return '—'
  return `${Number(value).toLocaleString('fa-IR')} ریال`
}

export function formatNumber(value) {
  if (value === null || value === undefined || value === '') return '—'
  return Number(value).toLocaleString('fa-IR')
}

/** ISO date -> Persian (Jalali) calendar date. */
export function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('fa-IR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

/** ISO datetime -> Persian date with the time of day. */
export function formatDateTime(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('fa-IR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatWeight(grams) {
  return grams >= 1000 ? `${grams / 1000} کیلوگرم` : `${formatNumber(grams)} گرم`
}

/** Freshness states from RoastBatch.freshness, as label + status-light state. */
export const FRESHNESS = {
  resting: { label: 'در حال استراحت', state: 'warn' },
  peak: { label: 'اوج تازگی', state: 'ok' },
  fading: { label: 'رو به افول', state: 'warn' },
  stale: { label: 'کهنه', state: 'error' },
}

export function freshnessLabel(key) {
  return FRESHNESS[key]?.label || '—'
}

export function freshnessState(key) {
  return FRESHNESS[key]?.state || 'idle'
}

/** Order statuses: Persian label plus the status-light state that goes with
 *  it. Mirrors Order.Status on the backend. */
export const ORDER_STATUS = {
  pending: { label: 'در انتظار رست', state: 'warn' },
  roasting: { label: 'در حال رست', state: 'active' },
  ground: { label: 'آسیاب شده', state: 'active' },
  packed: { label: 'بسته‌بندی شده', state: 'active' },
  shipped: { label: 'ارسال شده', state: 'active' },
  delivered: { label: 'تحویل شد', state: 'ok' },
  cancelled: { label: 'لغو شد', state: 'error' },
  refunded: { label: 'مسترد شد', state: 'error' },
}

export function orderStatusLabel(key) {
  return ORDER_STATUS[key]?.label || key
}

export function orderStatusState(key) {
  return ORDER_STATUS[key]?.state || 'idle'
}

/** Ticket statuses. `open` means the customer is waiting on us — the lamp
 *  that should draw the eye. Mirrors Ticket.Status on the backend. */
export const TICKET_STATUS = {
  open: { label: 'باز', state: 'warn' },
  pending: { label: 'در انتظار پاسخ شما', state: 'active' },
  closed: { label: 'بسته', state: 'idle' },
}

export function ticketStatusLabel(key) {
  return TICKET_STATUS[key]?.label || key
}

export function ticketStatusState(key) {
  return TICKET_STATUS[key]?.state || 'idle'
}

export const TICKET_TOPICS = [
  { value: 'order', label: 'درباره یک سفارش' },
  { value: 'shipping', label: 'ارسال و تحویل' },
  { value: 'payment', label: 'پرداخت' },
  { value: 'product', label: 'قهوه و دم‌آوری' },
  { value: 'other', label: 'سایر' },
]

export const TICKET_PRIORITY = {
  low: { label: 'کم', state: 'idle' },
  normal: { label: 'عادی', state: 'idle' },
  high: { label: 'زیاد', state: 'warn' },
  urgent: { label: 'فوری', state: 'error' },
}

/** How long ago, in words. Support inboxes are read by recency. */
export function timeAgo(iso) {
  if (!iso) return '—'
  const seconds = Math.floor((Date.now() - new Date(iso)) / 1000)
  if (seconds < 60) return 'همین حالا'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${formatNumber(minutes)} دقیقه پیش`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${formatNumber(hours)} ساعت پیش`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${formatNumber(days)} روز پیش`
  return formatDate(iso)
}

export const PAYMENT_STATUS = {
  unpaid: 'پرداخت نشده',
  paid: 'پرداخت شده',
  failed: 'ناموفق',
  refunded: 'مسترد شده',
}

/** Grind methods, in the order the configurator lays them out: whole bean
 *  first, then coarse to fine. Matches GrindType on the backend. */
export const GRIND_METHODS = [
  { value: 'whole', label: 'دانه کامل', hint: 'بدون آسیاب' },
  { value: 'french_press', label: 'فرنچ‌پرس', hint: 'درشت' },
  { value: 'chemex', label: 'کمکس', hint: 'متوسط-درشت' },
  { value: 'v60', label: 'وی۶۰', hint: 'متوسط' },
  { value: 'aeropress', label: 'ایروپرس', hint: 'متوسط-ریز' },
  { value: 'moka_pot', label: 'موکاپات', hint: 'ریز' },
  { value: 'espresso', label: 'اسپرسو', hint: 'خیلی ریز' },
  { value: 'turkish', label: 'ترک', hint: 'پودری' },
]
