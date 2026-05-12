/**
 * Shared scope filters backed by the URL's query string.
 *
 * Keeping filter state in the URL gives us three things:
 *   1. Reload survives — refresh the page, the filters stay.
 *   2. Sharable links — paste a URL into Slack and the recipient sees
 *      the same filtered view.
 *   3. No shared global state to wire — every page reads from the URL
 *      and writes to it through this one hook.
 *
 * The hook is intentionally generous about types: it doesn't try to
 * narrow `platform` to `"android" | "ios" | "unknown"` etc., because
 * the FilterBar UI is the authority on what users can pick. Endpoint-
 * level validation happens server-side already (400 for invalid values).
 */
import { useSearchParams } from 'react-router-dom'

export type Filters = {
  app?: string
  platform?: string
  channel?: string
  range_days?: number
}

export function useFilters() {
  const [params, setParams] = useSearchParams()

  const filters: Filters = {
    app: params.get('app') || undefined,
    platform: params.get('platform') || undefined,
    channel: params.get('channel') || undefined,
    range_days: params.get('range_days')
      ? Number(params.get('range_days'))
      : undefined,
  }

  function setFilter<K extends keyof Filters>(key: K, value: Filters[K]) {
    const next = new URLSearchParams(params)
    if (value === undefined || value === null || value === '' || value === 'all') {
      next.delete(key)
    } else {
      next.set(key, String(value))
    }
    setParams(next, { replace: true })
  }

  function reset() {
    setParams(new URLSearchParams(), { replace: true })
  }

  return { filters, setFilter, reset }
}
