// A tiny hash router. Plain functions, so it is tested without a browser. The URL is the only state that must survive a reload.
export type Route =
  | { name: 'home' }
  | { name: 'new'; sample?: true }
  | { name: 'project'; id: string; phase: string | null }
  | { name: 'traceability'; id: string; item: string | null }
  | { name: 'verify'; id: string }
  | { name: 'not-found'; hash: string }

const SAFE_ID = /^[A-Za-z0-9_-]{1,64}$/
const SAFE_KEY = /^[a-z][a-z0-9_]{0,63}$/
const SAFE_ITEM = /^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d{3,}$/

export function parseHash(hash: string): Route {
  const clean = hash.replace(/^#/, '').split('?')[0].replace(/\/+$/, '')
  if (clean === '' || clean === '/') return { name: 'home' }
  const parts = clean.replace(/^\//, '').split('/')
  if (parts.length === 1 && parts[0] === 'new') return { name: 'new' }
  if (parts.length === 2 && parts[0] === 'new' && parts[1] === 'sample') return { name: 'new', sample: true }
  if (parts[0] === 'projects' && parts.length >= 2 && parts.length <= 4) {
    let id: string
    try {
      id = decodeURIComponent(parts[1])
    } catch {
      return { name: 'not-found', hash: clean }
    }
    if (!SAFE_ID.test(id)) return { name: 'not-found', hash: clean }
    if (parts.length === 2) return { name: 'project', id, phase: null }
    if (parts.length === 4 && parts[2] === 'phases' && SAFE_KEY.test(parts[3])) return { name: 'project', id, phase: parts[3] }
    if (parts.length === 3 && parts[2] === 'traceability') return { name: 'traceability', id, item: null }
    if (parts.length === 3 && parts[2] === 'verify') return { name: 'verify', id }
    if (parts.length === 4 && parts[2] === 'traceability' && SAFE_ITEM.test(parts[3])) return { name: 'traceability', id, item: parts[3] }
  }
  return { name: 'not-found', hash: clean }
}

export function buildHash(route: Route): string {
  switch (route.name) {
    case 'home': return '#/'
    case 'new': return route.sample ? '#/new/sample' : '#/new'
    case 'project': return route.phase ? `#/projects/${encodeURIComponent(route.id)}/phases/${route.phase}` : `#/projects/${encodeURIComponent(route.id)}`
    case 'traceability': return route.item ? `#/projects/${encodeURIComponent(route.id)}/traceability/${route.item}` : `#/projects/${encodeURIComponent(route.id)}/traceability`
    case 'verify': return `#/projects/${encodeURIComponent(route.id)}/verify`
    case 'not-found': return '#/'
  }
}
