// The two folders last checked for a project, kept in this browser so the person does not retype them. Only a convenience: it may come back empty.
export interface Paths { backend: string; frontend: string }
export interface KeyValueStore { getItem(key: string): string | null; setItem(key: string, value: string): void }

const key = (projectId: string) => `sdlc.verify.paths.${projectId}`
const MAX = 1000

export function loadPaths(store: KeyValueStore | null, projectId: string): Paths {
  try {
    const raw = store?.getItem(key(projectId))
    if (!raw) return { backend: '', frontend: '' }
    const o = JSON.parse(raw) as Record<string, unknown>
    const text = (v: unknown) => (typeof v === 'string' ? v.slice(0, MAX) : '')
    return { backend: text(o.backend), frontend: text(o.frontend) }
  } catch {
    return { backend: '', frontend: '' }
  }
}

export function savePaths(store: KeyValueStore | null, projectId: string, paths: Paths): void {
  try {
    store?.setItem(key(projectId), JSON.stringify({ backend: paths.backend.slice(0, MAX), frontend: paths.frontend.slice(0, MAX) }))
  } catch {
    /* a full or blocked store is not an error: the page works without it */
  }
}
