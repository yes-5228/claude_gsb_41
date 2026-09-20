import { useEffect, useRef } from 'react'

/**
 * Reload only when `refreshKey` actually changes.
 * List hooks return a new `reload` identity on every filter/page change;
 * keying the effect off the counter avoids duplicate requests.
 */
export function useRefreshKey(refreshKey, reload) {
  const last = useRef(refreshKey)
  useEffect(() => {
    if (last.current === refreshKey) return
    last.current = refreshKey
    reload()
  }, [refreshKey, reload])
}
