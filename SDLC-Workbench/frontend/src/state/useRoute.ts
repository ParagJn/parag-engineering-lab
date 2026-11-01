import { useEffect, useState } from 'react'
import { buildHash, parseHash, type Route } from '../lib/router'

export function useRoute(): [Route, (route: Route) => void] {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash))
  useEffect(() => {
    const onChange = () => setRoute(parseHash(window.location.hash))
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return [route, (next) => { window.location.hash = buildHash(next) }]
}
