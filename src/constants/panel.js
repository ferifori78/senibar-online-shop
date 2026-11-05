/** Base path of the Senobar admin panel.
 *
 *  Deliberately not `/admin`: that path belongs to Django's own admin, which
 *  Nginx proxies to the backend, so the SPA router would never see it. Keeping
 *  the base in one place means the panel can be moved by editing this line —
 *  and the Nginx `location` blocks that pair with it.
 */
export const PANEL_BASE = '/senobar-panel/nazadmin'

/** `${PANEL_BASE}/orders` and friends, without repeating the base everywhere. */
export function panelPath(segment = '') {
  return segment ? `${PANEL_BASE}/${segment}` : PANEL_BASE
}
