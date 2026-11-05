import client from './client'

/**
 * Tell the server a page was viewed, for the shop's traffic digest.
 *
 * Fire-and-forget: the promise is never awaited by the caller and every
 * failure is swallowed. Nothing a visitor sees depends on this succeeding,
 * and a counter that could break a page would not be worth having.
 *
 * The referrer is sent only on the first view of a session — after that it is
 * the previous page of this same site, which tells the roaster nothing about
 * where the traffic came from.
 */
let sentReferrer = false

export function recordVisit(path) {
  const payload = { path }

  if (!sentReferrer) {
    sentReferrer = true
    if (typeof document !== 'undefined' && document.referrer) {
      payload.referrer = document.referrer
    }
  }

  return client.post('/visits/', payload).catch(() => {})
}

export default { recordVisit }
